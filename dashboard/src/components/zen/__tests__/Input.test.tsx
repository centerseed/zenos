import React from "react";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { Input } from "../Input";
import { useInk } from "@/lib/zen-ink/tokens";

const t = useInk("light");

afterEach(() => cleanup());

describe("Input", () => {
  it("renders with value and placeholder", () => {
    render(<Input t={t} value="hello" onChange={() => {}} placeholder="Type here" />);
    const input = screen.getByPlaceholderText("Type here") as HTMLInputElement;
    expect(input.value).toBe("hello");
  });

  it("calls onChange when value changes", () => {
    const onChange = vi.fn();
    render(<Input t={t} value="" onChange={onChange} />);
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "new value" } });
    expect(onChange).toHaveBeenCalledWith("new value");
  });

  it("is disabled when disabled=true", () => {
    render(<Input t={t} value="" onChange={() => {}} disabled />);
    const input = screen.getByRole("textbox") as HTMLInputElement;
    expect(input.disabled).toBe(true);
  });

  it("marks aria-invalid when invalid=true", () => {
    render(<Input t={t} value="" onChange={() => {}} invalid />);
    const input = screen.getByRole("textbox");
    expect(input.getAttribute("aria-invalid")).toBe("true");
  });

  it("renders with aria-label", () => {
    render(<Input t={t} value="" onChange={() => {}} aria-label="Search field" />);
    expect(screen.getByLabelText("Search field")).toBeDefined();
  });

  it("calls onKeyDown on keypress", () => {
    const onKeyDown = vi.fn();
    render(<Input t={t} value="" onChange={() => {}} onKeyDown={onKeyDown} />);
    const input = screen.getByRole("textbox");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onKeyDown).toHaveBeenCalled();
  });

  it("calls onBlur when losing focus", () => {
    const onBlur = vi.fn();
    render(<Input t={t} value="" onChange={() => {}} onBlur={onBlur} />);
    const input = screen.getByRole("textbox");
    fireEvent.blur(input);
    expect(onBlur).toHaveBeenCalled();
  });

  it("renders password type input", () => {
    const { container } = render(
      <Input t={t} value="secret" onChange={() => {}} type="password" />
    );
    const input = container.querySelector("input[type='password']");
    expect(input).toBeDefined();
  });

  it("renders sm size with smaller font", () => {
    const { container } = render(
      <Input t={t} value="" onChange={() => {}} size="sm" />
    );
    const input = container.querySelector("input") as HTMLInputElement;
    expect(input.style.fontSize).toBe("12px");
  });

  it("renders md size with larger font (default)", () => {
    const { container } = render(
      <Input t={t} value="" onChange={() => {}} size="md" />
    );
    const input = container.querySelector("input") as HTMLInputElement;
    expect(input.style.fontSize).toBe("13px");
  });
});
