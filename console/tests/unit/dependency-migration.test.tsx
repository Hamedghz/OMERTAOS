// @vitest-environment node

import { createRequire } from 'node:module';
import { copyFileSync, mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { afterEach, describe, expect, it } from 'vitest';

const require = createRequire(import.meta.url);
const prismaRequire = createRequire(require.resolve('prisma/config'));
const configRequire = createRequire(prismaRequire.resolve('@prisma/config'));
const sucraseRequire = createRequire(createRequire(require.resolve('tailwindcss')).resolve('sucrase'));
const globRequire = createRequire(sucraseRequire.resolve('glob'));
const directories: string[] = [];

function fixtureDirectory() {
  const directory = mkdtempSync(path.join(tmpdir(), 'omerta-dependency-test-'));
  directories.push(directory);
  return directory;
}

afterEach(() => {
  for (const directory of directories.splice(0)) rmSync(directory, { recursive: true, force: true });
});

describe('major dependency consumer compatibility', () => {
  it.each(['mts', 'cts'])('executes a typed %s fixture through the real tsx CLI', (extension) => {
    const directory = fixtureDirectory();
    writeFileSync(path.join(directory, 'dependency.ts'), 'export const value: number = 42;');
    const file = path.join(directory, `main.${extension}`);
    writeFileSync(file, extension === 'mts'
      ? "import { value } from './dependency.ts'; const result: number = await Promise.resolve(value); console.log(result);"
      : "const { value } = require('./dependency.ts'); const result: number = value; console.log(result);");
    expect(execFileSync(process.execPath, [require.resolve('tsx/cli'), file], {
      cwd: directory, encoding: 'utf8', timeout: 15000,
    }).trim()).toBe('42');
  });

  it('anchors Next tracing to the checkout despite external lockfiles and another cwd', () => {
    const directory = fixtureDirectory();
    const repository = path.join(directory, 'checkout');
    const consoleDirectory = path.join(repository, 'console');
    mkdirSync(consoleDirectory, { recursive: true });
    writeFileSync(path.join(directory, 'package-lock.json'), '{}');
    writeFileSync(path.join(consoleDirectory, 'pnpm-lock.yaml'), 'lockfileVersion: 9.0\n');
    const configPath = path.join(consoleDirectory, 'next.config.mjs');
    copyFileSync(require.resolve('../../next.config.mjs'), configPath);
    const script = `
      import { createRequire } from 'node:module';
      import config from ${JSON.stringify(pathToFileURL(configPath).href)};
      const require = createRequire(${JSON.stringify(require.resolve('next/package.json'))});
      const load = require('next/dist/server/config').default;
      const { PHASE_PRODUCTION_BUILD } = require('next/constants');
      const normalized = await load(PHASE_PRODUCTION_BUILD, ${JSON.stringify(consoleDirectory)}, {
        customConfig: config, silent: false,
      });
      console.log(JSON.stringify({
        root: normalized.outputFileTracingRoot,
        transpilePackages: normalized.transpilePackages,
        strict: normalized.reactStrictMode,
        headers: await normalized.headers(),
        fallback: normalized.webpack({ resolve: { fallback: { existing: true } } }).resolve.fallback,
      }));
    `;
    const result = JSON.parse(execFileSync(process.execPath, ['--input-type=module', '-e', script], {
      cwd: directory, encoding: 'utf8', timeout: 15000,
    }));
    expect(result.root).toBe(repository);
    expect(result.transpilePackages).toContain('@aion/ui-core');
    expect(result.strict).toBe(true);
    expect(result.headers).toContainEqual({ source: '/:path*', headers: [
      { key: 'Strict-Transport-Security', value: 'max-age=63072000; includeSubDomains; preload' },
    ] });
    expect(result.fallback).toEqual({ existing: true, fs: false });
  });

  it('loads a Prisma config using its real DeepmergeTS dependency', async () => {
    const directory = fixtureDirectory();
    writeFileSync(path.join(directory, 'prisma.config.mjs'), `export default {
      schema: 'schema.prisma', engine: 'classic', migrations: { path: 'migrations' },
      datasource: { url: 'postgresql://127.0.0.1:5432/omerta_validation' }
    };`);
    const { loadConfigFromFile } = prismaRequire('@prisma/config');
    const result = await loadConfigFromFile({ configRoot: directory });
    expect(result.error).toBeUndefined();
    expect(result.config.schema).toBe(path.join(directory, 'schema.prisma'));
    expect(result.config.migrations.path).toBe(path.join(directory, 'migrations'));
  });

  it('retains nested config merging without mutating inputs or polluting prototypes', () => {
    const { deepmerge } = configRequire('deepmerge-ts');
    const first = { migrations: { path: 'migrations' }, flags: ['one'] };
    const second = { migrations: { seed: 'seed-command' }, flags: ['two'] };
    expect(deepmerge(first, second)).toEqual({
      migrations: { path: 'migrations', seed: 'seed-command' }, flags: ['one', 'two'],
    });
    expect(first).toEqual({ migrations: { path: 'migrations' }, flags: ['one'] });
    deepmerge({}, JSON.parse('{"__proto__":{"polluted":true}}'));
    expect(({} as Record<string, unknown>).polluted).toBeUndefined();
  });

  it('keeps Sucrase glob discovery and modern named matcher APIs', async () => {
    const directory = fixtureDirectory();
    mkdirSync(path.join(directory, 'nested'));
    writeFileSync(path.join(directory, 'included.ts'), 'export {};');
    writeFileSync(path.join(directory, 'nested/excluded.ts'), 'export {};');
    const { glob } = sucraseRequire('glob');
    expect(await glob('**/*.ts', { cwd: directory, ignore: ['**/excluded.ts'] })).toEqual(['included.ts']);
    expect(await glob('{included,other}.ts', { cwd: directory })).toEqual(['included.ts']);
    const { Minimatch } = globRequire('minimatch');
    expect(new Minimatch('**/*.{ts,tsx}').match('src/example.ts')).toBe(true);
    expect(new Minimatch('**/*.ts').match('src/example.js')).toBe(false);
  });

  it('preserves the callable legacy matcher used by ESLint 8', () => {
    const eslintRequire = createRequire(require.resolve('eslint'));
    const minimatch = eslintRequire('minimatch');
    expect(typeof minimatch).toBe('function');
    expect(minimatch('src/example.ts', 'src/{example,other}.ts')).toBe(true);
  });
});
