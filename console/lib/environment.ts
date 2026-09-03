export type BlankPolicy = "unset" | "preserve" | "reject";

export class EnvironmentResolutionError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "EnvironmentResolutionError";
  }
}

export interface ResolveEnvironmentOptions<T> {
  aliases?: readonly string[];
  defaultValue?: string;
  required?: boolean;
  blank?: BlankPolicy;
  parse?: (value: string) => T;
  env?: Record<string, string | undefined>;
  onDeprecated?: (canonicalName: string, legacyName: string) => void;
}

const warnDeprecated = (canonicalName: string, legacyName: string): void => {
  console.warn(`${legacyName} is deprecated; use ${canonicalName}`);
};

const normalizeValue = (
  name: string,
  value: string | undefined,
  blank: BlankPolicy,
): string | undefined => {
  if (value !== "") {
    return value;
  }
  if (blank === "unset") {
    return undefined;
  }
  if (blank === "preserve") {
    return value;
  }
  throw new EnvironmentResolutionError(`${name} may not be blank`);
};

export const resolveEnvironment = <T = string>(
  canonicalName: string,
  options: ResolveEnvironmentOptions<T> = {},
): T | undefined => {
  const aliases = options.aliases ?? [];
  const names = [canonicalName, ...aliases];
  if (names.some((name) => !name) || new Set(names).size !== names.length) {
    throw new Error("environment names must be non-empty and unique");
  }
  const hasDefault = Object.prototype.hasOwnProperty.call(
    options,
    "defaultValue",
  );
  if (options.required && hasDefault) {
    throw new Error("required environment settings cannot declare a default");
  }

  const env = options.env ?? process.env;
  const blank = options.blank ?? "unset";
  if (!["unset", "preserve", "reject"].includes(blank)) {
    throw new Error(`unsupported blank policy: ${blank}`);
  }
  const present = names
    .map((name) => [name, normalizeValue(name, env[name], blank)] as const)
    .filter(
      (entry): entry is readonly [string, string] => entry[1] !== undefined,
    );

  let selectedName = canonicalName;
  let rawValue: string | undefined;
  if (present.length > 0) {
    if (new Set(present.map(([, value]) => value)).size > 1) {
      const conflictingNames = present
        .map(([name]) => name)
        .filter((name) => name !== canonicalName)
        .join(", ");
      throw new EnvironmentResolutionError(
        `${canonicalName} conflicts with deprecated ${conflictingNames}`,
      );
    }
    const canonical = present.find(([name]) => name === canonicalName);
    [selectedName, rawValue] = canonical ?? present[0];
    if (!canonical) {
      const onDeprecated = options.onDeprecated ?? warnDeprecated;
      for (const [legacyName] of present) {
        onDeprecated(canonicalName, legacyName);
      }
    }
  } else if (hasDefault) {
    rawValue = options.defaultValue;
  } else if (options.required) {
    throw new EnvironmentResolutionError(`${canonicalName} is required`);
  } else {
    return undefined;
  }

  const parser = options.parse ?? ((value: string) => value as T);
  try {
    return parser(rawValue as string);
  } catch {
    throw new EnvironmentResolutionError(`${selectedName} is invalid`);
  }
};

export const integerParser = ({
  minimum,
  maximum,
}: {
  minimum?: number;
  maximum?: number;
} = {}): ((value: string) => number) => {
  return (value: string): number => {
    const trimmed = value.trim();
    if (!/^[+-]?\d+$/.test(trimmed)) {
      throw new Error("not an integer");
    }
    const parsed = Number(trimmed);
    if (!Number.isSafeInteger(parsed)) {
      throw new Error("outside the safe integer range");
    }
    if (minimum !== undefined && parsed < minimum) {
      throw new Error("below minimum");
    }
    if (maximum !== undefined && parsed > maximum) {
      throw new Error("above maximum");
    }
    return parsed;
  };
};

export const choiceParser = <T extends string>(
  choices: readonly T[],
): ((value: string) => T) => {
  const allowed = new Set<string>(choices);
  return (value: string): T => {
    const normalized = value.trim().toLowerCase();
    if (!allowed.has(normalized)) {
      throw new Error("unsupported choice");
    }
    return normalized as T;
  };
};
