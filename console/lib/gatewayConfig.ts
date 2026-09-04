import { resolveEnvironment } from "./environment";

const dockerSetting = resolveEnvironment("OMERTA_DOCKER", {
  aliases: ["AION_DOCKER"],
});
const isDockerEnv = dockerSetting === "1" || process.env.DOCKER === "true";
const localDefaultGateway = "http://localhost:8080";
const dockerDefaultGateway = "http://gateway:8080";

const resolveGatewayUrl = (): string => {
  const defaultGateway = isDockerEnv
    ? dockerDefaultGateway
    : localDefaultGateway;
  const productGatewayUrl = resolveEnvironment("OMERTA_GATEWAY_URL", {
    aliases: ["AION_GATEWAY_URL"],
  });
  const raw =
    process.env.GATEWAY_URL ||
    productGatewayUrl ||
    process.env.NEXT_PUBLIC_GATEWAY_URL ||
    defaultGateway;

  const trimmed = raw.trim();
  if (!trimmed) {
    return defaultGateway;
  }

  // Avoid trailing slashes so callers can safely append paths.
  return trimmed.replace(/\/+$/, "") || defaultGateway;
};

export const GATEWAY_HTTP_URL = resolveGatewayUrl();
