import { describe, expect, it, vi } from "vitest";

import {
  EnvironmentResolutionError,
  integerParser,
  resolveEnvironment,
} from "@/lib/environment";

const CANONICAL = "OMERTA_TEST_CANONICAL";
const LEGACY = "AION_TEST_LEGACY";

describe("Console environment resolver", () => {
  it("supports canonical, deprecated alias, and equal values", () => {
    expect(
      resolveEnvironment(CANONICAL, {
        aliases: [LEGACY],
        env: { [CANONICAL]: "new" },
      }),
    ).toBe("new");

    const onDeprecated = vi.fn();
    expect(
      resolveEnvironment(CANONICAL, {
        aliases: [LEGACY],
        env: { [LEGACY]: "legacy-sensitive" },
        onDeprecated,
      }),
    ).toBe("legacy-sensitive");
    expect(onDeprecated).toHaveBeenCalledWith(CANONICAL, LEGACY);
    expect(JSON.stringify(onDeprecated.mock.calls)).not.toContain(
      "legacy-sensitive",
    );

    expect(
      resolveEnvironment(CANONICAL, {
        aliases: [LEGACY],
        env: { [CANONICAL]: "equal", [LEGACY]: "equal" },
        onDeprecated,
      }),
    ).toBe("equal");
    expect(onDeprecated).toHaveBeenCalledTimes(1);
  });

  it("redacts conflict and malformed values", () => {
    let conflict: unknown;
    try {
      resolveEnvironment(CANONICAL, {
        aliases: [LEGACY],
        env: { [CANONICAL]: "canonical-secret", [LEGACY]: "legacy-secret" },
      });
    } catch (error) {
      conflict = error;
    }
    expect(conflict).toBeInstanceOf(EnvironmentResolutionError);
    expect(String(conflict)).toContain(CANONICAL);
    expect(String(conflict)).toContain(LEGACY);
    expect(String(conflict)).not.toContain("canonical-secret");
    expect(String(conflict)).not.toContain("legacy-secret");

    let malformed: unknown;
    try {
      resolveEnvironment(CANONICAL, {
        env: { [CANONICAL]: "invalid-sensitive" },
        parse: integerParser({ minimum: 8, maximum: 32 }),
      });
    } catch (error) {
      malformed = error;
    }
    expect(String(malformed)).toContain(CANONICAL);
    expect(String(malformed)).not.toContain("invalid-sensitive");
  });

  it("applies explicit unset, blank, and required policies", () => {
    expect(
      resolveEnvironment(CANONICAL, { env: {}, defaultValue: "fallback" }),
    ).toBe("fallback");
    expect(resolveEnvironment(CANONICAL, { env: {} })).toBeUndefined();
    expect(
      resolveEnvironment(CANONICAL, {
        env: { [CANONICAL]: "" },
        defaultValue: "fallback",
      }),
    ).toBe("fallback");
    expect(
      resolveEnvironment(CANONICAL, {
        env: { [CANONICAL]: "" },
        blank: "preserve",
      }),
    ).toBe("");
    expect(() =>
      resolveEnvironment(CANONICAL, {
        env: { [CANONICAL]: "" },
        blank: "reject",
      }),
    ).toThrow(CANONICAL);
    expect(() =>
      resolveEnvironment(CANONICAL, { env: {}, required: true }),
    ).toThrow("required");
  });
});
