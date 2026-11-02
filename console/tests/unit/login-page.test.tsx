import { afterEach, beforeEach, expect, it, vi } from "vitest";

const { redirect, getServerSession, isSetupComplete } = vi.hoisted(() => ({
  redirect: vi.fn(),
  getServerSession: vi.fn(),
  isSetupComplete: vi.fn(),
}));

vi.mock("next/navigation", () => ({ redirect }));
vi.mock("next-auth", () => ({ getServerSession }));
vi.mock("@/lib/auth", () => ({ authOptions: {} }));
vi.mock("@/lib/setup", () => ({ isSetupComplete }));
vi.mock("@/app/(auth)/login/LoginForm", () => ({ default: () => null }));

beforeEach(() => {
  vi.clearAllMocks();
  redirect.mockImplementation(() => {
    throw new Error("redirect");
  });
  getServerSession.mockResolvedValue(null);
  isSetupComplete.mockResolvedValue(true);
  vi.stubEnv("CONSOLE_ADMIN_EMAIL", "admin@example.test");
  vi.stubEnv("CONSOLE_ADMIN_PASSWORD", "synthetic-test-password-only");
});

afterEach(() => vi.unstubAllEnvs());

it("does not pass the administrator password to the client login form", async () => {
  const { default: LoginPage } = await import("@/app/(auth)/login/page");
  const element = await LoginPage();
  expect(element.props.defaultHint).toBe("Administrator email: admin@example.test");
  expect(JSON.stringify(element.props)).not.toContain(
    "synthetic-test-password-only",
  );
});

it("uses a generic hint when no administrator email is configured", async () => {
  vi.stubEnv("CONSOLE_ADMIN_EMAIL", undefined);
  const { default: LoginPage } = await import("@/app/(auth)/login/page");
  const element = await LoginPage();

  expect(element.props.defaultHint).toBe(
    "Use the admin credentials you configured earlier.",
  );
});

it("redirects to setup before rendering a login form on first boot", async () => {
  isSetupComplete.mockResolvedValue(false);
  const { default: LoginPage } = await import("@/app/(auth)/login/page");

  await expect(LoginPage()).rejects.toThrow("redirect");
  expect(redirect).toHaveBeenCalledWith("/setup");
  expect(getServerSession).not.toHaveBeenCalled();
});

it("redirects authenticated users before rendering a login form", async () => {
  getServerSession.mockResolvedValue({ user: { email: "admin@example.test" } });
  const { default: LoginPage } = await import("@/app/(auth)/login/page");

  await expect(LoginPage()).rejects.toThrow("redirect");
  expect(redirect).toHaveBeenCalledWith("/");
});
