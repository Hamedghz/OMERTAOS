import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('gateway configuration defaults', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv('AION_GATEWAY_PORT', '');
    vi.stubEnv('AION_CONSOLE_ORIGIN', '');
    vi.stubEnv('AION_CORS_ORIGINS', '');
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('matches the documented Gateway and Console ports', async () => {
    const { gatewayConfig } = await import('../../gateway/src/config.js');

    expect(gatewayConfig.port).toBe(8080);
    expect(gatewayConfig.corsOrigins).toEqual(['http://localhost:3000']);
  });
});
