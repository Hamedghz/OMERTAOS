import { diag, DiagConsoleLogger, DiagLogLevel } from '@opentelemetry/api';
import { NodeSDK } from '@opentelemetry/sdk-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { resourceFromAttributes } from '@opentelemetry/resources';
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';

let sdk: NodeSDK | undefined;

export const startTelemetry = async (
  serviceName: string,
  enabled: boolean,
): Promise<boolean> => {
  if (!enabled) {
    return false;
  }
  const endpoint = process.env.OTEL_EXPORTER_OTLP_ENDPOINT;
  const exporter = endpoint ? new OTLPTraceExporter({ url: endpoint }) : new OTLPTraceExporter();
  diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.WARN);
  sdk = new NodeSDK({
    traceExporter: exporter,
    resource: resourceFromAttributes({
      [SemanticResourceAttributes.SERVICE_NAME]: serviceName,
    }),
  });
  await sdk.start();
  return true;
};

export const shutdownTelemetry = async (): Promise<void> => {
  if (sdk) {
    try {
      await sdk.shutdown();
    } catch (error) {
      // eslint-disable-next-line no-console
      console.warn('Failed to shut down telemetry', error);
    }
    sdk = undefined;
  }
};
