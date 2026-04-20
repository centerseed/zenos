import React, { useState } from "react";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { Dialog } from "../Dialog";
import { Btn } from "../Btn";
import { useInk } from "@/lib/zen-ink/tokens";

const t = useInk("light");

afterEach(() => cleanup());

function ControlledDialog({
  initialOpen = false,
  closable = true,
  onOpenChangeSpy = (_v: boolean) => {},
}: {
  initialOpen?: boolean;
  closable?: boolean;
  onOpenChangeSpy?: (v: boolean) => void;
}) {
  const [open, setOpen] = useState(initialOpen);
  return (
    <>
      <button onClick={() => setOpen(true)} data-testid="open-btn">
        Open
      </button>
      <Dialog
        t={t}
        open={open}
        onOpenChange={(v) => {
          setOpen(v);
          onOpenChangeSpy(v);
        }}
        title="Test Dialog"
        description="A test description"
        closable={closable}
        footer={<Btn t={t} onClick={() => setOpen(false)}>Close</Btn>}
      >
        <input data-testid="inner-input" />
        <button data-testid="inner-btn">Inner Button</button>
      </Dialog>
    </>
  );
}

describe("Dialog", () => {
  it("does not render when open=false", () => {
    render(<ControlledDialog initialOpen={false} />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders dialog when open=true", () => {
    render(<ControlledDialog initialOpen={true} />);
    expect(screen.getByRole("dialog")).toBeDefined();
  });

  it("has aria-modal=true", () => {
    render(<ControlledDialog initialOpen={true} />);
    const dialog = screen.getByRole("dialog");
    expect(dialog.getAttribute("aria-modal")).toBe("true");
  });

  it("has aria-labelledby pointing to title element", () => {
    render(<ControlledDialog initialOpen={true} />);
    const dialog = screen.getByRole("dialog");
    const labelId = dialog.getAttribute("aria-labelledby")!;
    expect(labelId).toBeTruthy();
    const titleEl = document.getElementById(labelId);
    expect(titleEl?.textContent).toBe("Test Dialog");
  });

  it("has aria-describedby pointing to description element", () => {
    render(<ControlledDialog initialOpen={true} />);
    const dialog = screen.getByRole("dialog");
    const descId = dialog.getAttribute("aria-describedby")!;
    expect(descId).toBeTruthy();
    const descEl = document.getElementById(descId);
    expect(descEl?.textContent).toContain("test description");
  });

  it("closes on Esc key", () => {
    const spy = vi.fn();
    render(<ControlledDialog initialOpen={true} onOpenChangeSpy={spy} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(spy).toHaveBeenCalledWith(false);
  });

  it("does not close on Esc when closable=false", () => {
    const spy = vi.fn();
    render(<ControlledDialog initialOpen={true} closable={false} onOpenChangeSpy={spy} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(spy).not.toHaveBeenCalled();
  });

  it("closes when clicking the close button", () => {
    const spy = vi.fn();
    render(<ControlledDialog initialOpen={true} onOpenChangeSpy={spy} />);
    const closeBtn = screen.getByLabelText("關閉");
    fireEvent.click(closeBtn);
    expect(spy).toHaveBeenCalledWith(false);
  });

  it("locks body scroll when open", () => {
    render(<ControlledDialog initialOpen={true} />);
    expect(document.body.style.overflow).toBe("hidden");
  });

  it("restores body scroll when closed", () => {
    const { rerender } = render(
      <Dialog t={t} open={true} onOpenChange={() => {}}>
        <div>content</div>
      </Dialog>
    );
    expect(document.body.style.overflow).toBe("hidden");
    rerender(
      <Dialog t={t} open={false} onOpenChange={() => {}}>
        <div>content</div>
      </Dialog>
    );
    expect(document.body.style.overflow).not.toBe("hidden");
  });

  it("renders footer content", () => {
    render(<ControlledDialog initialOpen={true} />);
    expect(screen.getByText("Close")).toBeDefined();
  });

  it("renders children", () => {
    render(<ControlledDialog initialOpen={true} />);
    expect(screen.getByTestId("inner-btn")).toBeDefined();
  });

  it("renders title with serif font (fontHead)", () => {
    render(
      <Dialog t={t} open={true} onOpenChange={() => {}} title="My Title">
        <div>body</div>
      </Dialog>
    );
    const title = screen.getByText("My Title");
    expect(title.style.fontFamily).toContain("Noto Serif");
  });

  it("renders correct size widths", () => {
    const { rerender } = render(
      <Dialog t={t} open={true} onOpenChange={() => {}} size="sm">
        <div>sm</div>
      </Dialog>
    );
    const smPanel = screen.getByRole("dialog");
    expect(smPanel.style.width).toBe("400px");

    rerender(
      <Dialog t={t} open={true} onOpenChange={() => {}} size="lg">
        <div>lg</div>
      </Dialog>
    );
    const lgPanel = screen.getByRole("dialog");
    expect(lgPanel.style.width).toBe("720px");
  });

  it("does not show close button when closable=false", () => {
    render(
      <Dialog t={t} open={true} onOpenChange={() => {}} title="T" closable={false}>
        <div>body</div>
      </Dialog>
    );
    expect(screen.queryByLabelText("關閉")).toBeNull();
  });
});
