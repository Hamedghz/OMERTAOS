import { describe, expect, it } from "vitest";

import { isDockerEnvironment } from "@/lib/gatewayConfig";

describe("system database environment", () => {
  it("uses the canonical Docker marker", () => {
    expect(isDockerEnvironment({ OMERTA_DOCKER: "1" })).toBe(true);
    expect(isDockerEnvironment({ OMERTA_DOCKER: "0" })).toBe(false);
  });

  it("rejects conflicting Docker markers without exposing values", () => {
    let error: unknown;
    try {
      isDockerEnvironment({ OMERTA_DOCKER: "1", AION_DOCKER: "0" });
    } catch (caught) {
      error = caught;
    }

    const rendered = String(error);
    expect(rendered).toContain("OMERTA_DOCKER");
    expect(rendered).toContain("AION_DOCKER");
    expect(rendered).not.toContain(" 1");
    expect(rendered).not.toContain(" 0");
  });
});
