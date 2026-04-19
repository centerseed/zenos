import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { CopilotRailShell } from "@/components/ai/CopilotRailShell";
import type { CopilotEntryConfig } from "@/lib/copilot/types";

const entry: CopilotEntryConfig = {
  intent_id: "crm.briefing",
  title: "AI 會議準備",
  mode: "artifact",
  launch_behavior: "auto_start",
  session_policy: "ephemeral",
  scope: {
    deal_id: "deal-1",
    scope_label: "企業流程導入 / 會議準備",
  },
  context_pack: {
    scene: "briefing",
  },
  build_prompt: () => "/crm-briefing",
};

describe("CopilotRailShell", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders a shared shell header with status and connector badges", () => {
    render(
      <CopilotRailShell
        open
        onOpenChange={() => {}}
        entry={entry}
        chatStatus="streaming"
        connectorStatus="connected"
      >
        <div>content</div>
      </CopilotRailShell>
    );

    expect(screen.getByText("AI 會議準備")).toBeInTheDocument();
    expect(screen.getByText("企業流程導入 / 會議準備")).toBeInTheDocument();
    expect(screen.getByText("AI 回覆中")).toBeInTheDocument();
    expect(screen.getByText("content")).toBeInTheDocument();
  });

  it("supports inline rail mode for desktop layouts without mounting the sheet dialog", async () => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: () => ({
        matches: true,
        media: "(min-width: 1280px)",
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => true,
      }),
    });

    render(
      <CopilotRailShell
        open
        onOpenChange={() => {}}
        entry={entry}
        chatStatus="idle"
        connectorStatus="disconnected"
        desktopInline
      >
        <div>inline content</div>
      </CopilotRailShell>
    );

    await waitFor(() => {
      expect(screen.getAllByText("AI 會議準備").length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText("inline content").length).toBeGreaterThan(0);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
