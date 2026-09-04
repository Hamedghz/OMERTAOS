import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { config } from 'dotenv';

import {
  choiceParser,
  integerParser,
  resolveEnvironment,
} from './config/environment.js';

type SecretPayload = Record<string, unknown> | string;

interface SecretProvider {
  getSecret(path: string): Promise<SecretPayload>;
}

type SecretProviderConstructor = new (options?: Record<string, unknown>) => SecretProvider;

type SecretProviderErrorConstructor = new (message?: string) => Error;

const secretProviderModuleUrl = 'file:///shared/secret-provider-node/index.js';

let SecretProviderError: SecretProviderErrorConstructor = class SecretProviderError
  extends Error {
  constructor(message?: string) {
    super(message);
    this.name = 'SecretProviderError';
  }
};

const inferredEnvFiles = new Set<string>();
const explicitEnv = process.env.ENV_FILE;
if (explicitEnv) {
  inferredEnvFiles.add(path.resolve(explicitEnv));
}

inferredEnvFiles.add(path.resolve(process.cwd(), '.env'));
inferredEnvFiles.add(path.resolve(process.cwd(), '..', '.env'));

const moduleDir = path.dirname(fileURLToPath(import.meta.url));
inferredEnvFiles.add(path.resolve(moduleDir, '..', '.env'));
inferredEnvFiles.add(path.resolve(moduleDir, '..', '..', '.env'));

for (const envFile of inferredEnvFiles) {
  if (fs.existsSync(envFile)) {
    config({ path: envFile, override: false });
  }
}

type GatewayEnvironment = 'development' | 'test' | 'production';

export interface GatewayConfig {
  port: number;
  host: string;
  controlGrpcEndpoint: string;
  controlBaseUrl: string;
  redisUrl: string;
  selfEvolving: {
    enabled: boolean;
    modelRegistryUrl: string;
    memoryUrl: string;
    defaultChannel: string;
  };
  apiKeys: Record<string, { roles: string[]; tenant?: string }>;
  jwtPublicKey: string | undefined;
  corsOrigins: string[];
  corsAllowCredentials: boolean;
  rateLimit: {
    max: number;
    timeWindow: string;
    perIp: number;
  };
  idempotencyTtlSeconds: number;
  environment: GatewayEnvironment;
  tls: {
    requireMtls: boolean;
    requireTls: boolean;
    secretPath?: string;
    clientCaSecretPath?: string;
    certPem?: string;
    keyPem?: string;
    caPem?: string[];
  };
  telemetry: {
    enabled: boolean;
    serviceName: string;
  };
  profile: 'user' | 'professional' | 'enterprise-vip';
  featureSeal: boolean;
  adminToken: string;
  devKernel: {
    enabled: boolean;
    url: string;
    profile: string;
  };
}

const parseApiKeysString = (raw?: string): Record<string, { roles: string[]; tenant?: string }> => {
  if (!raw) {
    return {};
  }
  const entries = raw.split(',').map((pair) => pair.trim()).filter(Boolean);
  const mapped: Record<string, { roles: string[]; tenant?: string }> = {};
  for (const entry of entries) {
    const [key, rolePart, tenant] = entry.split(':');
    if (key && rolePart) {
      mapped[key] = { roles: rolePart.split('|'), tenant: tenant || undefined };
    }
  }
  return mapped;
};

