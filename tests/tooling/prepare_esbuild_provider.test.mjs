import assert from 'node:assert/strict';
import childProcess from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { prepareProvider } from '../../scripts/prepare_esbuild_provider.mjs';
import { reviewedArtifact } from '../../scripts/verify_esbuild_artifact.mjs';

function fixture(t) {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'omerta-provider-test-')));
  t.after(() => fs.rmSync(root, { recursive: true }));
  const binary = path.join(root, 'esbuild');
  const license = path.join(root, 'LICENSE.md');
  const bytes = Buffer.from('\x7fELFsynthetic-unit-fixture');
  const licenseBytes = Buffer.from('synthetic test license');
  fs.writeFileSync(binary, bytes, { mode: 0o555 });
  fs.writeFileSync(license, licenseBytes);
  const artifact = { ...reviewedArtifact, bytes: bytes.length,
    sha256: crypto.createHash('sha256').update(bytes).digest('hex'),
    license_sha256: crypto.createHash('sha256').update(licenseBytes).digest('hex') };
  t.mock.method(childProcess, 'execFileSync', () => `${artifact.api_version}\n`);
  return { binary, license, output: path.join(root, 'provider'), artifact };
}

test('new provider has its own identity, exact bytes, license and unsigned provenance', (t) => {
  const input = fixture(t);
  const result = prepareProvider(input);
  const manifest = JSON.parse(fs.readFileSync(path.join(input.output, 'package.json')));
  assert.equal(manifest.name, '@omerta/esbuild-linux-x64');
  assert.equal(manifest.private, true);
  assert.equal(manifest.scripts, undefined);
  assert.equal(result.security_accepted, false);
  assert.deepEqual(fs.readFileSync(path.join(input.output, 'bin/esbuild')), fs.readFileSync(input.binary));
  assert.equal(fs.statSync(path.join(input.output, 'bin/esbuild')).mode & 0o777, 0o555);
  const provenance = JSON.parse(fs.readFileSync(path.join(input.output, 'provenance.json')));
  assert.equal(provenance.unsigned_local_manifest, true);
  assert.equal(provenance.security_accepted, false);
  assert.equal(provenance.open_advisory, reviewedArtifact.open_advisory);
});

for (const [label, change] of [
  ['publisher impersonation', (f) => { f.artifact.provider_name = '@esbuild/linux-x64'; }],
  ['bad binary digest', (f) => { f.artifact.sha256 = '0'.repeat(64); }],
  ['bad license digest', (f) => { f.artifact.license_sha256 = '0'.repeat(64); }],
  ['non-private parent', (f) => { fs.chmodSync(path.dirname(f.output), 0o755); }],
  ['relative destination', (f) => { f.output = 'relative-provider'; }],
  ['repository destination', (f) => { f.output = path.resolve('provider-unit-fixture'); }],
]) {
  test(`${label} is rejected before creating output`, (t) => {
    const input = fixture(t);
    change(input);
    assert.throws(() => prepareProvider(input));
    assert.equal(fs.existsSync(input.output), false);
  });
}

test('existing output is preserved unchanged', (t) => {
  const input = fixture(t);
  fs.mkdirSync(input.output);
  const retained = path.join(input.output, 'retained');
  fs.writeFileSync(retained, 'existing data');
  assert.throws(() => prepareProvider(input), /already exists/);
  assert.equal(fs.readFileSync(retained, 'utf8'), 'existing data');
});
