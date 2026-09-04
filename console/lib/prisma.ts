import { getDatabaseDiagnostics, requirePostgresUrl } from './databaseInfo';
import { resolveEnvironment } from './environment';

type PrismaClientCtor = new (options?: { log?: string[] }) => PrismaClientLike;
type PrismaClientLike = {
  $disconnect: () => Promise<void>;
  $queryRaw: (...args: unknown[]) => Promise<any>;
  [key: string]: any;
};

let prismaModule: { PrismaClient?: PrismaClientCtor } = {};
try {
  prismaModule = require('@prisma/client') as { PrismaClient?: PrismaClientCtor };
} catch (error) {
  // eslint-disable-next-line no-console
  console.warn('[console] Prisma package not fully generated; running with database client disabled.', error);
}

const PrismaClient = prismaModule.PrismaClient;

const dockerSetting = resolveEnvironment('OMERTA_DOCKER', {
  aliases: ['AION_DOCKER'],
});
const isDockerEnv = dockerSetting === '1' || process.env.DOCKER === 'true';
const isProdEnv = process.env.NODE_ENV === 'production';
const isNextBuild =
  process.env.NEXT_PHASE === 'phase-production-build' ||
  process.env.npm_lifecycle_event === 'build';
const enforceDatabaseUrl = (isDockerEnv || isProdEnv) && !isNextBuild;

const databaseUrl = process.env.DATABASE_URL;
requirePostgresUrl(databaseUrl, enforceDatabaseUrl);

const databaseDiagnostics = getDatabaseDiagnostics(databaseUrl, enforceDatabaseUrl);
// eslint-disable-next-line no-console
console.info(
  `[console] Database provider: ${databaseDiagnostics.provider}; URL: ${databaseDiagnostics.redactedUrl}`,
);

type GlobalWithPrisma = typeof globalThis & {
  prisma?: PrismaClientLike | null;
};

const prismaEnabledEnv = resolveEnvironment('OMERTA_ENABLE_PRISMA', {
  aliases: ['AION_ENABLE_PRISMA'],
});
const prismaEnabled =
  prismaEnabledEnv === undefined ||
  prismaEnabledEnv === '1' ||
  prismaEnabledEnv.toLowerCase?.() === 'true';

const createPrismaClient = (): PrismaClientLike | null => {
  if (!prismaEnabled || !PrismaClient) {
    return null;
  }

  try {
    return new PrismaClient({
      log: ['warn', 'error'],
    });
  } catch (error) {
    // eslint-disable-next-line no-console
    console.warn('[console] Prisma client unavailable; skipping database client init.', error);
    return null;
  }
};

const globalForPrisma = globalThis as GlobalWithPrisma;
const prismaInstance = globalForPrisma.prisma ?? createPrismaClient();

export const prisma: PrismaClientLike =
  prismaInstance ??
  (new Proxy(
    {},
    {
      get: (_target, prop: string) => {
        if (prop === '$disconnect') {
          return async () => undefined;
        }
        return () => Promise.reject(new Error('Prisma client is disabled'));
      },
    },
  ) as PrismaClientLike);

if (process.env.NODE_ENV !== 'production' && prismaInstance) {
  globalForPrisma.prisma = prismaInstance;
}
