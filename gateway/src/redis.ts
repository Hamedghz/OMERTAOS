import dns from 'node:dns/promises';
import { Redis } from 'ioredis';
import { gatewayConfig } from './config.js';
import { resolveEnvironment } from './config/environment.js';

const redisHostFromEnv = resolveEnvironment('OMERTA_REDIS_HOST', {
  aliases: ['AION_REDIS_HOST'],
  defaultValue: 'redis',
}) as string;

const normalizeRedisUrl = (rawUrl: string) => {
  try {
    const parsed = new URL(rawUrl);
    if (['localhost', '127.0.0.1'].includes(parsed.hostname)) {
      parsed.hostname = redisHostFromEnv;
    }
    if (!parsed.port) {
      parsed.port = '6379';
    }
    return parsed.toString();
  } catch {
    return `redis://${redisHostFromEnv}:6379/0`;
  }
};

let lastRedisErrorLoggedAt = 0;
const REDIS_ERROR_DEBOUNCE_MS = 5000;

const resolveRedisHost = async () => {
  try {
    const parsedUrl = new URL(redisUrl);
    const host = parsedUrl.hostname || redisHostFromEnv;
    const records = await dns.lookup(host, { all: true });
    const addresses = records.map((record) => record.address).join(', ');
    // eslint-disable-next-line no-console
    console.info(`[redis] resolved host ${host} -> ${addresses || 'no-records'}`);
  } catch (error) {
    // eslint-disable-next-line no-console
    console.warn('[redis] host resolution failed', (error as Error).message);
  }
};

const redisUrl = normalizeRedisUrl(gatewayConfig.redisUrl);

resolveRedisHost();

export const redis = new Redis(redisUrl, {
  enableAutoPipelining: true,
  maxRetriesPerRequest: 5,
  lazyConnect: gatewayConfig.environment === 'test',
  reconnectOnError: (error) => {
    if (/EAI_AGAIN|ENOTFOUND|ECONNREFUSED/.test(error.message)) {
      return true;
    }
    return false;
  },
  retryStrategy: (times) => {
    if (gatewayConfig.environment === 'test') {
      return null;
    }
    const capped = Math.min(times, 6);
    const base = Math.min(250 * 2 ** capped, 10_000);
    const jitter = Math.floor(Math.random() * 200);
    return base + jitter;
  },
});

redis.on('error', (error) => {
  const now = Date.now();
  if (gatewayConfig.environment === 'test' && process.env.VITEST) {
    return;
  }
  if (now - lastRedisErrorLoggedAt > REDIS_ERROR_DEBOUNCE_MS) {
    // eslint-disable-next-line no-console
    console.warn('[redis] connection error', error.message);
    lastRedisErrorLoggedAt = now;
  }
});

redis.on('ready', () => {
  // eslint-disable-next-line no-console
  console.info('[redis] client ready');
});

const idemKey = (key: string, tenantId?: string) =>
  tenantId ? `idem:${tenantId}:${key}` : `idem:${key}`;

const rateKey = (prefix: string, identifier: string, tenantId?: string) =>
  tenantId ? `${prefix}:${tenantId}:${identifier}` : `${prefix}:${identifier}`;

const handleRedisErrors = async <T>(op: () => Promise<T>, fallback: T): Promise<T> => {
  try {
    return await op();
  } catch (error) {
    const now = Date.now();
    if (now - lastRedisErrorLoggedAt > REDIS_ERROR_DEBOUNCE_MS) {
      // eslint-disable-next-line no-console
      console.warn('[redis] operation failed', (error as Error).message);
      lastRedisErrorLoggedAt = now;
    }
    return fallback;
  }
};

export const cacheIdempotency = async (key: string, payload: string, ttlSeconds: number, tenantId?: string) => {
  await handleRedisErrors(() => redis.set(idemKey(key, tenantId), payload, 'EX', ttlSeconds), null);
};

export const getIdempotency = async (key: string, tenantId?: string): Promise<string | null> => {
  return handleRedisErrors(() => redis.get(idemKey(key, tenantId)), null);
};

export const withRateLimitCounter = async (
  identifier: string,
  windowMs: number,
  limit: number,
  tenantId?: string,
  prefix = 'rl'
) => {
  const bucket = rateKey(prefix, identifier, tenantId);
  const windowKey = `${bucket}:${Math.floor(Date.now() / windowMs)}`;
  const ttl = Math.ceil(windowMs / 1000);
  const execResult = await handleRedisErrors(
    () => redis.multi().incr(windowKey).expire(windowKey, ttl).exec(),
    null,
  );

  if (!execResult) {
    return { requests: 0, remaining: limit };
  }

  const [incrResult, expireResult] = execResult;
  const [incrError, count] = incrResult;
  if (incrError) {
    throw incrError;
  }

  const [expireError] = expireResult;
  if (expireError) {
    throw expireError;
  }

  const requests = Number(count ?? 0);
  const remaining = Math.max(limit - requests, 0);
  return { requests, remaining };
};

export const closeRedis = async () => {
  await redis.quit();
};

