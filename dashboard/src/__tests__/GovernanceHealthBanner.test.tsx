/**
 * Tests for GovernanceHealthBanner component (ADR-021).
 *
 * Verifies:
 *   - green level renders nothing
 *   - yellow level shows correct message and guidance
 *   - red level shows correct message and guidance
 *   - copy button triggers clipboard write
 *   - no KPI terms or numbers are displayed
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import React from "react";
import { GovernanceHealthBanner } from "@/components/GovernanceHealthBanner";

describe("GovernanceHealthBanner", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
  });

  it("renders nothing when level is green", () => {
    const { container } = render(<GovernanceHealthBanner level="green" />);
    expect(container.innerHTML).toBe("");
  });

  it("shows yellow banner with correct message", () => {
    const { container } = render(<GovernanceHealthBanner level="yellow" />);
    expect(container.textContent).toContain("知識地圖有些內容可能需要整理");
    expect(container.textContent).toContain("/zenos-governance");
  });

  it("shows red banner with correct message", () => {
    const { container } = render(<GovernanceHealthBanner level="red" />);
    expect(container.textContent).toContain("知識地圖的品質可能正在影響 agent 的建議準確度");
    expect(container.textContent).toContain("/zenos-governance");
  });

  it("yellow banner includes auto-governance guidance text", () => {
    const { container } = render(<GovernanceHealthBanner level="yellow" />);
    const text = container.textContent || "";
    expect(text).toContain("請在 Claude Code 中執行");
    expect(text).toContain("進行自動治理");
  });

  it("red banner includes urgent guidance text", () => {
    const { container } = render(<GovernanceHealthBanner level="red" />);
    const text = container.textContent || "";
    expect(text).toContain("建議儘快在 Claude Code 中執行");
  });

  it("copies command to clipboard on button click", async () => {
    const { container } = render(<GovernanceHealthBanner level="yellow" />);
    const button = container.querySelector("button");
    expect(button).toBeTruthy();
    fireEvent.click(button!);
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("/zenos-governance");
  });

  it("does not display any KPI terms or numbers", () => {
    const { container } = render(<GovernanceHealthBanner level="red" />);
    const text = container.textContent || "";
    expect(text).not.toContain("KPI");
    expect(text).not.toContain("quality_score");
    expect(text).not.toContain("entity");
    expect(text).not.toContain("ontology");
  });
});
