import type { ParsedStructuredResult, StructuredResult } from "@/lib/copilot/types";

export type StructuredResultValidator = (
  target: string,
  value: unknown
) => string[];

function collectJsonCandidates(raw: string): string[] {
  const candidates: string[] = [];
  const trimmed = raw.trim();
  if (trimmed) candidates.push(trimmed);

  const fenced =
    raw.match(/```json\s*([\s\S]*?)```/i) ||
    raw.match(/```\s*([\s\S]*?)```/i);
  if (fenced?.[1]) candidates.push(fenced[1].trim());

  const firstBrace = raw.indexOf("{");
  const lastBrace = raw.lastIndexOf("}");
  if (firstBrace >= 0 && lastBrace > firstBrace) {
    candidates.push(raw.slice(firstBrace, lastBrace + 1).trim());
  }

  return [...new Set(candidates)];
}

function normalizeStructuredResult(
  parsed: Record<string, unknown>,
  fallbackTarget?: string
): StructuredResult | null {
  const target =
    typeof parsed.target === "string"
      ? parsed.target
      : typeof parsed.target_field === "string"
        ? parsed.target_field
        : fallbackTarget;

  if (!target) return null;

  return {
    target,
    value: "value" in parsed ? parsed.value : parsed,
    summary: typeof parsed.summary === "string" ? parsed.summary : undefined,
    missing_keys: Array.isArray(parsed.missing_keys)
      ? parsed.missing_keys.map(String)
      : undefined,
  };
}

export function parseStructuredResult(
  raw: string,
  options?: {
    allowedTargets?: string[];
    fallbackTarget?: string;
    validate?: StructuredResultValidator;
  }
): ParsedStructuredResult {
  const allowedTargets = options?.allowedTargets || [];

  for (const candidate of collectJsonCandidates(raw)) {
    try {
      const parsed = JSON.parse(candidate) as Record<string, unknown>;
      const result = normalizeStructuredResult(parsed, options?.fallbackTarget);
      if (!result) continue;
      if (allowedTargets.length > 0 && !allowedTargets.includes(result.target)) {
        return { result: null, missingKeys: ["target"] };
      }

      const validatorMissing = options?.validate?.(result.target, result.value) || [];
      const declaredMissing = result.missing_keys || [];
      const missingKeys = [...new Set([...declaredMissing, ...validatorMissing])];
      if (missingKeys.length > 0) {
        return { result: null, missingKeys };
      }

      return { result, missingKeys: [] };
    } catch {
      continue;
    }
  }

  return { result: null, missingKeys: [] };
}
