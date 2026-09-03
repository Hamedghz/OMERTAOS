import { describe, expect, it, vi } from "vitest";

import {
  EnvironmentResolutionError,
  integerParser,
  resolveEnvironment,
} from "../../gateway/src/config/environment.js";

const CANONICAL = "OMERTA_TEST_CANONICAL";
const LEGACY = "AION_TEST_LEGACY";

describe("Gateway environment resolver", () => {
  it("supports canonical-only, legacy-only, and equal values", () => {
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

  it("fails closed on conflict without exposing either value", () => {
    let error: unknown;
    try {
      resolveEnvironment(CANONICAL, {
        aliases: [LEGACY],
        env: { [CANONICAL]: "canonical-secret", [LEGACY]: "legacy-secret" },
      });
    } catch (caught) {
      error = caught;
    }

    expect(error).toBeInstanceOf(EnvironmentResolutionError);
    const rendered = String(error);
    expect(rendered).toContain(CANONICAL);
    expect(rendered).toContain(LEGACY);
    expect(rendered).not.toContain("canonical-secret");
    expect(rendered).not.toContain("legacy-secret");
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

  it.each(["not-a-number-sensitive", "7", "33"])(
    "rejects malformed or out-of-range integer %s without echoing it",
    (value) => {
      let error: unknown;
      try {
        resolveEnvironment(CANONICAL, {
          env: { [CANONICAL]: value },
          parse: integerParser({ minimum: 8, maximum: 32 }),
        });
      } catch (caught) {
        error = caught;
      }

      expect(error).toBeInstanceOf(EnvironmentResolutionError);
      expect(String(error)).toContain(CANONICAL);
      expect(String(error)).not.toContain(value);
    },
  );
});
