import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const ensureSetupState = vi.fn();

vi.mock("@/lib/systemState", () => ({ ensureSetupState }));
vi.mock("@/lib/gatewayClient", () => ({
  resolveGatewayBase: () => "http://gateway:8080",
}));

describe("system health route", () => {
  beforeEach(() => {
    vi.resetModules();
    ensureSetupState.mockReset().mockResolvedValue(false);
    process.env.GATEWAY_URL = "http://gateway:8080";
    process.env.INTERNAL_CONSOLE_URL = "http://localhost:3000";
    process.env.NEXTAUTH_URL = "http://localhost:23000";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    delete process.env.GATEWAY_URL;
    delete process.env.INTERNAL_CONSOLE_URL;
    delete process.env.NEXTAUTH_URL;
  });

  it("uses the internal URL for the container self-probe", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString();
      if (url === "http://gateway:8080/health") {
        return new Response(
          JSON.stringify({ dependencies: { control: "ok" } }),
          { status: 200 },
        );
      }
      if (url === "http://localhost:3000/healthz") {
        return new Response(null, { status: 200 });
      }
      throw new Error(`unexpected health URL: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const { GET } = await import("@/app/api/system/health/route");

    const response = await GET();
    const payload = await response.json();

    expect(payload.status).toBe("ok");
    expect(payload.services.console.status).toBe("ok");
    expect(fetchMock).not.toHaveBeenCalledWith(
      "http://localhost:23000/healthz",
      expect.anything(),
    );
  });

  it("degrades the aggregate status when the self-probe fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request) => {
      const url = input.toString();
      if (url === "http://gateway:8080/health") {
        return new Response(
          JSON.stringify({ dependencies: { control: "ok" } }),
          { status: 200 },
        );
      }
      throw new Error("console unavailable");
    }));
    const { GET } = await import("@/app/api/system/health/route");

    const response = await GET();
    const payload = await response.json();

    expect(payload.status).toBe("degraded");
    expect(payload.services.console.status).toBe("degraded");
  });
});
