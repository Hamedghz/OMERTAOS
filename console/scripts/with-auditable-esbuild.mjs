import assert from 'node:assert/strict';
import childProcess from 'node:child_process';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { reviewedArtifact, verifyArtifactIdentity } from '../../scripts/verify_esbuild_artifact.mjs';

export function guardedEnvironment(environment = process.env, artifact = reviewedArtifact) {
  const binary = environment.OMERTA_ESBUILD_BINARY
    || path.join(environment.OMERTA_ESBUILD_CONTEXT || path.join(os.homedir(), '.local/share/omerta-tools/esbuild',
      `linux-x64-${reviewedArtifact.provider_version}`), 'esbuild');
  assert(!environment.ESBUILD_BINARY_PATH || environment.ESBUILD_BINARY_PATH === binary,
    'Conflicting esbuild binary configuration');
  verifyArtifactIdentity(binary, artifact);
  return { ...environment, ESBUILD_BINARY_PATH: binary };
}

export async function runGuarded(argv, environment = process.env, artifact = reviewedArtifact) {
  assert(argv.length > 0 && argv.every((arg) => typeof arg === 'string'), 'A command argv is required');
  const env = guardedEnvironment(environment, artifact);
  return new Promise((resolve) => {
    const child = childProcess.spawn(argv[0], argv.slice(1), { stdio: 'inherit', env, shell: false });
    const forward = (signal) => child.kill(signal);
    const handlers = new Map(['SIGINT', 'SIGTERM'].map((signal) => [signal, () => forward(signal)]));
    for (const [signal, handler] of handlers) process.on(signal, handler);
    let finished = false;
    const finish = (code) => {
      if (finished) return;
      finished = true;
      for (const [signal, handler] of handlers) process.removeListener(signal, handler);
      resolve(code);
    };
    child.once('error', () => finish(1));
    child.once('exit', (code, signal) => finish(code ?? (128 + (os.constants.signals[signal] || 1))));
  });
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    process.exitCode = await runGuarded(process.argv.slice(2));
  } catch {
    console.error('Console compiler preflight failed; refusing consumer execution or fallback');
    process.exitCode = 1;
  }
}
