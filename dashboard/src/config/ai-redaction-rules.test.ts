import { describe, expect, it } from "vitest";
import {
  REDACTION_RULES_VERSION,
  redactSensitiveText,
  sanitizeContextValue,
  serializeSanitizedContextValue,
} from "@/config/ai-redaction-rules";

describe("ai redaction rules", () => {
  it("redacts known token patterns and sensitive keys", () => {
    expect(REDACTION_RULES_VERSION).toBe("2026-04-14");
    expect(redactSensitiveText("token sk_1234567890abcdef")).toContain("[REDACTED]");

    const sanitized = sanitizeContextValue({
      api_key: "secret-1", // pragma: allowlist secret
      nested: {
        password: "pw", // pragma: allowlist secret
        note: "keep me",
      },
      raw: "ghp_1234567890abcdefghij",
    }) as Record<string, unknown>;

    expect(sanitized.api_key).toBe("[REDACTED]");
    expect((sanitized.nested as Record<string, unknown>).password).toBe("[REDACTED]");
    expect(sanitized.raw).toBe("[REDACTED]");
  });

  it("serializes sanitized objects for context pack injection", () => {
    const output = serializeSanitizedContextValue({
      session_token: "eyJabc.def.ghi",
      summary: "safe",
    });
    expect(output).toContain("[REDACTED]");
    expect(output).toContain("safe");
  });
});
