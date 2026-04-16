import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
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
    expect(screen.getByText("Connector 已連線")).toBeInTheDocument();
    expect(screen.getByText("mode artifact")).toBeInTheDocument();
    expect(screen.getByText("content")).toBeInTheDocument();
  });

  it("supports inline rail mode for desktop layouts", () => {
    render(
      <CopilotRailShell
        open={false}
        onOpenChange={() => {}}
        entry={entry}
        chatStatus="idle"
        connectorStatus="disconnected"
        desktopInline
      >
        <div>inline content</div>
      </CopilotRailShell>
    );

    expect(screen.getAllByText("AI 會議準備").length).toBeGreaterThan(0);
    expect(screen.getAllByText("inline content").length).toBeGreaterThan(0);
  });
});
