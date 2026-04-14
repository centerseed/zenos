export const REDACTION_RULES_VERSION = "2026-04-14";

const SENSITIVE_KEYWORDS = [
  "api_key",
  "apikey",
  "token",
  "secret",
  "password",
  "passwd",
  "authorization",
  "bearer",
  "cookie",
  "session",
] as const;

const SENSITIVE_PATTERNS: RegExp[] = [
  /\b(sk|rk|pk|ghp|ghu|github_pat)_[a-z0-9_\-]{10,}\b/gi,
  /\bya29\.[a-z0-9._\-]+\b/gi,
  /\b(?:eyJ[a-zA-Z0-9_\-]+=*\.){2}[a-zA-Z0-9_\-=+/]*\b/g,
  /\b[A-Za-z0-9+/]{32,}={0,2}\b/g,
];

function shouldRedactKey(key: string): boolean {
  const normalized = key.trim().toLowerCase();
  return SENSITIVE_KEYWORDS.some((keyword) => normalized.includes(keyword));
}

export function redactSensitiveText(input: string): string {
  let result = input;
  for (const pattern of SENSITIVE_PATTERNS) {
    result = result.replace(pattern, "[REDACTED]");
  }
  return result;
}

export function sanitizeContextValue(value: unknown): unknown {
  if (value == null) return value;
  if (typeof value === "string") return redactSensitiveText(value);
  if (Array.isArray(value)) return value.map((item) => sanitizeContextValue(item));
  if (typeof value === "object") {
    const output: Record<string, unknown> = {};
    for (const [key, raw] of Object.entries(value as Record<string, unknown>)) {
      output[key] = shouldRedactKey(key) ? "[REDACTED]" : sanitizeContextValue(raw);
    }
    return output;
  }
  return value;
}

export function serializeSanitizedContextValue(value: unknown): string | null {
  if (value == null) return null;
  const sanitized = sanitizeContextValue(value);
  if (typeof sanitized === "string") return sanitized;
  try {
    return JSON.stringify(sanitized, null, 2);
  } catch {
    return String(sanitized);
  }
}
