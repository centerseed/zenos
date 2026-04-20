import React, { useState } from "react";
import { cleanup, render, screen, fireEvent, within } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { Dropdown } from "../Dropdown";
import { Btn } from "../Btn";
import { useInk } from "@/lib/zen-ink/tokens";

const t = useInk("light");
const items = [
  { value: "todo", label: "Todo" },
  { value: "in_progress", label: "In Progress" },
  { value: "done", label: "Done" },
];

afterEach(() => cleanup());

function TestDropdown({
  onSelect = (_v: string[]) => {},
  multiple = false,
  selected = [] as string[],
  disabled = false,
}) {
  return (
    <Dropdown
      t={t}
      trigger={<Btn t={t} variant="outline">Status</Btn>}
      items={items}
      selected={selected}
      multiple={multiple}
      onSelect={onSelect}
      disabled={disabled}
      aria-label="Status filter"
    />
  );
}

/** Helper: click the dropdown trigger using the text label */
function clickTrigger() {
  // Click the inner Btn child inside the trigger wrapper
  fireEvent.click(screen.getByText("Status"));
}

describe("Dropdown", () => {
  it("renders trigger text", () => {
    render(<TestDropdown />);
    expect(screen.getByText("Status")).toBeDefined();
  });

  it("does not render listbox before trigger click", () => {
    render(<TestDropdown />);
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("opens listbox on trigger click", () => {
    render(<TestDropdown />);
    clickTrigger();
    expect(screen.getByRole("listbox")).toBeDefined();
  });

  it("renders all items when open", () => {
    render(<TestDropdown />);
    clickTrigger();
    expect(screen.getByText("Todo")).toBeDefined();
    expect(screen.getByText("In Progress")).toBeDefined();
    expect(screen.getByText("Done")).toBeDefined();
  });

  it("calls onSelect with selected value on single-select click", () => {
    const onSelect = vi.fn();
    render(<TestDropdown onSelect={onSelect} />);
    clickTrigger();
    const options = screen.getAllByRole("option");
    const inProgress = options.find((o) => o.textContent?.includes("In Progress"))!;
    fireEvent.click(inProgress);
    expect(onSelect).toHaveBeenCalledWith(["in_progress"]);
  });

  it("closes listbox after single select (default)", () => {
    render(<TestDropdown />);
    clickTrigger();
    const options = screen.getAllByRole("option");
    fireEvent.click(options[0]);
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("keeps listbox open after multi-select", () => {
    render(<TestDropdown multiple={true} />);
    clickTrigger();
    const options = screen.getAllByRole("option");
    fireEvent.click(options[0]);
    expect(screen.getByRole("listbox")).toBeDefined();
  });

  it("closes on Esc key", () => {
    render(<TestDropdown />);
    clickTrigger();
    expect(screen.getByRole("listbox")).toBeDefined();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("marks selected items with aria-selected=true in multi mode", () => {
    render(<TestDropdown multiple={true} selected={["todo"]} />);
    clickTrigger();
    const options = screen.getAllByRole("option");
    const todoOption = options.find((o) => o.textContent?.includes("Todo"))!;
    expect(todoOption.getAttribute("aria-selected")).toBe("true");
  });

  it("marks unselected items with aria-selected=false", () => {
    render(<TestDropdown multiple={true} selected={["todo"]} />);
    clickTrigger();
    const options = screen.getAllByRole("option");
    const doneOption = options.find((o) => o.textContent?.includes("Done"))!;
    expect(doneOption.getAttribute("aria-selected")).toBe("false");
  });

  it("removes item from multi-select when clicking already-selected item", () => {
    const onSelect = vi.fn();
    render(<TestDropdown multiple={true} selected={["todo"]} onSelect={onSelect} />);
    clickTrigger();
    const options = screen.getAllByRole("option");
    const todoOption = options.find((o) => o.textContent?.includes("Todo"))!;
    fireEvent.click(todoOption);
    expect(onSelect).toHaveBeenCalledWith([]);
  });

  it("trigger wrapper has aria-haspopup=listbox", () => {
    render(<TestDropdown />);
    const triggerWrapper = document.querySelector("[aria-haspopup='listbox']");
    expect(triggerWrapper).not.toBeNull();
  });

  it("trigger has aria-expanded=false when closed", () => {
    render(<TestDropdown />);
    const triggerWrapper = document.querySelector("[aria-haspopup='listbox']");
    expect(triggerWrapper?.getAttribute("aria-expanded")).toBe("false");
  });

  it("trigger has aria-expanded=true when open", () => {
    render(<TestDropdown />);
    clickTrigger();
    const triggerWrapper = document.querySelector("[aria-haspopup='listbox']");
    expect(triggerWrapper?.getAttribute("aria-expanded")).toBe("true");
  });
});
