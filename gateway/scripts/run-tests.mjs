import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const gatewayDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const repoRoot = path.resolve(gatewayDir, '..');
const vitestEntry = path.join(gatewayDir, 'node_modules', 'vitest', 'vitest.mjs');

const result = spawnSync(process.execPath, [vitestEntry, 'run', 'tests/gateway'], {
  cwd: repoRoot,
  env: {
    ...process.env,
    OMERTA_ENV: process.env.OMERTA_ENV || 'development',
    OMERTA_GATEWAY_ADMIN_TOKEN:
      process.env.OMERTA_GATEWAY_ADMIN_TOKEN ||
      'test-admin-token',
    OMERTA_GATEWAY_API_KEYS:
      process.env.OMERTA_GATEWAY_API_KEYS ||
      'test-api-key:admin',
    OMERTA_CONTROL_BASE_URL:
      process.env.OMERTA_CONTROL_BASE_URL ||
      'http://127.0.0.1:8000',
  },
  stdio: 'inherit',
});

if (result.error) {
  throw result.error;
}

process.exit(result.status ?? 1);