const parseApiKeysSecret = (secret: Record<string, unknown> | string): Record<string, { roles: string[]; tenant?: string }> => {
  if (typeof secret === 'string') {
    return parseApiKeysString(secret);
  }
  if (typeof secret.value === 'string') {
    return parseApiKeysString(secret.value);
  }
  const keys: Record<string, { roles: string[]; tenant?: string }> = {};
  const payload = secret.keys && typeof secret.keys === 'object' ? secret.keys : secret;
  for (const [apiKey, value] of Object.entries(payload)) {
    if (apiKey === 'value') {
      continue;
    }
    if (typeof value === 'string') {
      keys[apiKey] = { roles: value.split(',').map((role) => role.trim()).filter(Boolean) };
      continue;
    }
    if (value && typeof value === 'object' && 'roles' in value) {
      const rolesValue = (value as { roles: unknown }).roles;
      let roles: string[] = [];
      if (Array.isArray(rolesValue)) {
        roles = rolesValue.map((role) => String(role));
      } else if (typeof rolesValue === 'string') {
        roles = rolesValue.split(/[,|]/).map((role) => role.trim()).filter(Boolean);
      }
      const tenantValue = (value as { tenant?: unknown }).tenant;
      keys[apiKey] = {
        roles,
        tenant: typeof tenantValue === 'string' && tenantValue ? tenantValue : undefined,
      };
    }
  }
  return keys;
};

const profile = resolveEnvironment<GatewayConfig['profile']>('OMERTA_GATEWAY_PROFILE', {
  aliases: ['AION_PROFILE'],
  defaultValue: 'user',
  parse: choiceParser(['user', 'professional', 'enterprise-vip'] as const),
}) as GatewayConfig['profile'];
const featureSeal = process.env.FEATURE_SEAL === '1' || profile === 'enterprise-vip';

const defaultConsoleOrigin = resolveEnvironment('OMERTA_CONSOLE_ORIGIN', {
  aliases: ['AION_CONSOLE_ORIGIN'],
  defaultValue: 'http://localhost:3000',
}) as string;

const parseCorsOrigins = (raw: string | undefined): string[] => {
  if (!raw) {
    return [];
  }
  const trimmed = raw.trim();
  if (trimmed === '*') {
    return ['*'];
  }
  if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
    try {
      const parsed = JSON.parse(trimmed);
      if (Array.isArray(parsed)) {
        return parsed.map((item) => String(item).trim()).filter(Boolean);
      }
    } catch (error) {
      throw new Error(`Invalid JSON list for OMERTA_CORS_ORIGINS: ${(error as Error).message}`);
    }
  }
  return trimmed
    .split(',')
    .map((origin) => origin.trim())
    .filter(Boolean);
};

const normaliseCorsOrigins = (origins: string[]): string[] => {
  return Array.from(new Set(origins));
};

const normalizeBoolean = (value: string | undefined): boolean => {
  if (!value) {
    return false;
  }
  const normalised = value.trim().toLowerCase();
  return normalised === '1' || normalised === 'true' || normalised === 'yes' || normalised === 'on';
};

const resolveCorsConfiguration = (
  rawOrigins: string | undefined,
  environment: GatewayEnvironment,
): { origins: string[]; allowCredentials: boolean } => {
  const parsedOrigins = parseCorsOrigins(rawOrigins);
  const origins = parsedOrigins.length > 0 ? normaliseCorsOrigins(parsedOrigins) : [defaultConsoleOrigin];

  if (origins.includes('*')) {
    if (origins.length > 1) {
      throw new Error(
        'Wildcard CORS origin (*) cannot be combined with explicit origins. Remove the wildcard or list specific origins.',
      );
    }
    if (environment === 'production') {
      throw new Error(
        'Wildcard CORS origins (*) are not permitted in production. Set explicit origins via OMERTA_CORS_ORIGINS.',
      );
    }
    return { origins: ['*'], allowCredentials: false };
  }

  return { origins, allowCredentials: origins.length > 0 };
};

const normaliseSecretProviderMode = (raw: string | undefined): string => {
  return (raw || 'local').trim().toLowerCase();
};

const secretProviderMode = normaliseSecretProviderMode(process.env.SECRET_PROVIDER_MODE);

const vaultEnabledRaw = resolveEnvironment('VAULT_ENABLED', {
  aliases: ['AION_VAULT_ENABLED'],
});
const vaultAddress = resolveEnvironment('VAULT_ADDR', {
  aliases: ['AION_VAULT_ADDR'],
});
const vaultEnabled =
  vaultEnabledRaw !== undefined
    ? normalizeBoolean(vaultEnabledRaw)
    : Boolean(vaultAddress);

