import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { reviewedArtifact, verifyArtifactIdentity } from './verify_esbuild_artifact.mjs';

export const archivePin = Object.freeze(JSON.parse(fs.readFileSync(
  new URL('./esbuild-provider-archive.json', import.meta.url), 'utf8')));
const repository = fileURLToPath(new URL('..', import.meta.url)).replace(/\/$/, '');

function verifiedArchiveBytes(archive, pin) {
  const info = fs.lstatSync(archive);
  assert(info.isFile() && info.size === pin.bytes, 'Provider archive is not the pinned regular file');
  const bytes = fs.readFileSync(archive);
  assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'), pin.sha256, 'Provider archive SHA256 mismatch');
  assert.equal('sha512-' + crypto.createHash('sha512').update(bytes).digest('base64'), pin.integrity,
    'Provider archive integrity mismatch');
  return bytes;
}

export function stageContext({ binary, archive, output, artifact = reviewedArtifact, pin = archivePin }) {
  assert(path.isAbsolute(output) && path.resolve(output) === output, 'Absolute canonical output required');
  assert(!fs.existsSync(output), 'Existing output is never overwritten');
  assert(output !== repository && !output.startsWith(`${repository}/`), 'Executable context must stay outside the repository');
  assert(pin.schema_version === 1 && pin.binary_sha256 === artifact.sha256);
  assert(pin.filename === 'omerta-esbuild-linux-x64-0.28.2-omerta.1.tgz');
  verifyArtifactIdentity(binary, artifact);
  const bytes = verifiedArchiveBytes(archive, pin);
  let parent = path.dirname(output);
  while (!fs.existsSync(parent)) parent = path.dirname(parent);
  assert.equal(fs.realpathSync(parent), parent, 'Symlink output ancestry is forbidden');
  for (let current = parent; ; current = path.dirname(current)) {
    const owner = fs.statSync(current);
    const stickyRoot = owner.uid === 0 && (owner.mode & 0o1000) !== 0;
    assert([0, process.getuid()].includes(owner.uid) && ((owner.mode & 0o022) === 0 || stickyRoot),
      'Output ancestry is not trusted');
    if (path.dirname(current) === current) break;
  }
  fs.mkdirSync(path.dirname(output), { recursive: true, mode: 0o700 });
  fs.mkdirSync(output, { mode: 0o700 });
  fs.copyFileSync(binary, path.join(output, 'esbuild'), fs.constants.COPYFILE_EXCL);
  fs.chmodSync(path.join(output, 'esbuild'), 0o555);
  fs.writeFileSync(path.join(output, pin.filename), bytes, { flag: 'wx', mode: 0o444 });
  fs.writeFileSync(path.join(output, 'provenance.json'), JSON.stringify(artifact, null, 2) + '\n',
    { flag: 'wx', mode: 0o444 });
  verifyArtifactIdentity(path.join(output, 'esbuild'), artifact);
  return { output, files: fs.readdirSync(output).sort(), security_accepted: false };
}

export function stageWorkspaceArchive({ context, workspace, artifact = reviewedArtifact, pin = archivePin }) {
  assert(path.isAbsolute(workspace) && fs.realpathSync(workspace) === workspace, 'Canonical workspace required');
  verifyArtifactIdentity(path.join(context, 'esbuild'), artifact);
  const bytes = verifiedArchiveBytes(path.join(context, pin.filename), pin);
  const directory = path.join(workspace, 'artifacts/tooling/esbuild');
  let current = workspace;
  for (const part of ['artifacts', 'tooling', 'esbuild']) {
    current = path.join(current, part);
    try {
      const info = fs.lstatSync(current);
      assert(info.isDirectory() && !info.isSymbolicLink(), 'Symlink archive destination is forbidden');
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
      fs.mkdirSync(current, { mode: 0o700 });
    }
  }
  const destination = path.join(directory, pin.filename);
  if (fs.existsSync(destination)) verifiedArchiveBytes(destination, pin);
  else fs.writeFileSync(destination, bytes, { flag: 'wx', mode: 0o444 });
  return { archive: destination, security_accepted: false };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    if (process.argv[2] === '--link-workspace') {
      assert.equal(process.argv.length, 5);
      console.log(JSON.stringify(stageWorkspaceArchive({ context: process.argv[3], workspace: process.argv[4] })));
    } else {
      assert([5, 7].includes(process.argv.length));
      console.log(JSON.stringify(stageContext({ binary: process.argv[2], archive: process.argv[3], output: process.argv[4] })));
      if (process.argv.length === 7) {
        assert.equal(process.argv[5], '--workspace');
        console.log(JSON.stringify(stageWorkspaceArchive({ context: process.argv[4], workspace: process.argv[6] })));
      }
    }
  } catch {
    console.error('Verified esbuild context staging failed; no fallback or overwrite');
    process.exitCode = 1;
  }
}
