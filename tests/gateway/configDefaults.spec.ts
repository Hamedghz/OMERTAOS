import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("gateway configuration defaults", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv("AION_GATEWAY_PORT", "");
    vi.stubEnv("AION_CONSOLE_ORIGIN", "");
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
});
