import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("Console Gateway URL environment compatibility", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv("AION_DOCKER", "");
    vi.stubEnv("DOCKER", "");
    vi.stubEnv("GATEWAY_URL", "");
    vi.stubEnv("NEXT_PUBLIC_GATEWAY_URL", "");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("uses the canonical product Gateway URL", async () => {
    vi.stubEnv("OMERTA_GATEWAY_URL", "http://canonical-gateway:8080/");
    vi.stubEnv("AION_GATEWAY_URL", "");

    const { GATEWAY_HTTP_URL } = await import("@/lib/gatewayConfig");

    expect(GATEWAY_HTTP_URL).toBe("http://canonical-gateway:8080");
  });

  it("accepts the legacy URL with a key-only deprecation warning", async () => {
    vi.stubEnv("OMERTA_GATEWAY_URL", "");
    vi.stubEnv("AION_GATEWAY_URL", "http://legacy-sensitive:8080");
    const warning = vi
      .spyOn(console, "warn")
      .mockImplementation(() => undefined);

    const { GATEWAY_HTTP_URL } = await import("@/lib/gatewayConfig");

    expect(GATEWAY_HTTP_URL).toBe("http://legacy-sensitive:8080");
    expect(warning).toHaveBeenCalledWith(
      "AION_GATEWAY_URL is deprecated; use OMERTA_GATEWAY_URL",
    );
    expect(JSON.stringify(warning.mock.calls)).not.toContain(
      "legacy-sensitive",
    );
  });

  it("rejects conflicting URLs without exposing either URL", async () => {
    vi.stubEnv("OMERTA_GATEWAY_URL", "http://canonical-sensitive:8080");
    vi.stubEnv("AION_GATEWAY_URL", "http://legacy-sensitive:8080");

    let error: unknown;
    try {
      await import("@/lib/gatewayConfig");
    } catch (caught) {
      error = caught;
    }

    const rendered = String(error);
    expect(rendered).toContain("OMERTA_GATEWAY_URL");
    expect(rendered).toContain("AION_GATEWAY_URL");
    expect(rendered).not.toContain("canonical-sensitive");
    expect(rendered).not.toContain("legacy-sensitive");
  });
});
