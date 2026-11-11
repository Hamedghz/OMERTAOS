import assert from 'node:assert/strict';
import childProcess from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { archivePin, stageContext, stageWorkspaceArchive } from '../../scripts/stage_esbuild_context.mjs';
import { reviewedArtifact } from '../../scripts/verify_esbuild_artifact.mjs';

function fixture(t) {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'omerta-context-test-')));
  t.after(() => fs.rmSync(root, { recursive: true }));
  const binary = path.join(root, 'esbuild');
  const bytes = Buffer.from('\x7fELFcontext-unit-fixture');
  fs.writeFileSync(binary, bytes, { mode: 0o555 });
  const artifact = { ...reviewedArtifact, bytes: bytes.length,
    sha256: crypto.createHash('sha256').update(bytes).digest('hex') };
  const archive = path.join(root, 'provider.tgz');
  const data = Buffer.from('synthetic archive identity fixture');
  fs.writeFileSync(archive, data);
  const pin = { ...archivePin, bytes: data.length, binary_sha256: artifact.sha256,
    sha256: crypto.createHash('sha256').update(data).digest('hex'),
    integrity: 'sha512-' + crypto.createHash('sha512').update(data).digest('base64') };
  t.mock.method(childProcess, 'execFileSync', () => `${artifact.api_version}\n`);
  return { binary, archive, artifact, pin, output: path.join(root, 'context') };
}

test('context contains only the pinned public inputs and is not security acceptance', (t) => {
  const input = fixture(t);
  const result = stageContext(input);
  assert.deepEqual(result.files, ['esbuild', input.pin.filename, 'provenance.json'].sort());
  assert.equal(result.security_accepted, false);
  assert.equal(fs.statSync(path.join(input.output, 'esbuild')).mode & 0o777, 0o555);
});

for (const [name, change] of [
  ['archive SHA mismatch', (f) => { f.pin.sha256 = '0'.repeat(64); }],
  ['archive SRI mismatch', (f) => { f.pin.integrity = 'sha512-wrong'; }],
  ['archive wrong size', (f) => { f.pin.bytes += 1; }],
  ['binary/archive mismatch', (f) => { f.pin.binary_sha256 = '0'.repeat(64); }],
  ['relative output', (f) => { f.output = 'relative-context'; }],
]) {
  test(`${name} cannot create a context`, (t) => {
    const input = fixture(t);
    change(input);
    assert.throws(() => stageContext(input));
    assert.equal(fs.existsSync(input.output), false);
  });
}

test('existing context is never overwritten', (t) => {
  const input = fixture(t);
  fs.mkdirSync(input.output);
  fs.writeFileSync(path.join(input.output, 'retained'), 'retained');
  assert.throws(() => stageContext(input), /never overwritten/);
  assert.equal(fs.readFileSync(path.join(input.output, 'retained'), 'utf8'), 'retained');
});

test('a shared workspace receives only archive data, not the executable', (t) => {
  const input = fixture(t);
  stageContext(input);
  const workspace = path.join(path.dirname(input.output), 'shared-workspace');
  fs.mkdirSync(workspace, { mode: 0o775 });
  const options = { context: input.output, workspace, artifact: input.artifact, pin: input.pin };
  stageWorkspaceArchive(options);
  assert.deepEqual(fs.readdirSync(path.join(workspace, 'artifacts/tooling/esbuild')), [input.pin.filename]);
  stageWorkspaceArchive(options);
  fs.chmodSync(path.join(workspace, 'artifacts/tooling/esbuild', input.pin.filename), 0o644);
  fs.writeFileSync(path.join(workspace, 'artifacts/tooling/esbuild', input.pin.filename), 'existing changed archive');
  assert.throws(() => stageWorkspaceArchive(options));
});

test('group-writable executable ancestry is rejected, not chmodded', (t) => {
  const input = fixture(t);
  fs.chmodSync(path.dirname(input.output), 0o775);
  assert.throws(() => stageContext(input), /not trusted/);
  assert.equal(fs.existsSync(input.output), false);
  assert.equal(fs.statSync(path.dirname(input.output)).mode & 0o777, 0o775);
});

test('workspace symlink is rejected before writing outside the workspace', (t) => {
  const input = fixture(t);
  stageContext(input);
  const root = path.dirname(input.output);
  const workspace = path.join(root, 'workspace');
  const outside = path.join(root, 'outside');
  fs.mkdirSync(workspace);
  fs.mkdirSync(outside);
  fs.symlinkSync(outside, path.join(workspace, 'artifacts'));
  assert.throws(() => stageWorkspaceArchive({ context: input.output, workspace,
    artifact: input.artifact, pin: input.pin }), /Symlink/);
  assert.deepEqual(fs.readdirSync(outside), []);
});
