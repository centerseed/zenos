/**
 * Tests for OnboardingChecklist component — empty workspace onboarding flow.
 *
 * OB-1: Shows start button when workspace is empty and not dismissed
 * OB-2: Checklist displays 4 steps with correct statuses
 * OB-3: Step 2 auto-completes when partner exists
 * OB-4: Step 3 auto-completes when entities exist
 * OB-5: Manual steps (1/4) call onUpdatePrefs when marked done
 * OB-6: Dismiss calls onUpdatePrefs with dismissed=true
 * OB-7: Technical vs non-technical copy differentiation
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import React from "react";
import {
  OnboardingChecklist,
  OnboardingStartButton,
} from "@/components/OnboardingChecklist";

// Mock clipboard
Object.assign(navigator, {
  clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
});

afterEach(() => {
  cleanup();
});

// Mock next/link
vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

describe("OnboardingStartButton", () => {
  it("OB-1: renders start button and calls onClick", () => {
    const onClick = vi.fn();
    render(<OnboardingStartButton onClick={onClick} />);

    const button = screen.getByText("開始使用");
    expect(button).toBeDefined();

    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("OB-1: shows empty state message", () => {
    render(<OnboardingStartButton onClick={vi.fn()} />);
    expect(screen.getByText("你的知識地圖還是空的")).toBeDefined();
  });
});

describe("OnboardingChecklist", () => {
  const defaultProps = {
    hasPartner: true,
    hasEntities: false,
    onboardingPrefs: {},
    apiKey: "test-api-key-12345678", // pragma: allowlist secret
    onUpdatePrefs: vi.fn(),
    platformType: "non_technical" as const,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("OB-2: renders all 4 steps", () => {
    render(<OnboardingChecklist {...defaultProps} />);

    expect(screen.getByText("導向知識庫")).toBeDefined();
    expect(screen.getByText("設定 MCP + 安裝 Skills")).toBeDefined();
    expect(screen.getByText("捕捉知識")).toBeDefined();
    expect(screen.getByText("體驗 AI 角色")).toBeDefined();
  });

  it("OB-2: shows progress bar with correct count", () => {
    // hasPartner=true auto-completes Step 2 → 1/4
    render(<OnboardingChecklist {...defaultProps} />);
    expect(screen.getByText("1/4")).toBeDefined();
  });

  it("OB-3: Step 2 shows as completed when partner exists", () => {
    render(<OnboardingChecklist {...defaultProps} hasPartner={true} />);
    const step2Title = screen.getByText("設定 MCP + 安裝 Skills");
    expect(step2Title.className).toContain("emerald");
  });

  it("OB-4: Step 3 shows as completed when entities exist", () => {
    render(
      <OnboardingChecklist {...defaultProps} hasEntities={true} />,
    );
    const step3Title = screen.getByText("捕捉知識");
    expect(step3Title.className).toContain("emerald");
  });

  it("OB-4: progress updates when entities exist", () => {
    // hasPartner=true + hasEntities=true → 2/4
    render(
      <OnboardingChecklist
        {...defaultProps}
        hasPartner={true}
        hasEntities={true}
      />,
    );
    expect(screen.getByText("2/4")).toBeDefined();
  });

  it("OB-5: Step 1 done button calls onUpdatePrefs", () => {
    const onUpdate = vi.fn();
    render(
      <OnboardingChecklist {...defaultProps} onUpdatePrefs={onUpdate} />,
    );

    // Expand Step 1
    fireEvent.click(screen.getByText("導向知識庫"));

    // Click done
    fireEvent.click(screen.getByText("已完成"));
    expect(onUpdate).toHaveBeenCalledWith({ step1_done: true });
  });

  it("OB-5: Step 4 done button calls onUpdatePrefs", () => {
    const onUpdate = vi.fn();
    render(
      <OnboardingChecklist {...defaultProps} onUpdatePrefs={onUpdate} />,
    );

    // Expand Step 4
    fireEvent.click(screen.getByText("體驗 AI 角色"));

    // Click done
    fireEvent.click(screen.getByText("已完成"));
    expect(onUpdate).toHaveBeenCalledWith({ step4_done: true });
  });

  it("OB-6: dismiss calls onUpdatePrefs with dismissed=true", () => {
    const onUpdate = vi.fn();
    render(
      <OnboardingChecklist {...defaultProps} onUpdatePrefs={onUpdate} />,
    );

    fireEvent.click(screen.getByText("不再顯示"));
    expect(onUpdate).toHaveBeenCalledWith({ dismissed: true });
  });

  it("OB-7: technical platform shows CLI-style copy in Step 3", () => {
    render(
      <OnboardingChecklist {...defaultProps} platformType="technical" />,
    );

    // Expand Step 3
    fireEvent.click(screen.getByText("捕捉知識"));

    // Should show CLI-style command
    expect(screen.getByText("/zenos-capture ~/your-project")).toBeDefined();
  });

  it("OB-7: non-technical platform shows conversational copy in Step 3", () => {
    render(
      <OnboardingChecklist
        {...defaultProps}
        platformType="non_technical"
      />,
    );

    // Expand Step 3
    fireEvent.click(screen.getByText("捕捉知識"));

    // Should show conversational prompt
    expect(
      screen.getByText(
        "幫我把這個專案加入 ZenOS，用 /zenos-capture 建立知識庫",
      ),
    ).toBeDefined();
  });

  it("OB-2: all steps done shows 4/4 progress", () => {
    render(
      <OnboardingChecklist
        {...defaultProps}
        hasPartner={true}
        hasEntities={true}
        onboardingPrefs={{ step1_done: true, step4_done: true }}
      />,
    );
    expect(screen.getByText("4/4")).toBeDefined();
  });

  it("Step 2 expand shows MCP URL with masked API key", () => {
    render(<OnboardingChecklist {...defaultProps} />);

    // Expand Step 2
    fireEvent.click(screen.getByText("設定 MCP + 安裝 Skills"));

    // Should show masked URL containing first 8 chars of api key
    expect(
      screen.getByText(/test-api/, { exact: false }),
    ).toBeDefined();
  });

  it("Step 1 shows different copy for technical vs non-technical", () => {
    const { unmount } = render(
      <OnboardingChecklist {...defaultProps} platformType="technical" />,
    );

    fireEvent.click(screen.getByText("導向知識庫"));
    expect(screen.getByText(/專案路徑/, { exact: false })).toBeDefined();
    unmount();

    render(
      <OnboardingChecklist {...defaultProps} platformType="non_technical" />,
    );
    fireEvent.click(screen.getByText("導向知識庫"));
    expect(screen.getAllByText(/Google Drive/, { exact: false }).length).toBeGreaterThan(0);
  });

  it("Step 4 shows zenos-setup hint for missing roles", () => {
    render(<OnboardingChecklist {...defaultProps} />);

    fireEvent.click(screen.getByText("體驗 AI 角色"));
    expect(screen.getByText(/zenos-setup/, { exact: false })).toBeDefined();
  });
});
