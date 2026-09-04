import path from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import { resolveProtoPath } from "../../gateway/src/protoPath.js";

describe("Gateway protobuf environment", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("uses the canonical protobuf root", () => {
    vi.stubEnv(
      "OMERTA_PROTO_ROOT",
      path.resolve(process.cwd(), "schemas/v1/protos"),
    );
    vi.stubEnv("AION_PROTO_ROOT", "");

    expect(
      resolveProtoPath("aion/v1/tasks.proto").endsWith(
        "schemas/v1/protos/aion/v1/tasks.proto",
      ),
    ).toBe(true);
  });

  it("rejects conflicting protobuf roots", () => {
    vi.stubEnv("OMERTA_PROTO_ROOT", "/canonical-test-root");
    vi.stubEnv("AION_PROTO_ROOT", "/legacy-test-root");

    expect(() => resolveProtoPath("aion/v1/tasks.proto")).toThrow(
      /OMERTA_PROTO_ROOT.*AION_PROTO_ROOT/,
    );
  });
});
