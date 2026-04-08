/**
 * Tests for AppNav — S02: two-stage nav + workspace entry component.
 *
 * S02-1: isHomeWorkspace=true → full app surface
 * S02-2: isHomeWorkspace=false + guest/member → Knowledge Map / Products / Tasks only
 * S02-3: single workspace → shows "我的工作區" static label
 * S02-4: multiple workspaces → shows workspace picker
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import React from "react";

type WorkspaceRole = "owner" | "member" | "guest";

const DEFAULT_PARTNER = {
  id: "partner-home",
  email: "owner@test.com",
  displayName: "Home Owner",
  apiKey: "test-key", // pragma: allowlist secret
  isAdmin: true,
  workspaceRole: "owner" as WorkspaceRole,
  status: "active" as const,
  accessMode: "internal" as const,
  authorizedEntityIds: [] as string[],
  sharedPartnerId: null as null | string,
  invitedBy: null as null,
  createdAt: new Date(),
  updatedAt: new Date(),
};

let mockPartner: Record<string, unknown> = { ...DEFAULT_PARTNER };

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/tasks",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { getIdToken: vi.fn().mockResolvedValue("fake-token") },
    partner: mockPartner,
    signOut: vi.fn(),
  }),
}));

beforeEach(() => {
  mockPartner = { ...DEFAULT_PARTNER };
});

afterEach(() => {
  cleanup();
});

// ─── S02-1: isHomeWorkspace=true → full nav ───────────────────────────────────

describe("S02-1: isHomeWorkspace=true → full app surface", () => {
  it("owner in home workspace sees full nav including 成員 and 設定", async () => {
    mockPartner = {
      ...mockPartner,
      workspaceRole: "owner",
      isAdmin: true,
      sharedPartnerId: null,
    };

    const { AppNav } = await import("@/components/AppNav");
    render(<AppNav />);

    expect(screen.getByRole("link", { name: "知識地圖" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "客戶" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "成員" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /設定/i })).toBeInTheDocument();
    // Should NOT show the shared-workspace-only labels
    expect(screen.queryByRole("link", { name: "Products" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Tasks" })).not.toBeInTheDocument();
  });

  it("member in home workspace (no sharedPartnerId) sees member nav", async () => {
    mockPartner = {
      ...mockPartner,
      workspaceRole: "member",
      isAdmin: false,
      sharedPartnerId: null,
    };

    const { AppNav } = await import("@/components/AppNav");
    render(<AppNav />);

    expect(screen.getByRole("link", { name: "知識地圖" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "客戶" })).toBeInTheDocument();
    // Member in home workspace should NOT see team/setup
    expect(screen.queryByRole("link", { name: "成員" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /設定/i })).not.toBeInTheDocument();
  });
});

// ─── S02-2: isHomeWorkspace=false → restricted surface ───────────────────────

describe("S02-2: isHomeWorkspace=false → Knowledge Map / Products / Tasks only", () => {
  it("guest in shared workspace sees restricted nav with correct labels", async () => {
    mockPartner = {
      ...mockPartner,
      workspaceRole: "guest",
      isAdmin: false,
      accessMode: "scoped",
      authorizedEntityIds: ["entity-1"],
      sharedPartnerId: "owner-abc",
    };

    const { AppNav } = await import("@/components/AppNav");
    render(<AppNav />);

    expect(screen.getByRole("link", { name: "知識地圖" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Products" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Tasks" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "客戶" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "成員" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /設定/i })).not.toBeInTheDocument();
  });

  it("member in shared workspace sees same restricted nav", async () => {
    mockPartner = {
      ...mockPartner,
      workspaceRole: "member",
      isAdmin: false,
      accessMode: "internal",
      authorizedEntityIds: [],
      sharedPartnerId: "owner-xyz",
    };

    const { AppNav } = await import("@/components/AppNav");
    render(<AppNav />);

    expect(screen.getByRole("link", { name: "知識地圖" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Products" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Tasks" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "客戶" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "成員" })).not.toBeInTheDocument();
  });
});

// ─── S02-3: workspace entry — single workspace ────────────────────────────────

describe("S02-3: single workspace → shows '我的工作區'", () => {
  it("shows static '我的工作區' text when no availableWorkspaces field (fallback to single)", async () => {
    mockPartner = {
      ...mockPartner,
      workspaceRole: "owner",
      isAdmin: true,
      sharedPartnerId: null,
      // No availableWorkspaces field → single workspace fallback
    };

    const { AppNav } = await import("@/components/AppNav");
    render(<AppNav />);

    const entry = screen.getByTestId("workspace-entry-single");
    expect(entry).toBeInTheDocument();
    expect(entry).toHaveTextContent("我的工作區");
    // Should NOT show picker
    expect(screen.queryByTestId("workspace-entry-picker")).not.toBeInTheDocument();
  });
});

// ─── S02-4: workspace entry — multiple workspaces ─────────────────────────────

describe("S02-4: multiple workspaces → shows picker", () => {
  it("shows workspace picker when partner has availableWorkspaces with 2+ items", async () => {
    const multiWsPartner = {
      ...mockPartner,
      workspaceRole: "owner" as WorkspaceRole,
      isAdmin: true,
      sharedPartnerId: null,
      availableWorkspaces: [
        { id: "ws-1", name: "我的工作區", hasUpdate: false },
        { id: "ws-2", name: "Acme Corp", hasUpdate: true },
      ],
    };
    mockPartner = multiWsPartner as typeof mockPartner;

    const { AppNav } = await import("@/components/AppNav");
    render(<AppNav />);

    const picker = screen.getByTestId("workspace-entry-picker");
    expect(picker).toBeInTheDocument();
    // Should NOT show static label
    expect(screen.queryByTestId("workspace-entry-single")).not.toBeInTheDocument();
  });

  it("picker dropdown shows all workspace options on click", async () => {
    const multiWsPartner = {
      ...mockPartner,
      workspaceRole: "owner" as WorkspaceRole,
      isAdmin: true,
      sharedPartnerId: null,
      availableWorkspaces: [
        { id: "ws-1", name: "我的工作區", hasUpdate: false },
        { id: "ws-2", name: "Acme Corp", hasUpdate: true },
      ],
    };
    mockPartner = multiWsPartner as typeof mockPartner;

    const { AppNav } = await import("@/components/AppNav");
    render(<AppNav />);

    const pickerBtn = screen.getByTestId("workspace-entry-picker").querySelector("button")!;
    fireEvent.click(pickerBtn);

    // "我的工作區" appears in both the picker button and the dropdown list item
    const wsLabels = screen.getAllByText("我的工作區");
    expect(wsLabels.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
  });

  it("non-active workspace with hasUpdate=true shows update badge", async () => {
    const multiWsPartner = {
      ...mockPartner,
      id: "ws-1",
      workspaceRole: "owner" as WorkspaceRole,
      isAdmin: true,
      sharedPartnerId: null,
      availableWorkspaces: [
        { id: "ws-1", name: "我的工作區", hasUpdate: false },
        { id: "ws-2", name: "Acme Corp", hasUpdate: true },
      ],
    };
    mockPartner = multiWsPartner as typeof mockPartner;

    const { AppNav } = await import("@/components/AppNav");
    render(<AppNav />);

    const pickerBtn = screen.getByTestId("workspace-entry-picker").querySelector("button")!;
    fireEvent.click(pickerBtn);

    // Badge should appear for ws-2 (non-active, hasUpdate=true)
    expect(screen.getByTestId("workspace-badge-ws-2")).toBeInTheDocument();
    // No badge for active workspace (ws-1)
    expect(screen.queryByTestId("workspace-badge-ws-1")).not.toBeInTheDocument();
  });
});
