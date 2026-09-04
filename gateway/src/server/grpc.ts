import { credentials, loadPackageDefinition } from '@grpc/grpc-js';
import { loadSync } from '@grpc/proto-loader';
import { resolveEnvironment } from '../config/environment.js';
import { loadTlsArtifacts } from '../config/tls.js';
import { gatewayConfig } from '../config.js';
import { resolveProtoPath } from '../protoPath.js';

const protoPath = resolveProtoPath('aion/v1/tasks.proto');

const packageDefinition = loadSync(protoPath, {
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true,
});

const loaded = loadPackageDefinition(packageDefinition) as unknown as {
  aion: {
    v1: {
      AionTasks: new (addr: string, creds: ReturnType<typeof credentials.createInsecure>, options?: Record<string, unknown>) => any;
    };
  };
};

export const createControlClient = () => {
  const { controlGrpcEndpoint } = gatewayConfig;
  const tls = loadTlsArtifacts();
  if (tls.enabled) {
    const rootCerts = tls.ca?.length ? Buffer.concat(tls.ca) : undefined;
    const secureCreds = credentials.createSsl(rootCerts, tls.key, tls.cert);
    const tlsName = resolveEnvironment('OMERTA_CONTROL_TLS_NAME', {
      aliases: ['AION_CONTROL_TLS_NAME'],
      defaultValue: 'control.aion.local',
    }) as string;
    const options = tls.requestClientCert
      ? { 'grpc.ssl_target_name_override': tlsName }
      : undefined;
    return new loaded.aion.v1.AionTasks(controlGrpcEndpoint, secureCreds, options);
  }
  return new loaded.aion.v1.AionTasks(controlGrpcEndpoint, credentials.createInsecure());
};
