import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { describe, it, expect, afterEach } from "vitest";
import { Panel } from "../Panel";
import { useInk } from "@/lib/zen-ink/tokens";

const t = useInk("light");

afterEach(() => cleanup());

// Helper: convert hex to lowercase rgb string for jsdom comparison
// jsdom converts inline style hex colors to rgb() form
function hexToRgb(hex: string): string {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!result) return hex;
  const r = parseInt(result[1], 16);
  const g = parseInt(result[2], 16);
  const b = parseInt(result[3], 16);
  return `rgb(${r}, ${g}, ${b})`;
}

describe("Panel", () => {
  it("renders children", () => {
    render(<Panel t={t}>Hello Panel</Panel>);
    expect(screen.getByText("Hello Panel")).toBeDefined();
  });

  it("renders with surface background by default", () => {
    const { container } = render(<Panel t={t}>content</Panel>);
    const div = container.firstChild as HTMLElement;
    // jsdom converts hex to rgb form
    expect(div.style.background).toBe(hexToRgb(t.c.surface));
  });

  it("renders with surfaceHi background when variant=surfaceHi", () => {
    const { container } = render(<Panel t={t} variant="surfaceHi">content</Panel>);
    const div = container.firstChild as HTMLElement;
    expect(div.style.background).toBe(hexToRgb(t.c.surfaceHi));
  });

  it("renders with paperWarm background when variant=paperWarm", () => {
    const { container } = render(<Panel t={t} variant="paperWarm">content</Panel>);
    const div = container.firstChild as HTMLElement;
    expect(div.style.background).toBe(hexToRgb(t.c.paperWarm));
  });

  it("hides border when outlined=false", () => {
    const { container } = render(<Panel t={t} outlined={false}>content</Panel>);
    const div = container.firstChild as HTMLElement;
    // "border: none" is not exactly "none" — check computed style approach or the raw shorthand
    // jsdom keeps it as inline style, 'none' or 'medium' for shorthand. Use border-style check.
    // We set style={{ border: "none" }} so jsdom stores it as border: "medium"
    // The reliable check is that border is NOT the inked inkHair value
    // Better: check borderStyle
    expect(div.style.borderStyle).toBe("none");
  });

  it("has border when outlined=true (default)", () => {
    const { container } = render(<Panel t={t}>content</Panel>);
    const div = container.firstChild as HTMLElement;
    // Should have a 1px solid border
    expect(div.style.borderStyle).toBe("solid");
    expect(div.style.borderWidth).toBe("1px");
  });

  it("applies custom padding number", () => {
    const { container } = render(<Panel t={t} padding={32}>content</Panel>);
    const div = container.firstChild as HTMLElement;
    expect(div.style.padding).toBe("32px");
  });

  it("applies custom padding string", () => {
    const { container } = render(<Panel t={t} padding="8px 16px">content</Panel>);
    const div = container.firstChild as HTMLElement;
    expect(div.style.padding).toBe("8px 16px");
  });

  it("applies custom style", () => {
    const { container } = render(<Panel t={t} style={{ marginTop: 10 }}>content</Panel>);
    const div = container.firstChild as HTMLElement;
    expect(div.style.marginTop).toBe("10px");
  });

  it("applies borderRadius from token (2px)", () => {
    const { container } = render(<Panel t={t}>content</Panel>);
    const div = container.firstChild as HTMLElement;
    expect(div.style.borderRadius).toBe("2px");
  });
});
