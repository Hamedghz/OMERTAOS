import { NextResponse } from "next/server";

import { resolveGatewayBase } from "@/lib/gatewayClient";
import { ensureSetupState } from "@/lib/systemState";

type ServiceStatus = "ok" | "degraded";

type ServiceCheck = {
  status: ServiceStatus;
  details: string;
};

const stripTrailingSlash = (value: string) => value.replace(/\/+$/, "");

const gatewayBase = () =>
  stripTrailingSlash(
    process.env.GATEWAY_URL ||
      resolveGatewayBase() ||
      "http://gateway:8080",
  );

const consoleBase = () =>
  stripTrailingSlash(
    process.env.INTERNAL_CONSOLE_URL ||
      process.env.CONSOLE_URL ||
      process.env.NEXTAUTH_URL ||
      "http://localhost:3000",
  );

async function check(
  baseUrl: string,
  paths: string[] = ["/healthz", "/health"],
): Promise<ServiceCheck> {
  const attempts: string[] = [];

  for (const path of paths) {
    const url = `${baseUrl}${path}`;
    attempts.push(url);

    try {
      const res = await fetch(url, { cache: "no-store" });

      if (res.ok) {
        return { status: "ok", details: `HTTP ${res.status} ${path}` };
      }

      attempts.push(`HTTP ${res.status}`);
    } catch {
      attempts.push("unreachable");
    }
  }

  return {
    status: "degraded",
    details: `unreachable: ${attempts.join(" | ")}`,
  };
}

async function checkGateway(): Promise<{
  gateway: ServiceCheck;
  control: ServiceCheck;
}> {
  try {
    const res = await fetch(`${gatewayBase()}/health`, { cache: "no-store" });
    const payload = await res.json().catch(() => ({}));
    const dependency = payload?.dependencies?.control;

    return {
      gateway: {
        status: res.ok ? "ok" : "degraded",
        details: `HTTP ${res.status} /health`,
      },
      control: {
        status: res.ok && dependency === "ok" ? "ok" : "degraded",
        details: `Gateway dependency: ${typeof dependency === "string" ? dependency : "unknown"}`,
      },
    };
  } catch {
    return {
      gateway: {
        status: "degraded",
        details: "unreachable via Gateway /health",
      },
      control: {
        status: "degraded",
        details: "Gateway dependency unavailable",
      },
    };
  }
}

export async function GET() {
  const [gatewayHealth, consoleSvc, setupComplete] = await Promise.all([
    checkGateway(),
    check(consoleBase()),
    ensureSetupState().catch(() => false),
  ]);
  const { gateway, control } = gatewayHealth;

  const status: ServiceStatus = [gateway, control, consoleSvc].some(
    (service) => service.status === "degraded",
  )
    ? "degraded"
    : "ok";

  return NextResponse.json({
    status,
    services: {
      gateway,
      control,
      console: consoleSvc,
    },
    setupComplete,
    updatedAt: new Date().toISOString(),
  });
}
