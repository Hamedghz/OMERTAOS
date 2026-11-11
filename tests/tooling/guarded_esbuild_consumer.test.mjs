import assert from 'node:assert/strict';
import childProcess from 'node:child_process';
import crypto from 'node:crypto';
import { EventEmitter } from 'node:events';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { guardedEnvironment, runGuarded } from '../../console/scripts/with-auditable-esbuild.mjs';
import { reviewedArtifact } from '../../scripts/verify_esbuild_artifact.mjs';

function verifiedFixture(t) {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'omerta-guard-test-')));
  t.after(() => fs.rmSync(root, { recursive: true }));
  const binary = path.join(root, 'esbuild');
  const bytes = Buffer.from('\x7fELFsynthetic-consumer-fixture');
  fs.writeFileSync(binary, bytes, { mode: 0o555 });
  const artifact = { ...reviewedArtifact, bytes: bytes.length,
    sha256: crypto.createHash('sha256').update(bytes).digest('hex') };
  t.mock.method(childProcess, 'execFileSync', () => `${artifact.api_version}\n`);
  return { binary, artifact };
}

test('missing artifact refuses a consumer before spawning', async (t) => {
  const spawn = t.mock.method(childProcess, 'spawn', () => { throw new Error('must not execute'); });
  await assert.rejects(runGuarded(['node', '-e', 'process.exit(0)'], { OMERTA_ESBUILD_BINARY: '/nonexistent/esbuild' }));
  assert.equal(spawn.mock.callCount(), 0);
});

test('conflicting override refuses execution rather than using upstream fallback', (t) => {
  const execute = t.mock.method(childProcess, 'execFileSync', () => { throw new Error('must not execute'); });
  assert.throws(() => guardedEnvironment({ OMERTA_ESBUILD_BINARY: '/one', ESBUILD_BINARY_PATH: '/other' }), /Conflicting/);
  assert.equal(execute.mock.callCount(), 0);
});

test('verified environment sets only the chosen tool and preserves consumer configuration', (t) => {
  const { binary, artifact } = verifiedFixture(t);
  const env = guardedEnvironment({ OMERTA_ESBUILD_BINARY: binary, NODE_ENV: 'test' }, artifact);
  assert.equal(env.ESBUILD_BINARY_PATH, binary);
  assert.equal(env.NODE_ENV, 'test');
});

for (const [label, code, signal, expected] of [['nonzero exit', 7, null, 7], ['signal exit', null, 'SIGTERM', 143]]) {
  test(`${label} propagates without a false success`, async (t) => {
    const { binary, artifact } = verifiedFixture(t);
    const before = process.listenerCount('SIGTERM');
    t.mock.method(childProcess, 'spawn', (command, argv, options) => {
      assert.equal(command, 'consumer');
      assert.deepEqual(argv, ['argument with spaces']);
      assert.equal(options.shell, false);
      assert.equal(options.env.ESBUILD_BINARY_PATH, binary);
      const child = new EventEmitter();
      queueMicrotask(() => child.emit('exit', code, signal));
      return child;
    });
    assert.equal(await runGuarded(['consumer', 'argument with spaces'], { OMERTA_ESBUILD_BINARY: binary }, artifact), expected);
    assert.equal(process.listenerCount('SIGTERM'), before);
  });
}

test('spawn error is nonzero and removes signal handlers', async (t) => {
  const { binary, artifact } = verifiedFixture(t);
  const before = process.listenerCount('SIGINT');
  t.mock.method(childProcess, 'spawn', () => {
    const child = new EventEmitter();
    queueMicrotask(() => child.emit('error', new Error('synthetic spawn failure')));
    return child;
  });
  assert.equal(await runGuarded(['consumer'], { OMERTA_ESBUILD_BINARY: binary }, artifact), 1);
  assert.equal(process.listenerCount('SIGINT'), before);
});
