import React, { useState } from "react";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { Drawer } from "../Drawer";
import { useInk } from "@/lib/zen-ink/tokens";

const t = useInk("light");

afterEach(() => cleanup());

function ControlledDrawer({
  initialOpen = false,
  onOpenChangeSpy = (_v: boolean) => {},
  headerExtras,
  header,
}: {
  initialOpen?: boolean;
  onOpenChangeSpy?: (v: boolean) => void;
  headerExtras?: React.ReactNode;
  header?: React.ReactNode;
}) {
  const [open, setOpen] = useState(initialOpen);
  return (
    <>
      <button data-testid="trigger-btn" onClick={() => setOpen(true)}>
        Open Drawer
      </button>
      <Drawer
        t={t}
        open={open}
        onOpenChange={(v) => {
          setOpen(v);
          onOpenChangeSpy(v);
        }}
        header={header ?? <span>Drawer Title</span>}
        headerExtras={headerExtras}
        footer={<span>Footer content</span>}
      >
        <input data-testid="drawer-input" />
        <button data-testid="drawer-btn">Inner Button</button>
      </Drawer>
    </>
  );
}

describe("Drawer", () => {
  it("does not render when open=false", () => {
    render(<ControlledDrawer initialOpen={false} />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders dialog when open=true", () => {
    render(<ControlledDrawer initialOpen={true} />);
    expect(screen.getByRole("dialog")).toBeDefined();
  });

  it("has aria-modal=true", () => {
    render(<ControlledDrawer initialOpen={true} />);
    expect(screen.getByRole("dialog").getAttribute("aria-modal")).toBe("true");
  });

  it("closes on Esc key", () => {
    const spy = vi.fn();
    render(<ControlledDrawer initialOpen={true} onOpenChangeSpy={spy} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(spy).toHaveBeenCalledWith(false);
  });

  it("renders header content", () => {
    render(<ControlledDrawer initialOpen={true} />);
    expect(screen.getByText("Drawer Title")).toBeDefined();
  });

  it("renders footer content", () => {
    render(<ControlledDrawer initialOpen={true} />);
    expect(screen.getByText("Footer content")).toBeDefined();
  });

  it("renders children inside drawer body", () => {
    render(<ControlledDrawer initialOpen={true} />);
    expect(screen.getByTestId("drawer-btn")).toBeDefined();
  });

  it("renders headerExtras when provided", () => {
    render(
      <ControlledDrawer
        initialOpen={true}
        headerExtras={<span data-testid="extras">Dispatcher Badge</span>}
      />
    );
    expect(screen.getByTestId("extras")).toBeDefined();
    expect(screen.getByText("Dispatcher Badge")).toBeDefined();
  });

  it("does not render headerExtras slot when not provided", () => {
    render(<ControlledDrawer initialOpen={true} />);
    expect(screen.queryByTestId("extras")).toBeNull();
  });

  it("locks body scroll when open", () => {
    render(<ControlledDrawer initialOpen={true} />);
    expect(document.body.style.overflow).toBe("hidden");
  });

  it("restores body scroll when closed", () => {
    const { rerender } = render(
      <Drawer t={t} open={true} onOpenChange={() => {}}>
        <div>content</div>
      </Drawer>
    );
    expect(document.body.style.overflow).toBe("hidden");
    rerender(
      <Drawer t={t} open={false} onOpenChange={() => {}}>
        <div>content</div>
      </Drawer>
    );
    expect(document.body.style.overflow).not.toBe("hidden");
  });

  it("renders with default right side (no error)", () => {
    render(<ControlledDrawer initialOpen={true} />);
    // No throw = success
    expect(screen.getByRole("dialog")).toBeDefined();
  });

  it("renders with left side", () => {
    render(
      <Drawer t={t} open={true} onOpenChange={() => {}} side="left">
        <div>Left drawer</div>
      </Drawer>
    );
    expect(screen.getByRole("dialog")).toBeDefined();
    expect(screen.getByText("Left drawer")).toBeDefined();
  });
});
