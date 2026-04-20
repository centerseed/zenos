import React from "react";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { Textarea } from "../Textarea";
import { useInk } from "@/lib/zen-ink/tokens";

const t = useInk("light");

afterEach(() => cleanup());

describe("Textarea", () => {
  it("renders with value", () => {
    render(<Textarea t={t} value="hello world" onChange={() => {}} />);
    const ta = screen.getByRole("textbox") as HTMLTextAreaElement;
    expect(ta.value).toBe("hello world");
  });

  it("calls onChange on input", () => {
    const onChange = vi.fn();
    render(<Textarea t={t} value="" onChange={onChange} />);
    const ta = screen.getByRole("textbox");
    fireEvent.change(ta, { target: { value: "typed" } });
    expect(onChange).toHaveBeenCalledWith("typed");
  });

  it("is disabled when disabled=true", () => {
    render(<Textarea t={t} value="" onChange={() => {}} disabled />);
    const ta = screen.getByRole("textbox") as HTMLTextAreaElement;
    expect(ta.disabled).toBe(true);
  });

  it("renders correct rows", () => {
    render(<Textarea t={t} value="" onChange={() => {}} rows={6} />);
    const ta = screen.getByRole("textbox") as HTMLTextAreaElement;
    expect(ta.rows).toBe(6);
  });

  it("marks aria-invalid when invalid=true", () => {
    render(<Textarea t={t} value="" onChange={() => {}} invalid />);
    const ta = screen.getByRole("textbox");
    expect(ta.getAttribute("aria-invalid")).toBe("true");
  });

  it("uses mono font variant when fontVariant=mono", () => {
    const { container } = render(
      <Textarea t={t} value="" onChange={() => {}} fontVariant="mono" />
    );
    const ta = container.querySelector("textarea") as HTMLTextAreaElement;
    expect(ta.style.fontFamily).toContain("monospace");
  });

  it("defaults to vertical resize", () => {
    const { container } = render(<Textarea t={t} value="" onChange={() => {}} />);
    const ta = container.querySelector("textarea") as HTMLTextAreaElement;
    expect(ta.style.resize).toBe("vertical");
  });

  it("can set resize to none", () => {
    const { container } = render(
      <Textarea t={t} value="" onChange={() => {}} resize="none" />
    );
    const ta = container.querySelector("textarea") as HTMLTextAreaElement;
    expect(ta.style.resize).toBe("none");
  });
});
