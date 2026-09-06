import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const require = createRequire(new URL('../../gateway/package.json', import.meta.url));
const Fastify = require('fastify');

describe('Gateway Fastify schema validation', () => {
  it('passes the validated primitive type to the handler', async () => {
    const app = Fastify();
    app.post('/bounded-number', {
      schema: { body: { type: 'integer', minimum: 1, maximum: 10 } },
    }, async (request: { body: unknown }) => ({
      value: request.body,
      type: typeof request.body,
    }));

    try {
      const response = await app.inject({
        method: 'POST', url: '/bounded-number',
        headers: { 'content-type': 'application/json' }, payload: '"10"',
      });
      expect(response.statusCode).toBe(200);
      expect(response.json()).toEqual({ value: 10, type: 'number' });

      const invalid = await app.inject({
        method: 'POST', url: '/bounded-number',
        headers: { 'content-type': 'application/json' }, payload: '"11"',
      });
      expect(invalid.statusCode).toBe(400);
    } finally {
      await app.close();
    }
  });
});