const isModuleNotFoundError = (error: unknown): boolean => {
  return (
    typeof error === 'object' &&
    error !== null &&
    'code' in error &&
    typeof (error as { code?: unknown }).code === 'string' &&
    (error as { code?: string }).code === 'ERR_MODULE_NOT_FOUND'
  );
};

const normaliseEnvSecretKey = (path: string): string => {
  const trimmed = String(path ?? '').trim();
  if (trimmed.startsWith('env://')) {
    return trimmed.slice('env://'.length);
  }
  if (trimmed.startsWith('env:')) {
    return trimmed.slice('env:'.length);
  }
  return trimmed;
};

class EnvSecretProvider implements SecretProvider {
  async getSecret(path: string): Promise<SecretPayload> {
    const key = normaliseEnvSecretKey(path);
    if (!key) {
      throw new SecretProviderError('Env secret key may not be empty');
    }
    const value = process.env[key];
    if (value === undefined) {
      throw new SecretProviderError(
        `Env secret '${key}' is not defined in process.env`,
      );
    }
    return value;
  }
}

const loadExternalSecretProvider = async (): Promise<SecretProvider | null> => {
  let providerModule: Record<string, unknown>;
  try {
    providerModule = await import(secretProviderModuleUrl);
  } catch (error) {
    if (isModuleNotFoundError(error)) {
      console.warn(
        `External secret provider module '${secretProviderModuleUrl}' not found; falling back to environment secrets.`,
      );
      return null;
    }
    const message = error instanceof Error ? error.message : String(error);
    console.warn(
      `Failed to load external secret provider module '${secretProviderModuleUrl}': ${message}`,
    );
    return null;
  }

  let ProviderCtor: SecretProviderConstructor | undefined;
  if (typeof providerModule.SecretProvider === 'function') {
    ProviderCtor = providerModule.SecretProvider as SecretProviderConstructor;
  } else if (
    providerModule.default &&
    typeof (providerModule.default as { SecretProvider?: unknown }).SecretProvider === 'function'
  ) {
    ProviderCtor = (providerModule.default as { SecretProvider: SecretProviderConstructor })
      .SecretProvider;
  } else if (typeof providerModule.default === 'function') {
    ProviderCtor = providerModule.default as SecretProviderConstructor;
  }

  if (typeof providerModule.SecretProviderError === 'function') {
    SecretProviderError = providerModule.SecretProviderError as SecretProviderErrorConstructor;
  }

  if (!ProviderCtor) {
    console.warn(
      `External secret provider module '${secretProviderModuleUrl}' does not export a SecretProvider constructor; falling back to environment secrets.`,
    );
    return null;
  }

  try {
    return new ProviderCtor({});
  } catch (error) {
    throw error;
  }
};

let secretProviderPromise: Promise<SecretProvider | null> | null = null;

const resolveSecretProvider = async (): Promise<SecretProvider | null> => {
  if (!vaultEnabled) {
    return null;
  }

  let provider: SecretProvider | null = null;

  if (secretProviderMode === 'external') {
    provider = await loadExternalSecretProvider();
    if (!provider) {
      console.warn(
        'Falling back to environment secret provider because the external provider was unavailable.',
      );
    }
  } else {
    console.info(
      'Using the configured environment-based secret provider',
    );
  }

  if (!provider) {
    provider = new EnvSecretProvider();
  }

  return provider;
};

const getSecretProvider = async (): Promise<SecretProvider | null> => {
  if (!secretProviderPromise) {
    secretProviderPromise = resolveSecretProvider();
  }
  return secretProviderPromise;
};

if (vaultEnabled) {
  try {
    await getSecretProvider();
  } catch (error) {
    if (error instanceof SecretProviderError) {
      throw error;
    }
    throw new Error(`Failed to initialise secret provider: ${String(error)}`);
  }
}

