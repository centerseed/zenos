import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CopilotInputBar } from "@/components/ai/CopilotInputBar";

describe("CopilotInputBar", () => {
  it("does not send on Enter while IME composition is active", () => {
    const onSend = vi.fn();

    render(
      <CopilotInputBar
        status="idle"
        onSend={onSend}
        onCancel={() => {}}
        onRetry={() => {}}
        hasStructuredResult={false}
      />
    );

    const input = screen.getByPlaceholderText("輸入訊息...");
    fireEvent.change(input, { target: { value: "組字中" } });
    fireEvent.keyDown(input, { key: "Enter", isComposing: true, keyCode: 229 });

    expect(onSend).not.toHaveBeenCalled();
    expect(screen.getByDisplayValue("組字中")).toBeInTheDocument();
  });
});
