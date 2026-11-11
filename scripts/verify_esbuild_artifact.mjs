import childProcess from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const reviewedArtifact = Object.freeze(JSON.parse(fs.readFileSync(
  new URL('./esbuild-linux-x64-artifact.json', import.meta.url), 'utf8')));

function require(condition, message) {
  if (!condition) throw new Error(message);
}

// Identity binds this file to separately reviewed build-info evidence, not a generic Go parser.
export function verifyArtifactIdentity(binary, artifact = reviewedArtifact) {
  require(artifact.schema_version === 1 && artifact.build_metadata_present === true,
    'Reviewed artifact metadata is required');
  require(artifact.platform === process.platform && artifact.architecture === process.arch,
    'Artifact platform does not match this host');
  require(typeof binary === 'string' && path.isAbsolute(binary) && fs.realpathSync(binary) === binary,
    'An absolute non-symlink binary path is required');
  for (let parent = path.dirname(binary); ; parent = path.dirname(parent)) {
    const info = fs.statSync(parent);
    const stickyRoot = info.uid === 0 && (info.mode & 0o1000) !== 0;
    require([0, process.getuid()].includes(info.uid) && ((info.mode & 0o022) === 0 || stickyRoot),
      'Binary parent directory is not trusted');
    if (path.dirname(parent) === parent) break;
  }
  const descriptor = fs.openSync(binary, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
  try {
    const before = fs.fstatSync(descriptor);
    require(before.isFile() && (before.mode & 0o111) !== 0 && (before.mode & 0o222) === 0,
      'Binary must be a non-writable executable regular file');
    require([0, process.getuid()].includes(before.uid), 'Binary owner is not trusted');
    require(before.size === artifact.bytes && /^[a-f0-9]{64}$/.test(artifact.sha256),
      'Artifact size or manifest digest is invalid');
    const digest = crypto.createHash('sha256');
    const buffer = Buffer.alloc(64 * 1024);
    let offset = 0;
    while (true) {
      const count = fs.readSync(descriptor, buffer, 0, buffer.length, offset);
      if (!count) break;
      if (offset === 0) require(buffer.subarray(0, 4).equals(Buffer.from([0x7f, 0x45, 0x4c, 0x46])),
        'Reviewed artifact must be an ELF binary');
      digest.update(buffer.subarray(0, count));
      offset += count;
    }
    require(offset === artifact.bytes && digest.digest('hex') === artifact.sha256,
      'Artifact SHA256 does not match the reviewed candidate');
    const after = fs.fstatSync(descriptor);
    const current = fs.lstatSync(binary);
    require(before.ino === current.ino && before.dev === current.dev && before.size === after.size
      && before.mtimeMs === after.mtimeMs && before.ctimeMs === after.ctimeMs,
    'Artifact changed during verification');
    const version = childProcess.execFileSync(binary, ['--version'], {
      encoding: 'utf8', timeout: 5000, maxBuffer: 8192,
      env: { PATH: '/usr/bin:/bin', LANG: 'C.UTF-8' }, stdio: ['ignore', 'pipe', 'pipe'],
    }).trim();
    require(version === artifact.api_version, 'Artifact API version mismatch');
    return { identity_verified: true, binary, sha256: artifact.sha256, api_version: version,
      security_accepted: artifact.security_accepted === true, open_advisory: artifact.open_advisory };
  } finally {
    fs.closeSync(descriptor);
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    require(process.argv.length === 3, 'Usage: node scripts/verify_esbuild_artifact.mjs /absolute/esbuild');
    console.log(JSON.stringify(verifyArtifactIdentity(process.argv[2])));
  } catch {
    console.error('Artifact identity verification failed; no fallback is permitted');
    process.exitCode = 1;
  }
}
