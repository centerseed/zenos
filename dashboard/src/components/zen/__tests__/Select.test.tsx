import React from "react";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { Select } from "../Select";
import { useInk } from "@/lib/zen-ink/tokens";

const t = useInk("light");
const options = [
  { value: "critical", label: "Critical" },
  { value: "high", label: "High" },
  { value: "low", label: "Low" },
];

afterEach(() => cleanup());

describe("Select", () => {
  it("renders options", () => {
    render(<Select t={t} value={null} onChange={() => {}} options={options} placeholder="Select" />);
    expect(screen.getByText("Critical")).toBeDefined();
    expect(screen.getByText("High")).toBeDefined();
  });

  it("calls onChange when selection changes", () => {
    const onChange = vi.fn();
    render(<Select t={t} value={null} onChange={onChange} options={options} placeholder="Select" />);
    const select = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: "high" } });
    expect(onChange).toHaveBeenCalledWith("high");
  });

  it("calls onChange with null when empty option selected", () => {
    const onChange = vi.fn();
    render(
      <Select t={t} value="high" onChange={onChange} options={options} clearable placeholder="Select" />
    );
    const select = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: "" } });
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it("is disabled when disabled=true", () => {
    render(<Select t={t} value={null} onChange={() => {}} options={options} disabled />);
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    expect(select.disabled).toBe(true);
  });

  it("shows aria-label", () => {
    render(
      <Select t={t} value={null} onChange={() => {}} options={options} aria-label="Priority" />
    );
    expect(screen.getByLabelText("Priority")).toBeDefined();
  });

  it("marks aria-invalid when invalid=true", () => {
    render(<Select t={t} value={null} onChange={() => {}} options={options} invalid />);
    const select = screen.getByRole("combobox");
    expect(select.getAttribute("aria-invalid")).toBe("true");
  });

  it("shows placeholder as first option", () => {
    render(
      <Select t={t} value={null} onChange={() => {}} options={options} placeholder="Pick one" />
    );
    const firstOption = screen.getByText("Pick one");
    expect(firstOption).toBeDefined();
  });
});