const requireSecretProvider = async (settingName: string): Promise<SecretProvider> => {
  const provider = await getSecretProvider();
  if (!provider) {
    throw new SecretProviderError(
      `Secret provider is not configured for ${settingName}`,
    );
  }
  return provider;
};

const resolveJwtPublicKey = async (): Promise<string | undefined> => {
  const secretPath = resolveEnvironment('OMERTA_JWT_SECRET_PATH', {
    aliases: ['AION_JWT_SECRET_PATH'],
  });
  if (!secretPath) {
    return resolveEnvironment('OMERTA_JWT_PUBLIC_KEY', {
      aliases: ['AION_JWT_PUBLIC_KEY'],
    });
  }
  const provider = await requireSecretProvider('OMERTA_JWT_SECRET_PATH');
  const payload = await provider.getSecret(secretPath);
  if (typeof payload === 'string') {
    return payload;
  }
  if (typeof payload.public_key === 'string') {
    return payload.public_key;
  }
  if (typeof payload.jwt === 'string') {
    return payload.jwt;
  }
  return undefined;
};

const ADMIN_TOKEN_ENV = 'OMERTA_GATEWAY_ADMIN_TOKEN';
const ADMIN_TOKEN_SECRET_PATH_ENV = 'OMERTA_GATEWAY_ADMIN_TOKEN_SECRET_PATH';

const takeFirstEnvValue = (keys: string[]): string | undefined => {
  for (const key of keys) {
    const value = process.env[key];
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }
  return undefined;
};

const takeAdminTokenFromPayload = (payload: SecretPayload): string | undefined => {
  if (typeof payload === 'string') {
    return payload.trim() || undefined;
  }
  if (typeof payload.token === 'string' && payload.token.trim()) {
    return payload.token.trim();
  }
  if (typeof payload.value === 'string' && payload.value.trim()) {
    return payload.value.trim();
  }
  if (typeof payload.admin_token === 'string' && payload.admin_token.trim()) {
    return payload.admin_token.trim();
  }
  return undefined;
};

const resolveAdminToken = async (): Promise<string> => {
  const productToken = resolveEnvironment(ADMIN_TOKEN_ENV, {
    aliases: ['AION_GATEWAY_ADMIN_TOKEN', 'AION_ADMIN_TOKEN'],
  });
  const envToken =
    (typeof productToken === 'string' && productToken.trim()) ||
    takeFirstEnvValue(['AUTH_TOKEN']);
  if (envToken) {
    return envToken;
  }

  const productSecretPath = resolveEnvironment(ADMIN_TOKEN_SECRET_PATH_ENV, {
    aliases: [
      'AION_GATEWAY_ADMIN_TOKEN_SECRET_PATH',
      'AION_ADMIN_TOKEN_SECRET_PATH',
    ],
  });
  const secretPath =
    typeof productSecretPath === 'string' ? productSecretPath.trim() : '';
  if (!secretPath) {
    throw new SecretProviderError(
      `Admin token is not configured. Set ${ADMIN_TOKEN_ENV} or provide ${ADMIN_TOKEN_SECRET_PATH_ENV}.`,
    );
  }

  const provider = await getSecretProvider();
  if (!provider) {
    throw new SecretProviderError(
      `Secret provider is not configured for ${ADMIN_TOKEN_SECRET_PATH_ENV}; set ${ADMIN_TOKEN_ENV} or configure a provider.`,
    );
  }

  const payload = await provider.getSecret(secretPath);
  const token = takeAdminTokenFromPayload(payload);
  if (token) {
    return token;
  }

  throw new SecretProviderError(
    `Secret referenced by ${ADMIN_TOKEN_SECRET_PATH_ENV} does not contain an admin token; populate 'token', 'value', or set ${ADMIN_TOKEN_ENV}.`,
  );
};

