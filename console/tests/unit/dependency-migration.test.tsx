import { createRequire } from 'node:module';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
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
