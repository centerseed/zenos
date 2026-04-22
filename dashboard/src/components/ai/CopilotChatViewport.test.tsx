import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render } from "@testing-library/react";
import { CopilotChatViewport } from "./CopilotChatViewport";

describe("CopilotChatViewport", () => {
  const scrollToMock = vi.fn();
  const scrollIntoViewMock = vi.fn();

  beforeEach(() => {
    scrollToMock.mockReset();
    scrollIntoViewMock.mockReset();
    Object.defineProperty(HTMLDivElement.prototype, "scrollTo", {
      configurable: true,
      writable: true,
      value: scrollToMock,
    });
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      writable: true,
      value: scrollIntoViewMock,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("scrolls only its own viewport on new messages instead of scrolling the whole page", () => {
    render(
      <CopilotChatViewport
        messages={[
          {
            role: "assistant",
            content: "hello",
            timestamp: Date.parse("2026-04-22T00:00:00.000Z"),
          },
        ]}
        streamingText=""
        isStreaming={false}
      />
    );

    expect(scrollToMock).toHaveBeenCalled();
    expect(scrollIntoViewMock).not.toHaveBeenCalled();
  });
});
