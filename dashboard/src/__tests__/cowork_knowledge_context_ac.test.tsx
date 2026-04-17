import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockGetCoworkGraphContext = vi.fn();

vi.mock("@/lib/api", () => ({
  getCoworkGraphContext: (...args: unknown[]) => mockGetCoworkGraphContext(...args),
}));

import { GraphContextBadge } from "@/components/ai/GraphContextBadge";
import {
  buildCrmKnowledgePrompt,
  buildMarketingKnowledgePrompt,
  COWORK_MAX_TURNS,
  graphContextUnavailableNotice,
  MARKETING_STRATEGY_TARGET_FIELDS,
  normalizeSourceCitations,
} from "@/lib/cowork-knowledge";
import {
  clearGraphContextCache,
  createGraphContextLoadedPayload,
  fetchGraphContext,
} from "@/lib/graph-context";

const baseGraphContext = {
  seed: {
    id: "prod-1",
    name: "Paceriz",
    type: "product",
    level: 1,
    status: "active",
    summary: "跑步知識產品",
    tags: { what: ["跑步"], why: "建立習慣", how: "", who: ["新手"] },
  },
  fallback_mode: "normal" as const,
  neighbors: [
    {
      id: "module-1",
      name: "Audience Engine",
      type: "module",
      level: 2,
      status: "active",
      summary: "鎖定跑步新手",
      tags: { what: ["受眾"], why: "提高命中率", how: "", who: ["新手"] },
      distance: 1,
      documents: [
        {
          id: "doc-1",
          doc_id: "doc-1",
          title: "SPEC Audience",
          type: "spec",
          status: "approved",
          summary: "說明目標受眾",
        },
      ],
    },
  ],
  partial: false,
  errors: [],
  truncated: false,
  truncation_details: { dropped_l2: 0, dropped_l3: 0, summary_truncated: 0 },
  estimated_tokens: 120,
  cached_at: new Date("2026-04-15T00:00:00Z"),
};

const strategyField = {
  fieldId: "strategy",
  fieldLabel: "策略設定",
  currentPhase: "strategy",
  projectSummary: "官網 Blog / 長期經營",
  fieldValue: { audience: ["跑步新手"] },
  relatedContext: "上輪摘要",
};

