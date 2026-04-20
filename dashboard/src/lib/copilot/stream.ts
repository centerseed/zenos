export interface ParsedStreamLine {
  delta: string;
  debug: string;
}

export function parseStreamLine(line: string): ParsedStreamLine {
  const raw = line.trim();
  if (!raw) return { delta: "", debug: "" };
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    if ("target_field" in parsed && "value" in parsed) {
      return { delta: raw, debug: "" };
    }
    const type = typeof parsed.type === "string" ? parsed.type : "";
    const inner =
      type === "stream_event" && parsed.event && typeof parsed.event === "object"
        ? (parsed.event as Record<string, unknown>)
        : parsed;
    const innerType = typeof inner.type === "string" ? inner.type : type;
    const candidates: unknown[] = [
      (inner.delta as Record<string, unknown> | undefined)?.text,
      (inner.content_block_delta as Record<string, unknown> | undefined)?.text,
      inner.text,
      (inner.content_block as Record<string, unknown> | undefined)?.text,
      (inner.message as Record<string, unknown> | undefined)?.text,
      (parsed.delta as Record<string, unknown> | undefined)?.text,
      (parsed.content_block_delta as Record<string, unknown> | undefined)?.text,
      parsed.text,
      (parsed.content_block as Record<string, unknown> | undefined)?.text,
      (parsed.message as Record<string, unknown> | undefined)?.text,
    ];
    for (const obj of [inner, parsed]) {
      const messageObj = obj.message as Record<string, unknown> | undefined;
      const messageContent = Array.isArray(messageObj?.content) ? messageObj?.content : null;
      if (messageContent && messageContent.length > 0) {
        const first = messageContent[0] as Record<string, unknown>;
        candidates.push(first?.text);
        const nested = first?.content as Record<string, unknown> | undefined;
        candidates.push(nested?.text);
      }
    }
    for (const candidate of candidates) {
      if (typeof candidate === "string" && candidate.trim().length > 0) {
        return { delta: candidate, debug: "" };
      }
    }
    if (innerType) {
      if (innerType.includes("delta")) return { delta: "", debug: "" };
      const blockType =
        (inner.content_block as Record<string, unknown> | undefined)?.type ||
        (inner.delta as Record<string, unknown> | undefined)?.type ||
        (parsed.content_block as Record<string, unknown> | undefined)?.type ||
        (parsed.delta as Record<string, unknown> | undefined)?.type ||
        "";
      const suffix = typeof blockType === "string" && blockType ? ` (${blockType})` : "";
      return { delta: "", debug: `事件：${innerType}${suffix}` };
    }
    return { delta: "", debug: "" };
  } catch {
    return { delta: "", debug: raw };
  }
}