const resolveApiKeys = async (): Promise<Record<string, { roles: string[]; tenant?: string }>> => {
  const envValue = resolveEnvironment('OMERTA_GATEWAY_API_KEYS', {
    aliases: ['AION_GATEWAY_API_KEYS'],
  });
  if (typeof envValue === 'string' && envValue.trim()) {
    const parsed = parseApiKeysString(envValue);
    if (Object.keys(parsed).length > 0) {
      return parsed;
    }
  }

  const secretPath = resolveEnvironment('OMERTA_GATEWAY_API_KEYS_SECRET_PATH', {
    aliases: ['AION_GATEWAY_API_KEYS_SECRET_PATH'],
  });
  if (!secretPath) {
    return {};
  }

  const provider = await getSecretProvider();
  if (!provider) {
    throw new SecretProviderError(
      'Secret provider is not configured for OMERTA_GATEWAY_API_KEYS_SECRET_PATH; ' +
        'set OMERTA_GATEWAY_API_KEYS or configure a provider.',
    );
  }

  const payload = await provider.getSecret(secretPath);
  return parseApiKeysSecret(payload);
};

const takeString = (candidate: unknown): string | undefined => {
  if (typeof candidate === 'string' && candidate.trim()) {
    return candidate.trim();
  }
  return undefined;
};

const normalisePemArray = (value: unknown): string[] | undefined => {
  if (!value) {
    return undefined;
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed ? [trimmed] : undefined;
  }
  if (Array.isArray(value)) {
    const entries = value
      .map((item) => (typeof item === 'string' ? item.trim() : ''))
      .filter((item) => item.length > 0);
    return entries.length ? entries : undefined;
  }
  return undefined;
};

const resolveTlsMaterials = async (): Promise<{
  secretPath?: string;
  clientCaSecretPath?: string;
  certPem?: string;
  keyPem?: string;
  caPem?: string[];
}> => {
  const secretPath = resolveEnvironment('OMERTA_TLS_SECRET_PATH', {
    aliases: ['AION_TLS_SECRET_PATH'],
  });
  const clientCaSecretPath = resolveEnvironment('OMERTA_TLS_CLIENT_CA_SECRET_PATH', {
    aliases: ['AION_TLS_CLIENT_CA_SECRET_PATH'],
  });
  let certPem =
    takeString(resolveEnvironment('OMERTA_TLS_CERT_PEM', {
      aliases: ['AION_TLS_CERT_PEM'],
    })) ||
    takeString(resolveEnvironment('OMERTA_TLS_CERT', {
      aliases: ['AION_TLS_CERT'],
    }));
  let keyPem =
    takeString(resolveEnvironment('OMERTA_TLS_KEY_PEM', {
      aliases: ['AION_TLS_KEY_PEM'],
    })) ||
    takeString(resolveEnvironment('OMERTA_TLS_KEY', {
      aliases: ['AION_TLS_KEY'],
    }));
  let caPem =
    normalisePemArray(resolveEnvironment('OMERTA_TLS_CA_PEM', {
      aliases: ['AION_TLS_CA_PEM'],
    })) ||
    normalisePemArray(resolveEnvironment('OMERTA_TLS_CA_CHAIN', {
      aliases: ['AION_TLS_CA_CHAIN'],
    }));

  if (secretPath) {
    const provider = await requireSecretProvider('OMERTA_TLS_SECRET_PATH');
    const payload = await provider.getSecret(secretPath);
    if (typeof payload === 'string') {
      throw new SecretProviderError(
        'Secret referenced by OMERTA_TLS_SECRET_PATH must contain certificate and private_key fields',
      );
    }
    certPem =
      takeString(payload.certificate) ||
      takeString(payload.cert) ||
      takeString(payload.public_cert) ||
      certPem;
    keyPem = takeString(payload.private_key) || takeString(payload.key) || keyPem;
    caPem =
      normalisePemArray(payload.ca_chain) ||
      normalisePemArray(payload.ca) ||
      normalisePemArray(payload.certificate_authority) ||
      caPem;
  }

  if (clientCaSecretPath) {
    const provider = await requireSecretProvider('OMERTA_TLS_CLIENT_CA_SECRET_PATH');
    const payload = await provider.getSecret(clientCaSecretPath);
    if (typeof payload === 'string') {
      caPem = normalisePemArray(payload) || caPem;
    } else {
      caPem =
        normalisePemArray(payload.ca_chain) ||
        normalisePemArray(payload.ca) ||
        normalisePemArray(payload.certificate) ||
        caPem;
    }
  }

  return {
    secretPath,
    clientCaSecretPath,
    certPem,
    keyPem,
    caPem,
  };
};

