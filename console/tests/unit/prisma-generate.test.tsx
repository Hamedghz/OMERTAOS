// @vitest-environment node

import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { runInNewContext } from 'node:vm';
import { describe, expect, it, vi } from 'vitest';

const require = createRequire(import.meta.url);
const wrapper = require.resolve('../../scripts/run-prisma-generate.cjs');

function runWrapper(status = 0, databaseUrl = 'postgresql://127.0.0.1:5432/validation') {
  const spawnSync = vi.fn(() => ({ status }));
  let exitCode: number | undefined;
  const stopped = new Error('wrapper stopped');
  const mockedRequire = Object.assign((name: string) => {
    if (name === 'dotenv/config') return {};
    if (name === 'node:path') return path;
    if (name === 'node:child_process') return { spawnSync };
    throw new Error(`Unexpected import: ${name}`);
  }, { resolve: () => '/fixture/prisma/build/index.js' });

  try {
    runInNewContext(readFileSync(wrapper, 'utf8'), {
      require: mockedRequire,
      __dirname: path.dirname(wrapper),
      console: { log: vi.fn(), warn: vi.fn(), error: vi.fn() },
      process: {
        env: { DATABASE_URL: databaseUrl },
        execPath: process.execPath,
        exit: (code: number) => { exitCode = code; throw stopped; },
      },
    });
  } catch (error) {
    if (error !== stopped) throw error;
  }
  return { spawnSync, exitCode };
}

describe('Prisma generation wrapper', () => {
  it('does not implicitly opt out of missing engine checksum verification', () => {
    const result = runWrapper();
    expect(result.exitCode).toBeUndefined();
    expect(result.spawnSync).toHaveBeenCalledWith(process.execPath, ['/fixture/prisma/build/index.js', 'generate'],
      expect.objectContaining({ env: { DATABASE_URL: 'postgresql://127.0.0.1:5432/validation' }, stdio: 'inherit' }));
  });

  it('propagates a failed Prisma command rather than reporting success', () => {
    const result = runWrapper(17);
    expect(result.exitCode).toBe(17);
    expect(result.spawnSync).toHaveBeenCalledTimes(1);
  });

  it('rejects non-PostgreSQL input before spawning Prisma', () => {
    const result = runWrapper(0, 'file:validation.db');
    expect(result.exitCode).toBe(1);
    expect(result.spawnSync).not.toHaveBeenCalled();
  });
});
