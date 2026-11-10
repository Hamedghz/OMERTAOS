import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';
import { devKernelRequestSchema, formatValidationIssues, taskRequestSchema } from '../../gateway/src/types.js';

const require = createRequire(new URL('../../gateway/package.json', import.meta.url));
const Fastify = require('fastify');

describe('Gateway Zod request contracts', () => {
  it('keeps parser matcher and legacy linter brace APIs compatible', () => {
    const parserRequire = createRequire(require.resolve('@typescript-eslint/typescript-estree'));
    const { Minimatch } = parserRequire('minimatch');
    expect(new Minimatch('**/*.{ts,tsx}').match('src/types.ts')).toBe(true);
    const eslintRequire = createRequire(require.resolve('eslint'));
    expect(eslintRequire('minimatch')('src/types.ts', 'src/{types,server}.ts')).toBe(true);
  });

  it('preserves defaults and arbitrary JSON records', () => {
    expect(taskRequestSchema.parse({ intent: 'runtime.echo.v1' })).toEqual({
      schemaVersion: '1.0', intent: 'runtime.echo.v1', params: {},
      preferredEngine: 'auto', priority: 'normal',
    });
    const payload = {
      intent: 'runtime.echo.v1', params: { nested: { values: [1, null, true] } },
      metadata: { 'tenant-context': 'tenant-a', count: 2 },
    };
    expect(taskRequestSchema.parse(payload)).toMatchObject(payload);
    expect(devKernelRequestSchema.parse({ message: 'hello', metadata: payload.metadata }))
      .toEqual({ message: 'hello', metadata: payload.metadata });
  });

  it('keeps strict envelopes, record validation and finite positive SLA bounds', () => {
    for (const payload of [
      { intent: 'echo', unexpected: true }, { intent: '' },
      { intent: 'echo', params: null }, { intent: 'echo', metadata: [] },
      { intent: 'echo', sla: { budget_usd: Infinity } },
      { intent: 'echo', sla: { budget_usd: NaN } },
      { intent: 'echo', sla: { p95_ms: 0 } },
      { intent: 'echo', sla: { p95_ms: 1.5 } },
    ]) expect(taskRequestSchema.safeParse(payload).success).toBe(false);
    expect(devKernelRequestSchema.safeParse({ message: 'hello', extra: true }).success).toBe(false);
  });

  it('retains the published enum diagnostic code and nested field path', () => {
    const result = taskRequestSchema.safeParse({ intent: 'echo', sla: { privacy: 'invalid' } });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(formatValidationIssues(result.error)).toEqual([
        expect.objectContaining({ path: 'sla.privacy', code: 'invalid_enum_value' }),
      ]);
    }
  });

  it('does not allow record keys to pollute the object prototype', () => {
    const payload = JSON.parse('{"intent":"echo","params":{"__proto__":{"polluted":true}}}');
    const result = taskRequestSchema.safeParse(payload);
    if (result.success) expect(Object.hasOwn(result.data.params, '__proto__')).toBe(false);
    expect(({} as Record<string, unknown>).polluted).toBeUndefined();
  });
});

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
