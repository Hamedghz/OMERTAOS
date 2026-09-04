import { NextResponse } from "next/server";

import { requireApiAccess } from "@/lib/apiAccess";
import { getDatabaseDiagnostics } from "@/lib/databaseInfo";
import { isDockerEnvironment } from "@/lib/gatewayConfig";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

export async function GET() {
  const denied = await requireApiAccess("ADMIN");
  if (denied) return denied;

  const diagnostics = getDatabaseDiagnostics(
    process.env.DATABASE_URL,
    isDockerEnvironment() || process.env.NODE_ENV === "production",
  );

  return NextResponse.json({
    provider: diagnostics.provider,
    enforced: diagnostics.enforced,
    url: diagnostics.redactedUrl,
    timestamp: new Date().toISOString(),
  });
}
