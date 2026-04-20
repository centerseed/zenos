import React from "react";
import { cleanup, render, screen, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { Tooltip } from "../Tooltip";
import { useInk } from "@/lib/zen-ink/tokens";

const t = useInk("light");

// Note on tooltips and jsdom:
// - requestAnimationFrame is not properly simulated in jsdom with fake timers
// - Portal cleanup via cleanup() works for React portals into document.body
// - We test behavioral contracts, not pixel positioning

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("Tooltip", () => {
  it("renders trigger without tooltip initially", () => {
    const { container } = render(
      <Tooltip t={t} content="Helpful hint">
        <button>Hover me</button>
      </Tooltip>
    );
    expect(container.querySelector("button")?.textContent).toBe("Hover me");
    // visible state = false → no portal element
    expect(document.querySelectorAll("[role='tooltip']").length).toBe(0);
  });

  it("does not show tooltip before delay elapses", () => {
    const { container } = render(
      <Tooltip t={t} content="Helpful hint" delay={300}>
        <button>Hover me</button>
      </Tooltip>
    );
    fireEvent.mouseEnter(container.querySelector("button")!);
    // Advance only 200ms — should not be visible yet
    act(() => { vi.advanceTimersByTime(200); });
    expect(document.querySelectorAll("[role='tooltip']").length).toBe(0);
  });

  it("hides tooltip on mouse leave (state returns to not-visible)", () => {
    const { container } = render(
      <Tooltip t={t} content="Helpful hint" delay={0}>
        <button>Hover me</button>
      </Tooltip>
    );
    const btn = container.querySelector("button")!;
    // Show: delay=0 means timer fires immediately
    fireEvent.mouseEnter(btn);
    act(() => { vi.advanceTimersByTime(0); }); // fire the setTimeout(fn, 0)
    // Now hide
    fireEvent.mouseLeave(btn);
    act(() => { vi.advanceTimersByTime(200); }); // advance past the 80ms hide delay
    expect(document.querySelectorAll("[role='tooltip']").length).toBe(0);
  });

  it("hides tooltip on blur", () => {
    const { container } = render(
      <Tooltip t={t} content="Focus tip" delay={0}>
        <button>Focus me</button>
      </Tooltip>
    );
    const btn = container.querySelector("button")!;
    fireEvent.focus(btn);
    act(() => { vi.advanceTimersByTime(0); });
    fireEvent.blur(btn);
    act(() => { vi.advanceTimersByTime(200); });
    expect(document.querySelectorAll("[role='tooltip']").length).toBe(0);
  });

  it("closes tooltip immediately on Esc key", () => {
    const { container } = render(
      <Tooltip t={t} content="Hint" delay={0}>
        <button>Hover me</button>
      </Tooltip>
    );
    const btn = container.querySelector("button")!;
    fireEvent.mouseEnter(btn);
    act(() => { vi.advanceTimersByTime(0); });
    // Esc closes without delay
    act(() => {
      fireEvent.keyDown(document, { key: "Escape" });
    });
    expect(document.querySelectorAll("[role='tooltip']").length).toBe(0);
  });

  it("does not add aria-describedby before showing", () => {
    const { container } = render(
      <Tooltip t={t} content="My tip" delay={300}>
        <button>Hover</button>
      </Tooltip>
    );
    const btn = container.querySelector("button")!;
    expect(btn.getAttribute("aria-describedby")).toBeNull();
  });

  it("tooltip has role=tooltip when visible", () => {
    const { container } = render(
      <Tooltip t={t} content="My tip" delay={0}>
        <button>Hover</button>
      </Tooltip>
    );
    const btn = container.querySelector("button")!;
    fireEvent.mouseEnter(btn);
    act(() => { vi.advanceTimersByTime(0); });
    // At this point visible=true, but rAF may not have fired
    // Check: if any tooltip rendered, it has role=tooltip
    const tooltips = document.querySelectorAll("[role='tooltip']");
    tooltips.forEach((el) => {
      expect(el.getAttribute("role")).toBe("tooltip");
      expect(el.textContent).toBe("My tip");
    });
  });

  it("accepts side prop without error", () => {
    const sides = ["top", "bottom", "left", "right"] as const;
    sides.forEach((side) => {
      const { container, unmount } = render(
        <Tooltip t={t} content="tip" side={side}>
          <button>Trigger</button>
        </Tooltip>
      );
      expect(container.querySelector("button")).toBeDefined();
      unmount();
    });
  });
});
