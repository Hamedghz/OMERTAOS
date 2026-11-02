export const dynamic = "force-dynamic";
export const revalidate = 0;

import { ReactNode } from "react";
import GlassPanel from "@/components/GlassPanel";
import BrandLogo from "@/components/BrandLogo";
import NavTabs from "@/components/NavTabs";
import UserMenu from "@/components/UserMenu";
import { ensureConsoleAccess } from "@/lib/consoleAccess";

export default async function DashboardLayout({
  children,
}: {
  children: ReactNode;
}) {
  const session = await ensureConsoleAccess();
  const role = (session.user as any)?.role ?? "USER";

  return (
    <section className="min-h-dvh text-white" dir="ltr">
      <div className="min-h-dvh grid gap-4 px-4 py-6 lg:grid-cols-[280px_1fr] lg:grid-rows-[auto_1fr]">
        <header className="lg:col-span-2">
          <GlassPanel className="flex flex-wrap items-center justify-between gap-4 p-4">
            <div className="flex items-center gap-3 text-left">
              <BrandLogo
                size={56}
                priority
                className="border border-white/20 shadow-lg"
              />
              <div className="space-y-1">
                <h1 className="text-2xl font-semibold text-white/90">
                  OMERTA OS
                </h1>
                <p className="text-sm text-white/65">
                  Unified console for control, gateway, and agents.
                </p>
              </div>
            </div>
            <UserMenu email={session.user?.email} role={role} />
          </GlassPanel>
        </header>

        <aside className="hidden min-h-0 lg:flex lg:flex-col">
          <GlassPanel className="flex flex-1 flex-col gap-4 p-4 text-left">
            <div>
              <h2 className="text-lg font-semibold text-white/85">
                Stack overview
              </h2>
              <p className="mt-1 text-sm text-white/60">
                Redis, Postgres, Qdrant, MinIO
              </p>
            </div>
            <div className="space-y-3 text-sm text-white/70">
              <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                <span className="font-medium text-white/80">Control</span>
                <p className="mt-1 leading-6">
                  HTTP and gRPC endpoints for orchestration.
                </p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                <span className="font-medium text-white/80">Gateway</span>
                <p className="mt-1 leading-6">
                  API gateway for console and client access.
                </p>
              </div>
            </div>
            <div className="mt-auto text-sm text-white/60">
              Theme: Liquid Glass with frosted highlights.
            </div>
          </GlassPanel>
        </aside>

        <main className="flex min-h-0 flex-col gap-4">
          <GlassPanel className="p-4">
            <NavTabs role={role} />
          </GlassPanel>
          <div className="grid gap-4 lg:grid-cols-2">
            <GlassPanel className="p-4 text-left">
              <h2 className="text-lg font-semibold text-white/85">
                Performance
              </h2>
              <p className="mt-2 text-sm leading-6 text-white/70">
                Monitor latency, throughput, and recent jobs.
              </p>
            </GlassPanel>
            <GlassPanel className="p-4 text-left">
              <h2 className="text-lg font-semibold text-white/85">Activity</h2>
              <p className="mt-2 text-sm leading-6 text-white/70">
                Keep track of recent tasks and agent activity.
              </p>
            </GlassPanel>
          </div>
          <GlassPanel className="p-4 text-left">{children}</GlassPanel>
        </main>
      </div>
    </section>
  );
}
