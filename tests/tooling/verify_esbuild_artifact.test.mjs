import assert from 'node:assert/strict';
import childProcess from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { reviewedArtifact, verifyArtifactIdentity } from '../../scripts/verify_esbuild_artifact.mjs';

function fixture(t) {
  const directory = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'omerta-esbuild-test-')));
  t.after(() => fs.rmSync(directory, { recursive: true }));
  const binary = path.join(directory, 'fixture');
  const bytes = Buffer.from('\x7fELFunit-fixture-not-a-real-compiler');
  fs.writeFileSync(binary, bytes, { mode: 0o555 });
  const artifact = { ...reviewedArtifact, bytes: bytes.length,
    sha256: crypto.createHash('sha256').update(bytes).digest('hex') };
  return { directory, binary, artifact };
}

test('reviewed manifest binds the recorded candidate without security acceptance', () => {
  assert.equal(reviewedArtifact.api_version, '0.28.2');
  assert.equal(reviewedArtifact.sha256, '332c847f63affcb51c6ac278f4bc26f38cb11ce4c6a066464248afa52ce0f461');
  assert.equal(reviewedArtifact.security_accepted, false);
  assert.equal(reviewedArtifact.open_advisory, 'CVE-2026-39824');
});

test('identity does not imply security acceptance and uses a bounded version command', (t) => {
  const { binary, artifact } = fixture(t);
  const run = t.mock.method(childProcess, 'execFileSync', (command, argv, options) => {
    assert.equal(command, binary);
    assert.deepEqual(argv, ['--version']);
    assert.equal(options.timeout, 5000);
    assert.equal(options.env.ESBUILD_BINARY_PATH, undefined);
    return '0.28.2\n';
  });
  assert.equal(verifyArtifactIdentity(binary, artifact).security_accepted, false);
  assert.equal(run.mock.callCount(), 1);
});

for (const [name, change] of [
  ['wrong hash', (f) => { f.artifact.sha256 = '0'.repeat(64); }],
  ['wrong size', (f) => { f.artifact.bytes += 1; }],
  ['wrong platform', (f) => { f.artifact.platform = 'win32'; }],
  ['missing metadata evidence', (f) => { f.artifact.build_metadata_present = false; }],
  ['writable binary', (f) => { fs.chmodSync(f.binary, 0o755); }],
  ['untrusted parent', (f) => { fs.chmodSync(f.directory, 0o777); }],
  ['missing binary', (f) => { f.binary = path.join(f.directory, 'missing'); }],
  ['relative path', (f) => { f.binary = 'relative-fixture'; }],
  ['symlink path', (f) => { const link = path.join(f.directory, 'link'); fs.symlinkSync(f.binary, link); f.binary = link; }],
]) {
  test(`${name} fails before execution`, (t) => {
    const f = fixture(t);
    change(f);
    const run = t.mock.method(childProcess, 'execFileSync', () => { throw new Error('must not execute'); });
    assert.throws(() => verifyArtifactIdentity(f.binary, f.artifact));
    assert.equal(run.mock.callCount(), 0);
  });
}

test('a version mismatch or failed executable cannot silently succeed', (t) => {
  const { binary, artifact } = fixture(t);
  const run = t.mock.method(childProcess, 'execFileSync', () => '0.27.0\n');
  assert.throws(() => verifyArtifactIdentity(binary, artifact), /version mismatch/);
  run.mock.mockImplementation(() => { throw new Error('synthetic process failure'); });
  assert.throws(() => verifyArtifactIdentity(binary, artifact), /synthetic process failure/);
});

test('non-ELF bytes cannot be approved by their hash alone', (t) => {
  const { binary, artifact } = fixture(t);
  fs.chmodSync(binary, 0o755);
  fs.writeFileSync(binary, Buffer.alloc(artifact.bytes, 65));
  fs.chmodSync(binary, 0o555);
  artifact.sha256 = crypto.createHash('sha256').update(fs.readFileSync(binary)).digest('hex');
  const run = t.mock.method(childProcess, 'execFileSync', () => '0.28.2\n');
  assert.throws(() => verifyArtifactIdentity(binary, artifact), /ELF/);
  assert.equal(run.mock.callCount(), 0);
});

test('replacing the path during hashing fails before execution', (t) => {
  const { binary, artifact } = fixture(t);
  const read = fs.readSync;
  let replaced = false;
  t.mock.method(fs, 'readSync', (...args) => {
    const count = read(...args);
    if (!replaced) {
      replaced = true;
      fs.renameSync(binary, `${binary}.original`);
      fs.copyFileSync(`${binary}.original`, binary);
    }
    return count;
  });
  const run = t.mock.method(childProcess, 'execFileSync', () => '0.28.2\n');
  assert.throws(() => verifyArtifactIdentity(binary, artifact), /changed during verification/);
  assert.equal(run.mock.callCount(), 0);
});

test('CLI propagates invalid input as a nonzero exit without fallback', () => {
  for (const args of [[], ['relative-fixture'], ['/nonexistent/omerta-esbuild-fixture']]) {
    const result = childProcess.spawnSync(process.execPath,
      [new URL('../../scripts/verify_esbuild_artifact.mjs', import.meta.url).pathname, ...args],
      { encoding: 'utf8', timeout: 5000, env: { PATH: '/usr/bin:/bin' } });
    assert.equal(result.status, 1);
    assert.equal(result.stdout, '');
    assert.match(result.stderr, /identity verification failed; no fallback is permitted/);
  }
});
