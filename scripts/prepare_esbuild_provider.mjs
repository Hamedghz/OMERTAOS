import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { reviewedArtifact, verifyArtifactIdentity } from './verify_esbuild_artifact.mjs';

const repository = fileURLToPath(new URL('..', import.meta.url)).replace(/\/$/, '');

function require(condition, message) {
  if (!condition) throw new Error(message);
}

export function prepareProvider({ binary, license, output, artifact = reviewedArtifact }) {
  require(artifact.provider_name === '@omerta/esbuild-linux-x64', 'Independent provider identity required');
  require(typeof output === 'string' && path.isAbsolute(output) && path.resolve(output) === output,
    'A new absolute output directory is required');
  require(output !== repository && !output.startsWith(`${repository}/`), 'Output must be outside the repository');
  require(!fs.existsSync(output), 'Output already exists; no overwrite is permitted');
  const parent = path.dirname(output);
  const owner = fs.statSync(parent);
  require(fs.realpathSync(parent) === parent && owner.uid === process.getuid() && (owner.mode & 0o077) === 0,
    'Output needs a canonical private caller-owned parent');
  verifyArtifactIdentity(binary, artifact);
  const info = fs.lstatSync(license);
  require(info.isFile() && info.size < 65536, 'A bounded regular upstream license file is required');
  const licenseBytes = fs.readFileSync(license);
  require(crypto.createHash('sha256').update(licenseBytes).digest('hex') === artifact.license_sha256,
    'Upstream license digest mismatch');

  fs.mkdirSync(output, { mode: 0o700 });
  fs.mkdirSync(path.join(output, 'bin'), { mode: 0o755 });
  const copy = path.join(output, 'bin/esbuild');
  fs.copyFileSync(binary, copy, fs.constants.COPYFILE_EXCL);
  fs.chmodSync(copy, 0o555);
  verifyArtifactIdentity(copy, artifact);
  const manifest = {
    name: artifact.provider_name, version: artifact.provider_version, private: true,
    description: 'Locally rebuilt esbuild candidate; not security-accepted', license: 'MIT',
    os: [artifact.platform], cpu: [artifact.architecture],
    files: ['bin/esbuild', 'LICENSE.md', 'provenance.json'],
  };
  for (const [name, bytes] of [
    ['package.json', JSON.stringify(manifest, null, 2) + '\n'],
    ['provenance.json', JSON.stringify({ ...artifact, unsigned_local_manifest: true }, null, 2) + '\n'],
    ['LICENSE.md', licenseBytes],
  ]) fs.writeFileSync(path.join(output, name), bytes, { flag: 'wx', mode: 0o444 });
  return { output, name: manifest.name, version: manifest.version,
    sha256: artifact.sha256, security_accepted: artifact.security_accepted === true };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    require(process.argv.length === 5,
      'Usage: node scripts/prepare_esbuild_provider.mjs /absolute/esbuild /upstream/LICENSE.md /new/private/output');
    console.log(JSON.stringify(prepareProvider({ binary: process.argv[2], license: process.argv[3], output: process.argv[4] })));
  } catch (error) {
    console.error(`Provider preparation failed: ${error.message}`);
    process.exitCode = 1;
  }
}
