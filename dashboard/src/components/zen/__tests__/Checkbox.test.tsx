import React from "react";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { Checkbox } from "../Checkbox";
import { useInk } from "@/lib/zen-ink/tokens";

const t = useInk("light");

afterEach(() => cleanup());

describe("Checkbox", () => {
  it("renders unchecked by default", () => {
    const { container } = render(
      <Checkbox t={t} checked={false} onChange={() => {}} label="Accept terms" />
    );
    const cb = container.querySelector("input[type='checkbox']") as HTMLInputElement;
    expect(cb.checked).toBe(false);
  });

  it("renders checked when checked=true", () => {
    const { container } = render(
      <Checkbox t={t} checked={true} onChange={() => {}} label="Accept terms" />
    );
    const cb = container.querySelector("input[type='checkbox']") as HTMLInputElement;
    expect(cb.checked).toBe(true);
  });

  it("calls onChange(true) when clicking unchecked checkbox", () => {
    const onChange = vi.fn();
    const { container } = render(
      <Checkbox t={t} checked={false} onChange={onChange} label="Accept terms" />
    );
    const cb = container.querySelector("input[type='checkbox']")!;
    fireEvent.click(cb);
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("calls onChange(false) when clicking checked checkbox", () => {
    const onChange = vi.fn();
    const { container } = render(
      <Checkbox t={t} checked={true} onChange={onChange} label="Accept terms" />
    );
    const cb = container.querySelector("input[type='checkbox']")!;
    fireEvent.click(cb);
    expect(onChange).toHaveBeenCalledWith(false);
  });

  it("is disabled when disabled=true", () => {
    const { container } = render(
      <Checkbox t={t} checked={false} onChange={() => {}} label="Accept" disabled />
    );
    const cb = container.querySelector("input[type='checkbox']") as HTMLInputElement;
    expect(cb.disabled).toBe(true);
  });

  it("renders label text", () => {
    render(<Checkbox t={t} checked={false} onChange={() => {}} label="My Label" />);
    expect(screen.getByText("My Label")).toBeDefined();
  });

  it("renders aria-label on input when no visible label", () => {
    const { container } = render(
      <Checkbox t={t} checked={false} onChange={() => {}} aria-label="Toggle item" />
    );
    const cb = container.querySelector("input[type='checkbox']")!;
    expect(cb.getAttribute("aria-label")).toBe("Toggle item");
  });

  it("renders checkmark SVG when checked", () => {
    const { container } = render(
      <Checkbox t={t} checked={true} onChange={() => {}} />
    );
    expect(container.querySelector("svg")).toBeDefined();
  });

  it("does not render checkmark SVG when unchecked", () => {
    const { container } = render(
      <Checkbox t={t} checked={false} onChange={() => {}} />
    );
    expect(container.querySelector("svg")).toBeNull();
  });
});
