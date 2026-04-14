/**
 * Unit tests for pure parsing functions in DealDetailClient.
 *
 * These are tested independently (inlined) because the functions are
 * not exported from the React component file. TDD approach: each test
 * verifies real parsing logic against representative AI output formats.
 */

import { describe, it, expect } from "vitest";

// ─── Inline the pure functions under test ─────────────────────────────────────
// (They live in DealDetailClient.tsx but are not exported.
//  We inline them here to test deterministically without React deps.)

function extractDebriefMetadata(text: string): Record<string, unknown> {
  const metadata: Record<string, unknown> = {};

  const decisionsMatch = text.match(/##\s*關鍵決策\s*\n([\s\S]*?)(?=\n##|\n$|$)/);
  if (decisionsMatch) {
    metadata.key_decisions = decisionsMatch[1]
      .split("\n")
      .filter((l) => l.trim().startsWith("-"))
      .map((l) => l.replace(/^-\s*/, "").trim())
      .filter(Boolean);
  }

  const concernsMatch = text.match(/##\s*客戶顧慮\s*\n([\s\S]*?)(?=\n##|\n$|$)/);
  if (concernsMatch) {
    metadata.customer_concerns = concernsMatch[1]
      .split("\n")
      .filter((l) => l.trim().startsWith("-"))
      .map((l) => l.replace(/^-\s*/, "").trim())
      .filter(Boolean);
  }

  const nextStepsMatch = text.match(/##\s*下一步行動\s*\n([\s\S]*?)(?=\n##|\n$|$)/);
  if (nextStepsMatch) {
    metadata.next_steps = nextStepsMatch[1]
      .split("\n")
      .filter((l) => l.trim().startsWith("-"))
      .map((l) => l.replace(/^-\s*/, "").trim())
      .filter(Boolean);
  }

  const stageMatch = text.match(/##\s*階段建議\s*\n([\s\S]*?)(?=\n##|\n$|$)/);
  if (stageMatch) {
    metadata.stage_recommendation = stageMatch[1].trim();
  }

  const lineMatch = text.match(/##\s*(?:LINE|Line|line)[^\n]*\n([\s\S]*?)(?=##|$)/);
  const emailMatch = text.match(/##\s*(?:Email|email|電子郵件|郵件)[^\n]*\n([\s\S]*?)(?=##|$)/);

  if (lineMatch || emailMatch) {
    const followUp: Record<string, unknown> = {
      line: lineMatch ? lineMatch[1].trim() : "",
    };
    if (emailMatch) {
      const emailContent = emailMatch[1].trim();
      const subjectMatch = emailContent.match(/(?:\*\*主旨[:：]\*\*|主旨[:：])\s*(.+)/);
      if (subjectMatch) {
        followUp.email = {
          subject: subjectMatch[1].trim(),
          body: emailContent.replace(subjectMatch[0], "").trim(),
        };
      } else {
        const lines = emailContent.split("\n");
        followUp.email = {
          subject: lines[0].replace(/^[*#\-\s]+/, "").trim(),
          body: lines.slice(1).join("\n").trim(),
        };
      }
    }
    metadata.follow_up = followUp;
  }

  return metadata;
}

interface CommitmentRaw {
  content: string;
  owner: "us" | "customer";
  deadline?: string;
}

function extractCommitments(text: string): CommitmentRaw[] {
  const commitments: CommitmentRaw[] = [];

  const sectionMatch = text.match(/##\s*承諾事項\s*\n([\s\S]*?)(?=\n##|\n$|$)/);
  if (!sectionMatch) return commitments;

  const section = sectionMatch[1];

  const ourMatch = section.match(/我方承諾[：:]\s*\n([\s\S]*?)(?=客戶承諾|$)/);
  const customerMatch = section.match(/客戶承諾[：:]\s*\n([\s\S]*?)(?=$)/);

  function parseItems(block: string, owner: "us" | "customer"): CommitmentRaw[] {
    return block
      .split("\n")
      .filter((l) => l.trim().startsWith("-"))
      .map((l) => {
        const raw = l.replace(/^-\s*/, "").trim();
        const deadlineMatch = raw.match(/[—–-]\s*預期時間[：:]\s*(.+)$/);
        const content = deadlineMatch
          ? raw.replace(deadlineMatch[0], "").trim()
          : raw;
        return {
          content,
          owner,
          ...(deadlineMatch ? { deadline: deadlineMatch[1].trim() } : {}),
        };
      })
      .filter((c) => c.content.length > 0);
  }

  if (ourMatch) commitments.push(...parseItems(ourMatch[1], "us"));
  if (customerMatch) commitments.push(...parseItems(customerMatch[1], "customer"));

  return commitments;
}

// ─── extractDebriefMetadata tests ────────────────────────────────────────────

describe("extractDebriefMetadata", () => {
  it("returns empty object for text with no known sections", () => {
    const result = extractDebriefMetadata("一些隨機文字，沒有 ## 標題。");
    expect(result).toEqual({});
  });

  it("extracts key_decisions from ## 關鍵決策 section", () => {
    const text = "## 關鍵決策\n- 決定採用方案 A\n- 預算上限 50 萬\n\n## 其他";
    const result = extractDebriefMetadata(text);
    expect(result.key_decisions).toEqual(["決定採用方案 A", "預算上限 50 萬"]);
  });

  it("extracts customer_concerns from ## 客戶顧慮 section", () => {
    const text = "## 客戶顧慮\n- 上線時間太緊\n- 資安合規問題\n";
    const result = extractDebriefMetadata(text);
    expect(result.customer_concerns).toEqual(["上線時間太緊", "資安合規問題"]);
  });

  it("extracts next_steps from ## 下一步行動 section", () => {
    const text = "## 下一步行動\n- 寄報價單\n- 安排第二次會議\n";
    const result = extractDebriefMetadata(text);
    expect(result.next_steps).toEqual(["寄報價單", "安排第二次會議"]);
  });

  it("extracts stage_recommendation from ## 階段建議 section", () => {
    const text = "## 階段建議\n建議推進至「提案報價」階段。\n";
    const result = extractDebriefMetadata(text);
    expect(result.stage_recommendation).toBe("建議推進至「提案報價」階段。");
  });

  it("filters out non-list lines in section content", () => {
    const text = "## 關鍵決策\n一些說明文字\n- 有效決策\n空白行\n- 另一個決策\n";
    const result = extractDebriefMetadata(text);
    expect(result.key_decisions).toEqual(["有效決策", "另一個決策"]);
  });

  it("handles multiple sections in one text", () => {
    const text = [
      "## 關鍵決策",
      "- 決策 A",
      "",
      "## 客戶顧慮",
      "- 顧慮 X",
      "",
      "## 下一步行動",
      "- 行動 1",
      "",
      "## 階段建議",
      "維持現況。",
    ].join("\n");

    const result = extractDebriefMetadata(text);
    expect(result.key_decisions).toEqual(["決策 A"]);
    expect(result.customer_concerns).toEqual(["顧慮 X"]);
    expect(result.next_steps).toEqual(["行動 1"]);
    expect(result.stage_recommendation).toBe("維持現況。");
  });

  it("extracts follow_up when LINE section is present", () => {
    const text = "## LINE\n\n嗨，感謝今天的會議！\n\n## Email\n\n主旨：後續確認\n\n內容文字。";
    const result = extractDebriefMetadata(text);
    expect(result.follow_up).toBeDefined();
    const fu = result.follow_up as Record<string, unknown>;
    expect(fu.line).toContain("嗨，感謝今天的會議");
  });

  it("returns empty arrays for sections with no list items", () => {
    const text = "## 關鍵決策\n沒有列點，只有文字。\n";
    const result = extractDebriefMetadata(text);
    expect(result.key_decisions).toEqual([]);
  });
});

// ─── extractCommitments tests ─────────────────────────────────────────────────

describe("extractCommitments", () => {
  it("returns empty array when no 承諾事項 section exists", () => {
    expect(extractCommitments("## 關鍵決策\n- 決策 A")).toEqual([]);
  });

  it("returns empty array for empty 承諾事項 section", () => {
    const text = "## 承諾事項\n\n";
    expect(extractCommitments(text)).toEqual([]);
  });

  it("parses our-side commitments with deadline", () => {
    const text = [
      "## 承諾事項",
      "我方承諾：",
      "- 寄報價單 — 預期時間：2026-03-20",
      "- 安排 Demo — 預期時間：2026-03-25",
    ].join("\n");

    const result = extractCommitments(text);
    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({
      content: "寄報價單",
      owner: "us",
      deadline: "2026-03-20",
    });
    expect(result[1]).toEqual({
      content: "安排 Demo",
      owner: "us",
      deadline: "2026-03-25",
    });
  });

  it("parses customer commitments with deadline", () => {
    const text = [
      "## 承諾事項",
      "客戶承諾：",
      "- 確認內部預算 — 預期時間：2026-04-01",
    ].join("\n");

    const result = extractCommitments(text);
    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({
      content: "確認內部預算",
      owner: "customer",
      deadline: "2026-04-01",
    });
  });

  it("parses commitments without deadline", () => {
    const text = [
      "## 承諾事項",
      "我方承諾：",
      "- 準備投影片",
    ].join("\n");

    const result = extractCommitments(text);
    expect(result).toHaveLength(1);
    expect(result[0].content).toBe("準備投影片");
    expect(result[0].deadline).toBeUndefined();
  });

  it("parses both our and customer commitments from same section", () => {
    const text = [
      "## 承諾事項",
      "我方承諾：",
      "- 寄 NDA — 預期時間：2026-03-18",
      "客戶承諾：",
      "- 提供採購流程說明",
    ].join("\n");

    const result = extractCommitments(text);
    expect(result).toHaveLength(2);
    expect(result.find((c) => c.owner === "us")?.content).toBe("寄 NDA");
    expect(result.find((c) => c.owner === "customer")?.content).toBe("提供採購流程說明");
  });

  it("ignores non-list lines in commitment blocks", () => {
    const text = [
      "## 承諾事項",
      "我方承諾：",
      "以下是我方需要做的事情：",
      "- 有效承諾",
      "備注：這只是說明",
    ].join("\n");

    const result = extractCommitments(text);
    expect(result).toHaveLength(1);
    expect(result[0].content).toBe("有效承諾");
  });
});
