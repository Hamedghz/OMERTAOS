import { SecretProvider, SecretProviderError } from '@aion/secret-provider';

import { resolveEnvironment } from './environment';

export interface ConsoleSecrets {
  adminToken: string;
}

const normalizeBoolean = (value: string | undefined): boolean => {
  if (!value) {
    return false;
  }
  const normalised = value.trim().toLowerCase();
  return normalised === '1' || normalised === 'true' || normalised === 'yes' || normalised === 'on';
};

let secretProvider: SecretProvider | null = null;
const resolveSecretProviderMode = (raw: string | undefined): string => {
  return (raw || 'local').trim().toLowerCase();
};

const secretProviderMode = resolveSecretProviderMode(process.env.SECRET_PROVIDER_MODE);

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

if (secretProviderMode === 'local') {
  secretProvider = new SecretProvider({ mode: 'local' });
} else if (vaultEnabled) {
  try {
    secretProvider = new SecretProvider({});
  } catch (error) {
    if (error instanceof SecretProviderError) {
      throw error;
    }
    throw new Error(`Failed to initialise Vault secret provider: ${String(error)}`);
  }
}

const ensureSecretProvider = (): SecretProvider => {
  if (!secretProvider) {
    throw new SecretProviderError(
      'Secret provider is not configured for OMERTA_GATEWAY_ADMIN_TOKEN_SECRET_PATH',
    );
  }
  return secretProvider;
};

const loadConsoleSecrets = async (): Promise<ConsoleSecrets> => {
  const secretPath = resolveEnvironment('OMERTA_GATEWAY_ADMIN_TOKEN_SECRET_PATH', {
    aliases: [
      'AION_GATEWAY_ADMIN_TOKEN_SECRET_PATH',
      'AION_ADMIN_TOKEN_SECRET_PATH',
    ],
  });
  const configuredToken = resolveEnvironment('OMERTA_GATEWAY_ADMIN_TOKEN', {
    aliases: ['AION_GATEWAY_ADMIN_TOKEN', 'AION_ADMIN_TOKEN'],
  });
  if (!secretPath) {
    return {
      adminToken: configuredToken || process.env.NEXT_PUBLIC_SETUP_TOKEN || '',
    };
  }
  const provider = ensureSecretProvider();
  const payload = await provider.getSecret(secretPath);
  if (typeof payload === 'string') {
    return { adminToken: payload };
  }
  if (typeof payload.token === 'string') {
    return { adminToken: payload.token };
  }
  if (typeof payload.value === 'string') {
    return { adminToken: payload.value };
  }
  return { adminToken: '' };
};

const consoleSecretsPromise = loadConsoleSecrets();

export const getConsoleSecrets = async (): Promise<ConsoleSecrets> => consoleSecretsPromise;
