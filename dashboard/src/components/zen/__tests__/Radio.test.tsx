import React from "react";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { Radio } from "../Radio";
import { useInk } from "@/lib/zen-ink/tokens";

const t = useInk("light");

afterEach(() => cleanup());

describe("Radio", () => {
  it("renders unselected when value !== selected", () => {
    const { container } = render(
      <Radio t={t} name="priority" value="high" selected="low" onChange={() => {}} label="High" />
    );
    const rb = container.querySelector("input[type='radio']") as HTMLInputElement;
    expect(rb.checked).toBe(false);
  });

  it("renders selected when value === selected", () => {
    const { container } = render(
      <Radio t={t} name="priority" value="high" selected="high" onChange={() => {}} label="High" />
    );
    const rb = container.querySelector("input[type='radio']") as HTMLInputElement;
    expect(rb.checked).toBe(true);
  });

  it("calls onChange with value when clicked", () => {
    const onChange = vi.fn();
    const { container } = render(
      <Radio t={t} name="priority" value="high" selected="low" onChange={onChange} label="High" />
    );
    const rb = container.querySelector("input[type='radio']")!;
    fireEvent.click(rb);
    expect(onChange).toHaveBeenCalledWith("high");
  });

  it("is disabled when disabled=true", () => {
    const { container } = render(
      <Radio t={t} name="priority" value="high" selected="low" onChange={() => {}} label="High" disabled />
    );
    const rb = container.querySelector("input[type='radio']") as HTMLInputElement;
    expect(rb.disabled).toBe(true);
  });

  it("renders label text", () => {
    render(
      <Radio t={t} name="p" value="x" selected="" onChange={() => {}} label="Option X" />
    );
    expect(screen.getByText("Option X")).toBeDefined();
  });

  it("renders aria-label on input when no visible label", () => {
    const { container } = render(
      <Radio t={t} name="p" value="x" selected="" onChange={() => {}} aria-label="Option X" />
    );
    const rb = container.querySelector("input[type='radio']")!;
    expect(rb.getAttribute("aria-label")).toBe("Option X");
  });

  it("renders inner dot when selected", () => {
    const { container } = render(
      <Radio t={t} name="p" value="x" selected="x" onChange={() => {}} label="Option X" />
    );
    // The inner dot span should exist (second span inside the outer circle span)
    const circles = container.querySelectorAll("span[aria-hidden='true'] span");
    expect(circles.length).toBe(1);
  });

  it("does not render inner dot when unselected", () => {
    const { container } = render(
      <Radio t={t} name="p" value="x" selected="y" onChange={() => {}} label="Option Y" />
    );
    const circles = container.querySelectorAll("span[aria-hidden='true'] span");
    expect(circles.length).toBe(0);
  });
});
