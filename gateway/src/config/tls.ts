import { gatewayConfig } from '../config.js';

export interface TlsArtifacts {
  key?: Buffer;
  cert?: Buffer;
  ca?: Buffer[];
  enabled: boolean;
  requestClientCert: boolean;
}

export const loadTlsArtifacts = (): TlsArtifacts => {
  const keyPem = gatewayConfig.tls.keyPem;
  const certPem = gatewayConfig.tls.certPem;
  const caPem = gatewayConfig.tls.caPem;
  const tlsMaterialsAvailable = Boolean(keyPem && certPem);
  const tlsRequired = gatewayConfig.tls.requireTls;

  if (!tlsMaterialsAvailable) {
    if (tlsRequired) {
      throw new Error(
        'TLS key and certificate must be available from Vault or environment when TLS is required',
      );
    }
    console.warn(
      '[gateway] TLS key/cert missing; continuing with an insecure gRPC client (set OMERTA_TLS_REQUIRED=1 or provide certs to enable TLS)',
    );
    return { enabled: false, requestClientCert: false };
  }

  return {
    key: Buffer.from(keyPem!, 'utf8'),
    cert: Buffer.from(certPem!, 'utf8'),
    ca: caPem?.map((entry) => Buffer.from(entry, 'utf8')),
    enabled: true,
    requestClientCert: gatewayConfig.tls.requireMtls,
  };
};
