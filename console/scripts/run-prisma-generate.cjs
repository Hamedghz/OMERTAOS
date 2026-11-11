#!/usr/bin/env node
require('dotenv/config');
const { spawnSync } = require('node:child_process');
const path = require('node:path');

if (process.env.SKIP_PRISMA_GENERATE === 'true') {
  console.log('Skipping Prisma generate because SKIP_PRISMA_GENERATE=true');
  process.exit(0);
}

const env = { ...process.env };
const fallbackDatabaseUrl =
  'postgresql://aion:aion@127.0.0.1:5432/aion?schema=public';

if (!env.DATABASE_URL) {
  env.DATABASE_URL = fallbackDatabaseUrl;
  console.warn(
    '[prisma:generate] DATABASE_URL was not provided. Using a local placeholder so CI builds remain reproducible.',
  );
}

if (!/^postgres(ql)?:\/\//i.test(env.DATABASE_URL)) {
  console.error('DATABASE_URL must be a Postgres connection string.');
  process.exit(1);
}

const prismaCli = require.resolve('prisma/build/index.js');
const result = spawnSync(process.execPath, [prismaCli, 'generate'], {
  stdio: 'inherit',
  env,
  cwd: path.resolve(__dirname, '..'),
});

if (result.status !== 0) {
  process.exit(result.status ?? 1);
}
