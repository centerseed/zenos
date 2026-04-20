import React from "react";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { Tabs } from "../Tabs";
import { useInk } from "@/lib/zen-ink/tokens";

const t = useInk("light");
const items = [
  { value: "line" as const, label: "LINE" },
  { value: "email" as const, label: "Email" },
  { value: "sms" as const, label: "SMS", disabled: true },
] as const;

type TabVal = "line" | "email" | "sms";

afterEach(() => cleanup());

describe("Tabs", () => {
  it("renders all tab labels", () => {
    render(<Tabs t={t} value="line" onChange={() => {}} items={[...items]} />);
    expect(screen.getByText("LINE")).toBeDefined();
    expect(screen.getByText("Email")).toBeDefined();
    expect(screen.getByText("SMS")).toBeDefined();
  });

  it("has role=tablist on container", () => {
    render(<Tabs t={t} value="line" onChange={() => {}} items={[...items]} />);
    expect(screen.getByRole("tablist")).toBeDefined();
  });

  it("marks active tab with aria-selected=true", () => {
    render(<Tabs t={t} value="email" onChange={() => {}} items={[...items]} />);
    const tabs = screen.getAllByRole("tab");
    const emailTab = tabs.find((el) => el.textContent === "Email");
    expect(emailTab?.getAttribute("aria-selected")).toBe("true");
  });

  it("marks inactive tabs with aria-selected=false", () => {
    render(<Tabs t={t} value="line" onChange={() => {}} items={[...items]} />);
    const tabs = screen.getAllByRole("tab");
    const emailTab = tabs.find((el) => el.textContent === "Email");
    expect(emailTab?.getAttribute("aria-selected")).toBe("false");
  });

  it("calls onChange when clicking an enabled tab", () => {
    const onChange = vi.fn();
    render(<Tabs t={t} value="line" onChange={onChange} items={[...items]} />);
    fireEvent.click(screen.getByText("Email"));
    expect(onChange).toHaveBeenCalledWith("email");
  });

  it("does not call onChange when clicking disabled tab", () => {
    const onChange = vi.fn();
    render(<Tabs t={t} value="line" onChange={onChange} items={[...items]} />);
    // SMS is disabled
    const smsBtn = screen.getAllByRole("tab").find((el) => el.textContent === "SMS")!;
    fireEvent.click(smsBtn);
    expect(onChange).not.toHaveBeenCalled();
  });

  it("navigates with ArrowRight key to next enabled tab", () => {
    const onChange = vi.fn();
    render(
      <Tabs t={t} value="line" onChange={onChange} items={[...items]} />
    );
    const tabs = screen.getAllByRole("tab");
    const lineTab = tabs.find((el) => el.textContent === "LINE")!;
    fireEvent.keyDown(lineTab, { key: "ArrowRight" });
    expect(onChange).toHaveBeenCalledWith("email");
  });

  it("navigates with ArrowLeft key to previous enabled tab", () => {
    const onChange = vi.fn();
    render(
      <Tabs t={t} value="email" onChange={onChange} items={[...items]} />
    );
    const tabs = screen.getAllByRole("tab");
    const emailTab = tabs.find((el) => el.textContent === "Email")!;
    fireEvent.keyDown(emailTab, { key: "ArrowLeft" });
    expect(onChange).toHaveBeenCalledWith("line");
  });

  it("renders tab panels with role=tabpanel", () => {
    const twoItems = [
      { value: "line" as const, label: "LINE" },
      { value: "email" as const, label: "Email" },
    ];
    const panels = {
      line: <div>LINE content</div>,
      email: <div>Email content</div>,
    };
    render(
      <Tabs t={t} value="line" onChange={() => {}} items={twoItems} panels={panels} />
    );
    const panelEls = screen.getAllByRole("tabpanel", { hidden: true });
    expect(panelEls.length).toBe(2);
  });

  it("active panel is not hidden", () => {
    const twoItems = [
      { value: "line" as const, label: "LINE" },
      { value: "email" as const, label: "Email" },
    ];
    const panels = {
      line: <div>LINE content</div>,
      email: <div>Email content</div>,
    };
    render(
      <Tabs t={t} value="line" onChange={() => {}} items={twoItems} panels={panels} />
    );
    const allPanels = screen.getAllByRole("tabpanel", { hidden: true });
    const activePanel = allPanels.find((el) => el.getAttribute("hidden") === null);
    expect(activePanel?.textContent).toContain("LINE content");
  });

  it("renders segment variant with group background", () => {
    const { container } = render(
      <Tabs t={t} value="line" onChange={() => {}} items={[...items]} variant="segment" />
    );
    // Segment has pill-group background on the tablist (paperWarm = #EFE9DB)
    // jsdom converts hex to rgb
    const tablist = container.querySelector("[role='tablist']") as HTMLElement;
    // Just verify background is set (non-transparent)
    expect(tablist.style.background).not.toBe("transparent");
    expect(tablist.style.background).not.toBe("");
  });
});
