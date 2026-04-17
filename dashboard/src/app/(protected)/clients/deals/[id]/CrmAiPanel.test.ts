/**
 * Unit tests for CrmAiPanel helper functions.
 * Tests the pure logic extracted from the component:
 * - parseSseLineForDelta: SSE line parsing
 * - buildActivitiesSummary: activity summary truncation
 * - extractFollowUpDraft: follow-up section extraction from AI markdown
 * - DEBRIEF_TRIGGER_TYPES: correct activity types trigger debrief
 */

import { describe, it, expect } from "vitest";

// ─── Inline the pure functions from CrmAiPanel for testing ───────────────────
// These are tested independently without rendering the React component.

function parseSseLineForDelta(line: string): string {
  const raw = line.trim();
  if (!raw) return "";
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const type = typeof parsed.type === "string" ? parsed.type : "";
    const inner = type === "stream_event" && parsed.event && typeof parsed.event === "object"
      ? parsed.event as Record<string, unknown>
      : parsed;
    const candidates: unknown[] = [
      (inner.delta as Record<string, unknown> | undefined)?.text,
      (inner.content_block_delta as Record<string, unknown> | undefined)?.text,
      inner.text,
      (inner.content_block as Record<string, unknown> | undefined)?.text,
      (parsed.delta as Record<string, unknown> | undefined)?.text,
      parsed.text,
    ];
    for (const obj of [inner, parsed]) {
      const messageObj = obj.message as Record<string, unknown> | undefined;
      const messageContent = Array.isArray(messageObj?.content) ? messageObj.content : null;
      if (messageContent && messageContent.length > 0) {
        const first = messageContent[0] as Record<string, unknown>;
        candidates.push(first?.text);
      }
    }
    for (const candidate of candidates) {
      if (typeof candidate === "string" && candidate.trim().length > 0) {
        return candidate;
      }
    }
    return "";
  } catch {
    return raw;
  }
}

function buildActivitiesSummary(activities: Array<{ activityAt: Date; activityType: string; summary: string; isSystem: boolean }>): string {
  const sorted = [...activities]
    .filter((a) => !a.isSystem)
    .sort((a, b) => b.activityAt.getTime() - a.activityAt.getTime())
    .slice(0, 10);

  const lines = sorted.map((a) => {
    const dateStr = a.activityAt.toLocaleDateString("zh-TW", { year: "numeric", month: "2-digit", day: "2-digit" });
    return `[${dateStr}] ${a.activityType}: ${a.summary}`;
  });

  let result = lines.join("\n");
  if (result.length > 1500) result = result.slice(0, 1497) + "...";
  return result;
}

interface FollowUpDraft {
  line: string;
  email: { subject: string; body: string };
}