describe("SPEC-cowork-knowledge-context AC (frontend)", () => {
  beforeEach(() => {
    clearGraphContextCache();
    mockGetCoworkGraphContext.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("AC-CKC-02: pre-first-turn traversal injects graph_context into prompt", () => {
    const prompt = buildMarketingKnowledgePrompt(strategyField, "", {
      graphContext: baseGraphContext,
      targetFields: MARKETING_STRATEGY_TARGET_FIELDS,
    });
    expect(prompt).toContain("graph_context=");
    expect(prompt).toContain("Audience Engine");
    expect(prompt).toContain("target_fields=");
  });

  it("AC-CKC-03: no seed_entity → no traversal, prompt has no graph_context", async () => {
    const result = await fetchGraphContext("token", { seedId: null });
    expect(result).toBeNull();
    expect(mockGetCoworkGraphContext).not.toHaveBeenCalled();
  });

  it("AC-CKC-04: mcp_ok=false → UI shows degraded notice, chat still works", () => {
    expect(graphContextUnavailableNotice()).toContain("知識圖譜暫時無法讀取");
  });

  it("AC-CKC-14: graph_context_loaded event dispatched with l2_count/l3_count", () => {
    expect(createGraphContextLoadedPayload(baseGraphContext)).toEqual({
      l2_count: 1,
      l3_count: 1,
      truncated: false,
      fallback_mode: "normal",
    });
  });

  it("AC-CKC-15: within 60s same seed → uses session cache, no duplicate fetch", async () => {
    mockGetCoworkGraphContext.mockResolvedValue(baseGraphContext);
    const first = await fetchGraphContext("token", { seedId: "prod-1" });
    const second = await fetchGraphContext("token", { seedId: "prod-1" });
    expect(first).toEqual(baseGraphContext);
    expect(second).toEqual(baseGraphContext);
    expect(mockGetCoworkGraphContext).toHaveBeenCalledTimes(1);
  });

  it("AC-CKC-20: GraphContextBadge default collapsed with summary text", () => {
    render(<GraphContextBadge graphContext={baseGraphContext} />);
    const summary = screen.getByText("已讀取 1 個模組、1 個文件 ▸");
    expect(summary).toBeInTheDocument();
    expect(summary.closest("details")).not.toHaveAttribute("open");
  });

  it("AC-CKC-21: GraphContextBadge expanded shows seed → L2 → L3 hierarchy", () => {
    render(<GraphContextBadge graphContext={baseGraphContext} />);
    const details = screen.getByText("已讀取 1 個模組、1 個文件 ▸").closest("details");
    details?.setAttribute("open", "");
    expect(screen.getByText("Paceriz")).toBeInTheDocument();
    expect(screen.getByText(/Audience Engine/)).toBeInTheDocument();
    expect(screen.getByText(/SPEC Audience/)).toBeInTheDocument();
    expect(screen.queryByText(/graph_context=/)).not.toBeInTheDocument();
  });

  it("AC-CKC-22: truncated=true → shows 'N more nodes not loaded' notice", () => {
    render(
      <GraphContextBadge
        graphContext={{
          ...baseGraphContext,
          truncated: true,
          truncation_details: { dropped_l2: 1, dropped_l3: 2, summary_truncated: 0 },
        }}
      />
    );
    expect(screen.getByText("還有 3 個節點因長度限制未載入")).toBeInTheDocument();
  });

  it("AC-CKC-23: graph_context unavailable → badge hidden or replaced with degraded notice", () => {
    render(<GraphContextBadge graphContext={null} unavailableReason="知識圖譜暫時無法讀取" />);
    expect(screen.getByText("知識圖譜暫時無法讀取")).toBeInTheDocument();
    expect(screen.queryByText(/已讀取/)).not.toBeInTheDocument();
  });

  it("AC-CKC-30: first-turn reply cites specific graph_context nodes", () => {
    const prompt = buildMarketingKnowledgePrompt(strategyField, "", { graphContext: baseGraphContext });
    expect(prompt).toContain("Audience Engine");
    expect(prompt).toContain("source_citations");
  });

  it("AC-CKC-31: no evidence → marks 'insufficient basis', no fabrication", () => {
    const prompt = buildMarketingKnowledgePrompt(strategyField, "", {
      graphContext: { ...baseGraphContext, fallback_mode: "l1_tags_only", neighbors: [] },
    });
    expect(prompt).toContain("不得捏造引用");
    expect(prompt).toContain("以下草案僅基於產品 tags");
  });

  it("AC-CKC-32: subsequent turns ask one user_required field per turn", () => {
    const prompt = buildMarketingKnowledgePrompt(strategyField, "", { graphContext: baseGraphContext });
    expect(prompt).toContain("每一輪最多只追問一個 user_required 欄位");
  });

  it("AC-CKC-33: 'skip' response marks field pending, moves on", () => {
    const prompt = buildMarketingKnowledgePrompt(strategyField, "", { graphContext: baseGraphContext });
    expect(prompt).toContain("先跳過");
    expect(prompt).toContain("pending_fields");
  });

  it("AC-CKC-34: apply payload conforms to target_field/value schema", () => {
    const prompt = buildMarketingKnowledgePrompt(strategyField, "", { graphContext: baseGraphContext });
    expect(prompt).toContain('"target_field":"strategy"');
    expect(prompt).toContain('"value"');
  });

  it("AC-CKC-35: turn 10 reached → show limit notice, no forced termination", () => {
    expect(COWORK_MAX_TURNS).toBe(10);
  });

  it("AC-CKC-41: l1_tags_only fallback → first reply contains explicit notice", () => {
    const prompt = buildMarketingKnowledgePrompt(strategyField, "", {
      graphContext: { ...baseGraphContext, fallback_mode: "l1_tags_only", neighbors: [] },
    });
    expect(prompt).toContain("目前只有基本產品資訊");
    expect(prompt).toContain("以下草案僅基於產品 tags");
  });

  it("AC-CKC-42: fallback mode → final summary marks confidence=low", () => {
    const prompt = buildMarketingKnowledgePrompt(strategyField, "", {
      graphContext: { ...baseGraphContext, fallback_mode: "l1_tags_only", neighbors: [] },
    });
    expect(prompt).toContain('confidence="low"');
  });

  it("AC-CKC-51: CRM briefing uses graph_context + shows GraphContextBadge", () => {
    const prompt = buildCrmKnowledgePrompt({
      promptLabel: "CRM briefing",
      baseContext: { deal_id: "deal-1" },
      graphContext: baseGraphContext,
    });
    render(<GraphContextBadge graphContext={baseGraphContext} />);
    expect(prompt).toContain("graph_context=");
    expect(prompt).toContain("Audience Engine");
    expect(screen.getByText("已讀取 1 個模組、1 個文件 ▸")).toBeInTheDocument();
  });

  it("AC-CKC-55: marketing strategy seed=product + target_fields with source_preference", () => {
    expect(MARKETING_STRATEGY_TARGET_FIELDS).toHaveLength(7);
    expect(MARKETING_STRATEGY_TARGET_FIELDS.some((field) => field.source_preference === "graph_derivable")).toBe(true);
    expect(MARKETING_STRATEGY_TARGET_FIELDS.some((field) => field.source_preference === "user_required")).toBe(true);
  });

  it("AC-CKC-56: applied strategy writes 3+ traceable field citations to ZenOS", () => {
    const citations = normalizeSourceCitations([
      { node_id: "module-1", node_name: "Audience Engine", field_ids: ["audience"] },
      { node_id: "module-2", node_name: "Message Engine", field_ids: ["tone"] },
      { node_id: "doc-1", node_name: "SPEC Audience", field_ids: ["core_message"] },
    ]);
    expect(citations).toHaveLength(3);
    expect(citations.map((item) => item.node_name)).toEqual([
      "Audience Engine",
      "Message Engine",
      "SPEC Audience",
    ]);
  });
});
