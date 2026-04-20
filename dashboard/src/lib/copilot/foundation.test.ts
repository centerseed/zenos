import { describe, expect, it } from "vitest";
import { buildCopilotPromptEnvelope } from "@/lib/copilot/envelope";
import { getCopilotConversationKey, nextCopilotStatus, usesScopedResume } from "@/lib/copilot/state";
import { parseStructuredResult } from "@/lib/copilot/structured-result";
import { parseStreamLine } from "@/lib/copilot/stream";
import type { CopilotEntryConfig } from "@/lib/copilot/types";

function makeEntry(overrides?: Partial<CopilotEntryConfig>): CopilotEntryConfig {
  return {
    intent_id: "marketing.strategy",
    title: "策略設定",
    mode: "apply",
    launch_behavior: "manual",
    session_policy: "scoped_resume",
    scope: {
      project: "paceriz",
      campaign_id: "proj-1",
      scope_label: "Paceriz / 策略",
    },
    context_pack: {
      field_id: "strategy",
      project_summary: "Paceriz / 官網 Blog",
    },
    write_targets: ["marketing_strategy"],
    build_prompt: (input) => `請根據輸入調整策略：${input}`,
    ...overrides,
  };
}

describe("copilot state", () => {
  it("uses the shared 7-state transitions", () => {
    expect(nextCopilotStatus("idle", "send")).toBe("loading");
    expect(nextCopilotStatus("loading", "message")).toBe("streaming");
    expect(nextCopilotStatus("streaming", "permission_request")).toBe("awaiting-local-approval");
    expect(nextCopilotStatus("awaiting-local-approval", "permission_result")).toBe("streaming");
    expect(nextCopilotStatus("streaming", "apply_available")).toBe("apply-ready");
    expect(nextCopilotStatus("apply-ready", "apply_start")).toBe("applying");
    expect(nextCopilotStatus("applying", "apply_done")).toBe("idle");
    expect(nextCopilotStatus("streaming", "error")).toBe("error");
  });

  it("derives a stable scoped conversation key", () => {
    const entry = makeEntry({
      scope: {
        workspace_id: "ws-1",
        project: "paceriz",
        campaign_id: "proj-1",
        entity_ids: ["entity-a", "entity-b"],
        scope_label: "Paceriz / 策略",
      },
    });
    expect(getCopilotConversationKey(entry)).toBe(
      "marketing.strategy:ws-1:paceriz:proj-1:entity-a,entity-b"
    );
    expect(usesScopedResume(entry)).toBe(true);
  });
});

describe("copilot envelope", () => {
  it("wraps prompt body with metadata and scope sections", () => {
    const envelope = buildCopilotPromptEnvelope(makeEntry(), "請聚焦跑步新手");
    expect(envelope).toContain("[AI_RAIL]");
    expect(envelope).toContain("intent_id=marketing.strategy");
    expect(envelope).toContain("[SCOPE]");
    expect(envelope).toContain("campaign_id=proj-1");
    expect(envelope).toContain("[CONTEXT_PACK]");
    expect(envelope).toContain('"field_id": "strategy"');
    expect(envelope).toContain("[TASK_PROMPT]");
  });
});

describe("structured result parser", () => {
  it("parses fenced json and validates allowed targets", () => {
    const raw = [
      "先調整語氣。",
      "```json",
      '{"target":"marketing_strategy","value":{"tone":"更直接"}}',
      "```",
    ].join("\n");
    const parsed = parseStructuredResult(raw, {
      allowedTargets: ["marketing_strategy"],
      validate: (_target, value) => {
        const record = value as Record<string, unknown>;
        return typeof record.tone === "string" ? [] : ["tone"];
      },
    });
    expect(parsed.missingKeys).toEqual([]);
    expect(parsed.result).toEqual({
      target: "marketing_strategy",
      value: { tone: "更直接" },
      summary: undefined,
      missing_keys: undefined,
    });
  });

  it("rejects results outside the write target whitelist", () => {
    const parsed = parseStructuredResult('{"target":"crm_briefing","value":{"title":"x"}}', {
      allowedTargets: ["marketing_strategy"],
    });
    expect(parsed.result).toBeNull();
    expect(parsed.missingKeys).toEqual(["target"]);
  });

  it("returns missing keys when validator fails", () => {
    const parsed = parseStructuredResult('{"target":"marketing_prompt_draft","value":{"content":"x"}}', {
      allowedTargets: ["marketing_prompt_draft"],
      validate: () => ["version"],
    });
    expect(parsed.result).toBeNull();
    expect(parsed.missingKeys).toEqual(["version"]);
  });
});

describe("parseStreamLine", () => {
  it("returns empty delta and debug for empty string", () => {
    expect(parseStreamLine("")).toEqual({ delta: "", debug: "" });
  });

  it("extracts delta.text", () => {
    expect(parseStreamLine('{"delta":{"text":"hello"}}')).toEqual({ delta: "hello", debug: "" });
  });

  it("extracts top-level text", () => {
    expect(parseStreamLine('{"text":"world"}')).toEqual({ delta: "world", debug: "" });
  });

  it("extracts content_block_delta.text", () => {
    expect(parseStreamLine('{"content_block_delta":{"text":"chunk"}}')).toEqual({ delta: "chunk", debug: "" });
  });

  it("extracts nested message.content[0].text", () => {
    expect(parseStreamLine('{"message":{"content":[{"text":"nested"}]}}')).toEqual({ delta: "nested", debug: "" });
  });

  it("extracts nested stream_event payload", () => {
    expect(
      parseStreamLine('{"type":"stream_event","event":{"message":{"content":[{"content":{"text":"nested stream"}}]}}}')
    ).toEqual({ delta: "nested stream", debug: "" });
  });

  it("passes through structured result (target_field + value) as raw JSON in delta", () => {
    const raw = '{"target_field":"strategy","value":{"tone":"直接"}}';
    const result = parseStreamLine(raw);
    expect(result.delta).toBe(raw);
    expect(result.debug).toBe("");
  });

  it("emits debug message for non-delta type events with content_block type suffix", () => {
    expect(
      parseStreamLine('{"type":"content_block_start","content_block":{"type":"text"}}')
    ).toEqual({ delta: "", debug: "事件：content_block_start (text)" });
  });

  it("silently ignores delta-type events (debug empty)", () => {
    expect(parseStreamLine('{"type":"content_block_delta"}')).toEqual({ delta: "", debug: "" });
  });

  it("returns non-JSON string as debug", () => {
    expect(parseStreamLine("hello raw")).toEqual({ delta: "", debug: "hello raw" });
  });
});