export async function buildGatewayConfig(): Promise<GatewayConfig> {
  const [apiKeys, jwtPublicKey, adminToken, tlsMaterials] = await Promise.all([
    resolveApiKeys(),
    resolveJwtPublicKey(),
    resolveAdminToken(),
    resolveTlsMaterials(),
  ]);

  const environment = resolveEnvironment<GatewayEnvironment>('OMERTA_ENV', {
    aliases: ['AION_ENV'],
    defaultValue: process.env.NODE_ENV || 'development',
    parse: (value) => value as GatewayEnvironment,
  }) as GatewayEnvironment;
  const corsOrigins = resolveEnvironment('OMERTA_CORS_ORIGINS', {
    aliases: ['AION_CORS_ORIGINS'],
  });
  const cors = resolveCorsConfiguration(corsOrigins, environment);

  const requireMtlsSetting = resolveEnvironment('OMERTA_TLS_REQUIRE_MTLS', {
    aliases: ['AION_TLS_REQUIRE_MTLS'],
    defaultValue: 'false',
  });
  const requireMtls =
    ['1', 'true', 'yes', 'on'].includes(requireMtlsSetting as string) ||
    profile === 'enterprise-vip';

  const requireTlsSetting = resolveEnvironment('OMERTA_TLS_REQUIRED', {
    aliases: ['AION_TLS_REQUIRED'],
    defaultValue: 'false',
  });
  const requireTls =
    requireMtls || ['1', 'true', 'yes', 'on'].includes(requireTlsSetting as string);

  const controlBase =
    resolveEnvironment('OMERTA_CONTROL_BASE_URL', {
      aliases: ['AION_CONTROL_BASE_URL'],
    }) ||
    resolveEnvironment('OMERTA_CONTROL_BASE', {
      aliases: ['AION_CONTROL_BASE'],
    }) ||
    'http://localhost:8000';
  const rawApiPrefix = resolveEnvironment('OMERTA_CONTROL_API_PREFIX', {
    aliases: ['AION_CONTROL_API_PREFIX'],
    defaultValue: '/v1',
  }) as string;
  const apiPrefix = rawApiPrefix.startsWith('/') ? rawApiPrefix : `/${rawApiPrefix}`;
  const trimmedControlBase = controlBase.replace(/\/$/, '');

  const redisUrl = (() => {
    const configured = resolveEnvironment('OMERTA_REDIS_URL', {
      aliases: ['AION_REDIS_URL'],
    });
    if (configured && configured.trim().length > 0) {
      return configured;
    }

    const isDocker =
      process.env.CONTAINER === 'docker' ||
      process.env.DOCKER_CONTAINER === 'true' ||
      fs.existsSync('/.dockerenv');

    if (isDocker) {
      return 'redis://redis:6379/0';
    }

    return 'redis://127.0.0.1:6379/0';
  })();

  return {
    port: resolveEnvironment('OMERTA_GATEWAY_PORT', {
      aliases: ['AION_GATEWAY_PORT'],
      defaultValue: '8080',
      parse: integerParser({ minimum: 1, maximum: 65535 }),
    }) as number,
    host: resolveEnvironment('OMERTA_GATEWAY_HOST', {
      aliases: ['AION_GATEWAY_HOST'],
      defaultValue: '0.0.0.0',
    }) as string,
    controlGrpcEndpoint: resolveEnvironment('OMERTA_CONTROL_GRPC', {
      aliases: ['AION_CONTROL_GRPC'],
      defaultValue: 'control:50051',
    }) as string,
    controlBaseUrl: `${trimmedControlBase}${apiPrefix}`,
    redisUrl,
    selfEvolving: {
      enabled: !['false', '0'].includes(
        resolveEnvironment('OMERTA_SELF_EVOLVING_ENABLED', {
          aliases: ['AION_SELF_EVOLVING_ENABLED'],
          defaultValue: 'true',
        }) as string,
      ),
      modelRegistryUrl: resolveEnvironment('OMERTA_MODEL_REGISTRY_URL', {
        aliases: ['AION_MODEL_REGISTRY_URL'],
        defaultValue: 'http://aion-model-registry:8081',
      }) as string,
      memoryUrl: resolveEnvironment('OMERTA_MEMORY_URL', {
        aliases: ['AION_MEMORY_URL'],
        defaultValue: 'http://aion-memory:8080',
      }) as string,
      defaultChannel: resolveEnvironment('OMERTA_SELF_EVOLVING_CHANNEL', {
        aliases: ['AION_SELF_EVOLVING_CHANNEL'],
        defaultValue: 'enterprise',
      }) as string,
    },
    apiKeys,
    jwtPublicKey,
    corsOrigins: cors.origins,
    corsAllowCredentials: cors.allowCredentials,
    rateLimit: {
      max: resolveEnvironment('OMERTA_RATE_LIMIT_MAX', {
        aliases: ['AION_RATE_LIMIT_MAX'],
        defaultValue: '60',
        parse: integerParser({ minimum: 1 }),
      }) as number,
      timeWindow: resolveEnvironment('OMERTA_RATE_LIMIT_WINDOW', {
        aliases: ['AION_RATE_LIMIT_WINDOW'],
        defaultValue: '1 minute',
      }) as string,
      perIp: resolveEnvironment('OMERTA_RATE_LIMIT_PER_IP', {
        aliases: ['AION_RATE_LIMIT_PER_IP'],
        defaultValue: '30',
        parse: integerParser({ minimum: 1 }),
      }) as number,
    },
    idempotencyTtlSeconds: resolveEnvironment('OMERTA_IDEMPOTENCY_TTL', {
      aliases: ['AION_IDEMPOTENCY_TTL'],
      defaultValue: '900',
      parse: integerParser({ minimum: 1 }),
    }) as number,
    environment,
    tls: {
      requireMtls,
      requireTls,
      secretPath: tlsMaterials.secretPath,
      clientCaSecretPath: tlsMaterials.clientCaSecretPath,
      certPem: tlsMaterials.certPem,
      keyPem: tlsMaterials.keyPem,
      caPem: tlsMaterials.caPem,
    },
    telemetry: {
      enabled: resolveEnvironment('OMERTA_OTEL_ENABLED', {
        aliases: ['AION_OTEL_ENABLED'],
        defaultValue: 'false',
      }) === 'true',
      serviceName: resolveEnvironment('OMERTA_SERVICE_NAME', {
        aliases: ['AION_SERVICE_NAME'],
        defaultValue: 'aion-gateway',
      }) as string,
    },
    profile,
    featureSeal,
    adminToken,
    devKernel: {
      enabled: resolveEnvironment('OMERTA_DEV_KERNEL_ENABLED', {
        aliases: ['AION_DEV_KERNEL_ENABLED'],
        defaultValue: 'true',
      }) !== 'false',
      url: resolveEnvironment('OMERTA_DEV_KERNEL_URL', {
        aliases: ['AION_DEV_KERNEL_URL'],
        defaultValue: 'http://dev-kernel:9100/kernel',
      }) as string,
      profile: resolveEnvironment('OMERTA_DEV_KERNEL_PROFILE', {
        aliases: ['AION_DEV_KERNEL_PROFILE'],
        defaultValue: 'dev-qwen-coder',
      }) as string,
    },
  };
}

export const gatewayConfig: GatewayConfig = await buildGatewayConfig();
