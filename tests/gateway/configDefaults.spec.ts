import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("gateway configuration defaults", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv("OMERTA_GATEWAY_PORT", "");
    vi.stubEnv("AION_GATEWAY_PORT", "");
    vi.stubEnv("OMERTA_CONSOLE_ORIGIN", "");
    vi.stubEnv("AION_CONSOLE_ORIGIN", "");
    vi.stubEnv("OMERTA_CORS_ORIGINS", "");
    vi.stubEnv("AION_CORS_ORIGINS", "");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("matches the documented Gateway and Console ports", async () => {
    const { gatewayConfig } = await import("../../gateway/src/config.js");

    expect(gatewayConfig.port).toBe(8080);
    expect(gatewayConfig.corsOrigins).toEqual(["http://localhost:3000"]);
  });

  it("uses the canonical Gateway profile name", async () => {
    vi.stubEnv("OMERTA_GATEWAY_PROFILE", "professional");
    vi.stubEnv("AION_PROFILE", "");

    const { gatewayConfig } = await import("../../gateway/src/config.js");

    expect(gatewayConfig.profile).toBe("professional");
  });

  it("uses the canonical Gateway port", async () => {
    vi.stubEnv("OMERTA_GATEWAY_PORT", "8181");
    vi.stubEnv("AION_GATEWAY_PORT", "");

    const { gatewayConfig } = await import("../../gateway/src/config.js");

    expect(gatewayConfig.port).toBe(8181);
  });

  it("rejects conflicting Gateway ports without exposing values", async () => {
    vi.stubEnv("OMERTA_GATEWAY_PORT", "8181");
    vi.stubEnv("AION_GATEWAY_PORT", "8282");

    let error: unknown;
    try {
      await import("../../gateway/src/config.js");
    } catch (caught) {
      error = caught;
    }

    const rendered = String(error);
    expect(rendered).toContain("OMERTA_GATEWAY_PORT");
    expect(rendered).toContain("AION_GATEWAY_PORT");
    expect(rendered).not.toContain("8181");
    expect(rendered).not.toContain("8282");
  });

  it("rejects conflicting Gateway profile names without exposing values", async () => {
    vi.stubEnv("OMERTA_GATEWAY_PROFILE", "professional");
    vi.stubEnv("AION_PROFILE", "enterprise-vip");

    let error: unknown;
    try {
      await import("../../gateway/src/config.js");
    } catch (caught) {
      error = caught;
    }

    const rendered = String(error);
    expect(rendered).toContain("OMERTA_GATEWAY_PROFILE");
    expect(rendered).toContain("AION_PROFILE");
    expect(rendered).not.toContain("professional");
    expect(rendered).not.toContain("enterprise-vip");
  });

  it("reads the remaining Gateway settings from canonical names", async () => {
    const settings = {
      OMERTA_SELF_EVOLVING_ENABLED: "false",
      OMERTA_MODEL_REGISTRY_URL: "http://models.test:8081",
      OMERTA_MEMORY_URL: "http://memory.test:8080",
      OMERTA_SELF_EVOLVING_CHANNEL: "stable",
      OMERTA_RATE_LIMIT_MAX: "80",
      OMERTA_RATE_LIMIT_WINDOW: "2 minutes",
      OMERTA_RATE_LIMIT_PER_IP: "20",
      OMERTA_IDEMPOTENCY_TTL: "1200",
      OMERTA_TLS_REQUIRE_MTLS: "false",
      OMERTA_TLS_REQUIRED: "true",
      OMERTA_OTEL_ENABLED: "true",
      OMERTA_SERVICE_NAME: "omerta-gateway-test",
      OMERTA_DEV_KERNEL_ENABLED: "false",
      OMERTA_DEV_KERNEL_URL: "http://kernel.test:9100/kernel",
      OMERTA_DEV_KERNEL_PROFILE: "test-profile",
    };
    for (const [name, value] of Object.entries(settings)) {
      vi.stubEnv(name, value);
      vi.stubEnv(name.replace("OMERTA_", "AION_"), "");
    }

    const { gatewayConfig } = await import("../../gateway/src/config.js");

    expect(gatewayConfig.selfEvolving).toEqual({
      enabled: false,
      modelRegistryUrl: "http://models.test:8081",
      memoryUrl: "http://memory.test:8080",
      defaultChannel: "stable",
    });
    expect(gatewayConfig.rateLimit).toEqual({
      max: 80,
      timeWindow: "2 minutes",
      perIp: 20,
    });
    expect(gatewayConfig.idempotencyTtlSeconds).toBe(1200);
    expect(gatewayConfig.tls.requireMtls).toBe(false);
    expect(gatewayConfig.tls.requireTls).toBe(true);
    expect(gatewayConfig.telemetry).toEqual({
      enabled: true,
      serviceName: "omerta-gateway-test",
    });
    expect(gatewayConfig.devKernel).toEqual({
      enabled: false,
      url: "http://kernel.test:9100/kernel",
      profile: "test-profile",
    });
  });

  it("reads canonical TLS material and redacts conflicting values", async () => {
    vi.stubEnv("OMERTA_TLS_CERT_PEM", "canonical-test-certificate");
    vi.stubEnv("AION_TLS_CERT_PEM", "");
    vi.stubEnv("OMERTA_TLS_KEY_PEM", "canonical-test-private-key");
    vi.stubEnv("AION_TLS_KEY_PEM", "");

    const { gatewayConfig } = await import("../../gateway/src/config.js");
    expect(gatewayConfig.tls.certPem).toBe("canonical-test-certificate");
    expect(gatewayConfig.tls.keyPem).toBe("canonical-test-private-key");

    vi.resetModules();
    vi.stubEnv("AION_TLS_KEY_PEM", "legacy-test-private-key");
    let error: unknown;
    try {
      await import("../../gateway/src/config.js");
    } catch (caught) {
      error = caught;
    }

    const rendered = String(error);
    expect(rendered).toContain("OMERTA_TLS_KEY_PEM");
    expect(rendered).toContain("AION_TLS_KEY_PEM");
    expect(rendered).not.toContain("canonical-test-private-key");
    expect(rendered).not.toContain("legacy-test-private-key");
  });
});