function extractFollowUpDraft(markdown: string): FollowUpDraft | null {
  const lineMatch = markdown.match(/##\s*(?:LINE|Line|line)[^\n]*\n([\s\S]*?)(?=##|$)/);
  const emailMatch = markdown.match(/##\s*(?:Email|email|電子郵件|郵件)[^\n]*\n([\s\S]*?)(?=##|$)/);

  if (!lineMatch && !emailMatch) return null;

  const lineContent = lineMatch ? lineMatch[1].trim() : "";

  let emailSubject = "";
  let emailBody = "";
  if (emailMatch) {
    const emailContent = emailMatch[1].trim();
    const subjectMatch = emailContent.match(/(?:\*\*主旨[:：]\*\*|主旨[:：])\s*(.+)/);
    if (subjectMatch) {
      emailSubject = subjectMatch[1].trim();
      emailBody = emailContent.replace(subjectMatch[0], "").trim();
    } else {
      const lines = emailContent.split("\n");
      emailSubject = lines[0].replace(/^[*#\-\s]+/, "").trim();
      emailBody = lines.slice(1).join("\n").trim();
    }
  }

  return {
    line: lineContent,
    email: { subject: emailSubject, body: emailBody },
  };
}

const DEBRIEF_TRIGGER_TYPES = new Set(["會議", "Demo", "電話"]);

// ─── Tests ───────────────────────────────────────────────────────────────────

describe("parseSseLineForDelta", () => {
  it("returns empty string for empty input", () => {
    expect(parseSseLineForDelta("")).toBe("");
    expect(parseSseLineForDelta("   ")).toBe("");
  });

  it("extracts text from delta.text format", () => {
    const line = JSON.stringify({ type: "content_block_delta", delta: { type: "text_delta", text: "Hello" } });
    expect(parseSseLineForDelta(line)).toBe("Hello");
  });

  it("extracts text from content_block_delta.text format", () => {
    const line = JSON.stringify({ content_block_delta: { text: "World" } });
    expect(parseSseLineForDelta(line)).toBe("World");
  });

  it("extracts text from top-level text field", () => {
    const line = JSON.stringify({ text: "Top level" });
    expect(parseSseLineForDelta(line)).toBe("Top level");
  });

  it("extracts text from message.content[0].text format", () => {
    const line = JSON.stringify({ message: { content: [{ text: "Message content" }] } });
    expect(parseSseLineForDelta(line)).toBe("Message content");
  });

  it("returns empty string for JSON with no text fields", () => {
    const line = JSON.stringify({ type: "message_start", message: { role: "assistant" } });
    expect(parseSseLineForDelta(line)).toBe("");
  });

  it("returns raw line for non-JSON input (treats as debug line)", () => {
    expect(parseSseLineForDelta("plain text")).toBe("plain text");
  });

  it("skips empty text fields and uses next candidate", () => {
    const line = JSON.stringify({ delta: { text: "" }, content_block_delta: { text: "fallback" } });
    expect(parseSseLineForDelta(line)).toBe("fallback");
  });

  it("extracts text from stream_event wrapper (Claude CLI format)", () => {
    const line = JSON.stringify({
      type: "stream_event",
      event: { type: "content_block_delta", index: 0, delta: { type: "text_delta", text: "wrapped text" } },
      session_id: "test",
    });
    expect(parseSseLineForDelta(line)).toBe("wrapped text");
  });

  it("returns empty for stream_event with no text (e.g. message_start)", () => {
    const line = JSON.stringify({
      type: "stream_event",
      event: { type: "message_start", message: { role: "assistant", content: [] } },
    });
    expect(parseSseLineForDelta(line)).toBe("");
  });

  it("extracts text from assistant message wrapper", () => {
    const line = JSON.stringify({
      type: "assistant",
      message: { content: [{ type: "text", text: "full response" }] },
    });
    expect(parseSseLineForDelta(line)).toBe("full response");
  });
});

describe("buildActivitiesSummary", () => {
  const makeActivity = (overrides: Partial<{ activityAt: Date; activityType: string; summary: string; isSystem: boolean }>) => ({
    activityAt: new Date("2026-01-15"),
    activityType: "會議",
    summary: "meeting summary",
    isSystem: false,
    ...overrides,
  });

  it("returns empty string for empty activities", () => {
    expect(buildActivitiesSummary([])).toBe("");
  });

  it("filters out system activities", () => {
    const activities = [
      makeActivity({ isSystem: true, summary: "system event" }),
      makeActivity({ isSystem: false, summary: "user meeting" }),
    ];
    const result = buildActivitiesSummary(activities);
    expect(result).not.toContain("system event");
    expect(result).toContain("user meeting");
  });

  it("sorts activities newest first", () => {
    const activities = [
      makeActivity({ activityAt: new Date("2026-01-10"), summary: "older" }),
      makeActivity({ activityAt: new Date("2026-01-20"), summary: "newer" }),
    ];
    const result = buildActivitiesSummary(activities);
    const newerIndex = result.indexOf("newer");
    const olderIndex = result.indexOf("older");
    expect(newerIndex).toBeLessThan(olderIndex);
  });

  it("truncates to 1500 characters with ellipsis", () => {
    const longSummary = "A".repeat(200);
    const activities = Array.from({ length: 10 }, (_, i) =>
      makeActivity({ activityAt: new Date(2026, 0, i + 1), summary: longSummary })
    );
    const result = buildActivitiesSummary(activities);
    expect(result.length).toBeLessThanOrEqual(1500);
    expect(result.endsWith("...")).toBe(true);
  });

  it("limits to 10 activities", () => {
    const activities = Array.from({ length: 15 }, (_, i) =>
      makeActivity({ activityAt: new Date(2026, 0, i + 1), summary: `activity-${i}` })
    );
    const result = buildActivitiesSummary(activities);
    // Only 10 should appear; activity-0 through activity-4 (oldest) should be absent
    expect((result.match(/activity-/g) ?? []).length).toBeLessThanOrEqual(10);
  });
});

describe("extractFollowUpDraft", () => {
  it("returns null when no LINE or Email sections found", () => {
    const markdown = "## 本次重點\n\n討論了預算問題。\n\n## 下一步\n\n安排提案。";
    expect(extractFollowUpDraft(markdown)).toBeNull();
  });

  it("extracts LINE section content", () => {
    const markdown = "## LINE\n\n嗨，感謝今天的會議！\n\n如有問題歡迎聯繫。\n\n## Email\n\n主旨：後續確認\n\n正文。";
    const result = extractFollowUpDraft(markdown);
    expect(result).not.toBeNull();
    expect(result!.line).toContain("嗨，感謝今天的會議");
  });

  it("extracts Email section with 主旨 pattern", () => {
    const markdown = "## LINE\n\nLine content.\n\n## Email\n\n主旨：會議後續\n\n感謝您今天撥冗。";
    const result = extractFollowUpDraft(markdown);
    expect(result).not.toBeNull();
    expect(result!.email.subject).toBe("會議後續");
    expect(result!.email.body).toContain("感謝您今天撥冗");
  });

  it("handles Email section without 主旨 prefix — uses first line as subject", () => {
    const markdown = "## Email\n\n後續確認事項\n\n本次會議決定...";
    const result = extractFollowUpDraft(markdown);
    expect(result).not.toBeNull();
    expect(result!.email.subject).toBe("後續確認事項");
    expect(result!.email.body).toContain("本次會議決定");
  });

  it("returns LINE content only when Email section is absent", () => {
    const markdown = "## LINE\n\nQuick message here.";
    const result = extractFollowUpDraft(markdown);
    expect(result).not.toBeNull();
    expect(result!.line).toBe("Quick message here.");
    expect(result!.email.subject).toBe("");
    expect(result!.email.body).toBe("");
  });

  it("handles case-insensitive LINE heading variants", () => {
    const markdown = "## Line Follow-up\n\nContent here.";
    const result = extractFollowUpDraft(markdown);
    expect(result).not.toBeNull();
    expect(result!.line).toContain("Content here");
  });
});

describe("DEBRIEF_TRIGGER_TYPES", () => {
  it("triggers debrief for 會議", () => {
    expect(DEBRIEF_TRIGGER_TYPES.has("會議")).toBe(true);
  });

  it("triggers debrief for Demo", () => {
    expect(DEBRIEF_TRIGGER_TYPES.has("Demo")).toBe(true);
  });

  it("triggers debrief for 電話", () => {
    expect(DEBRIEF_TRIGGER_TYPES.has("電話")).toBe(true);
  });

  it("does NOT trigger debrief for 備忘", () => {
    expect(DEBRIEF_TRIGGER_TYPES.has("備忘")).toBe(false);
  });

  it("does NOT trigger debrief for Email", () => {
    expect(DEBRIEF_TRIGGER_TYPES.has("Email")).toBe(false);
  });

  it("does NOT trigger debrief for 系統", () => {
    expect(DEBRIEF_TRIGGER_TYPES.has("系統")).toBe(false);
  });
});
