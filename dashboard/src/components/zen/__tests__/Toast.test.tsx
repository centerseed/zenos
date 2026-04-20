import React from "react";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider, useToast, type ToastInput } from "../Toast";
import { useInk } from "@/lib/zen-ink/tokens";

const t = useInk("light");

afterEach(() => {
  cleanup();
});

// Test harness: exposes showToast / dismiss / dismissAll via data attributes
function Trigger({ inputs }: { inputs: ToastInput[] }) {
  const { showToast, dismissAll } = useToast();
  return (
    <>
      {inputs.map((input, i) => (
        <button
          key={i}
          data-testid={`show-${i}`}
          onClick={() => showToast(input)}
        >
          show {i}
        </button>
      ))}
      <button data-testid="dismiss-all" onClick={dismissAll}>
        dismiss all
      </button>
    </>
  );
}

function renderWith(inputs: ToastInput[]) {
  return render(
    <ToastProvider t={t}>
      <Trigger inputs={inputs} />
    </ToastProvider>
  );
}

describe("Toast", () => {
  it("renders success toast with role=status + aria-live=polite", () => {
    renderWith([{ title: "Saved", tone: "success" }]);
    fireEvent.click(screen.getByTestId("show-0"));
    const el = screen.getByRole("status");
    expect(el.getAttribute("aria-live")).toBe("polite");
    expect(el.textContent).toContain("Saved");
  });

  it("renders info toast with role=status + aria-live=polite", () => {
    renderWith([{ title: "FYI", tone: "info" }]);
    fireEvent.click(screen.getByTestId("show-0"));
    const el = screen.getByRole("status");
    expect(el.getAttribute("aria-live")).toBe("polite");
    expect(el.textContent).toContain("FYI");
  });

  it("renders error toast with role=alert + aria-live=assertive", () => {
    renderWith([{ title: "Oops", tone: "error" }]);
    fireEvent.click(screen.getByTestId("show-0"));
    const el = screen.getByRole("alert");
    expect(el.getAttribute("aria-live")).toBe("assertive");
    expect(el.textContent).toContain("Oops");
  });

  it("renders warn toast with role=alert + aria-live=assertive", () => {
    renderWith([{ title: "Heads up", tone: "warn" }]);
    fireEvent.click(screen.getByTestId("show-0"));
    const el = screen.getByRole("alert");
    expect(el.getAttribute("aria-live")).toBe("assertive");
  });

  it("renders description when provided", () => {
    renderWith([
      { title: "Saved", description: "Your changes were saved to disk.", tone: "success" },
    ]);
    fireEvent.click(screen.getByTestId("show-0"));
    expect(screen.getByText("Your changes were saved to disk.")).toBeDefined();
  });

  it("auto-dismisses after duration (default 5000ms)", () => {
    vi.useFakeTimers();
    try {
      renderWith([{ title: "Hi", tone: "success" }]);
      fireEvent.click(screen.getByTestId("show-0"));
      expect(screen.queryByRole("status")).not.toBeNull();
      act(() => {
        vi.advanceTimersByTime(5000);
      });
      expect(screen.queryByRole("status")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("auto-dismisses after custom duration", () => {
    vi.useFakeTimers();
    try {
      renderWith([{ title: "Hi", tone: "success", duration: 2000 }]);
      fireEvent.click(screen.getByTestId("show-0"));
      act(() => {
        vi.advanceTimersByTime(1999);
      });
      expect(screen.queryByRole("status")).not.toBeNull();
      act(() => {
        vi.advanceTimersByTime(1);
      });
      expect(screen.queryByRole("status")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("duration=null disables auto-dismiss", () => {
    vi.useFakeTimers();
    try {
      renderWith([{ title: "Sticky", tone: "info", duration: null }]);
      fireEvent.click(screen.getByTestId("show-0"));
      act(() => {
        vi.advanceTimersByTime(20_000);
      });
      expect(screen.queryByRole("status")).not.toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("duration=0 disables auto-dismiss", () => {
    vi.useFakeTimers();
    try {
      renderWith([{ title: "Sticky", tone: "info", duration: 0 }]);
      fireEvent.click(screen.getByTestId("show-0"));
      act(() => {
        vi.advanceTimersByTime(20_000);
      });
      expect(screen.queryByRole("status")).not.toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("manual close button dismisses the toast", () => {
    renderWith([{ title: "Saved", tone: "success" }]);
    fireEvent.click(screen.getByTestId("show-0"));
    expect(screen.queryByRole("status")).not.toBeNull();
    fireEvent.click(screen.getByLabelText("關閉通知"));
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("queue: 3 showToast calls renders 3 toast elements", () => {
    renderWith([
      { title: "First", tone: "success" },
      { title: "Second", tone: "info" },
      { title: "Third", tone: "error" },
    ]);
    fireEvent.click(screen.getByTestId("show-0"));
    fireEvent.click(screen.getByTestId("show-1"));
    fireEvent.click(screen.getByTestId("show-2"));
    // success + info → role=status; error → role=alert
    expect(screen.getAllByRole("status")).toHaveLength(2);
    expect(screen.getAllByRole("alert")).toHaveLength(1);
  });

  it("dismissAll clears all toasts", () => {
    renderWith([
      { title: "A", tone: "success" },
      { title: "B", tone: "success" },
      { title: "C", tone: "success" },
    ]);
    fireEvent.click(screen.getByTestId("show-0"));
    fireEvent.click(screen.getByTestId("show-1"));
    fireEvent.click(screen.getByTestId("show-2"));
    expect(screen.getAllByRole("status")).toHaveLength(3);
    fireEvent.click(screen.getByTestId("dismiss-all"));
    expect(screen.queryAllByRole("status")).toHaveLength(0);
  });

  it("Esc dismisses the most recent toast", () => {
    renderWith([
      { title: "First", tone: "info", duration: null },
      { title: "Second", tone: "info", duration: null },
    ]);
    fireEvent.click(screen.getByTestId("show-0"));
    fireEvent.click(screen.getByTestId("show-1"));
    expect(screen.getAllByRole("status")).toHaveLength(2);
    fireEvent.keyDown(document, { key: "Escape" });
    // Last one (Second) should be removed, First remains
    const remaining = screen.getAllByRole("status");
    expect(remaining).toHaveLength(1);
    expect(remaining[0].textContent).toContain("First");
  });

  it("throws when useToast called outside provider", () => {
    function Orphan() {
      useToast();
      return null;
    }
    // React logs an error boundary message; suppress with a spy
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Orphan />)).toThrow(/ToastProvider/);
    spy.mockRestore();
  });
});
