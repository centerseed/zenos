/**
 * Tests for client portal — scoped partner visibility and access control.
 *
 * DC-1: scoped partner nav shows only 專案 and 任務
 * DC-2: internal member nav unchanged
 * DC-3: non-admin redirect from /setup
 * DC-4: empty-scope prompt on tasks page
 * DC-5: external client badge in team member list
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import React from "react";

// ── Mutable partner state shared across tests ────────────────────────────────
let mockPartner: {
  id: string;
  email: string;
  displayName: string;
  apiKey: string;
  isAdmin: boolean;
  status: "active" | "invited" | "suspended";
  authorizedEntityIds: string[];
  invitedBy: null;
  createdAt: Date;
  updatedAt: Date;
} = {
  id: "partner-1",
  email: "user@test.com",
  displayName: "Test User",
  apiKey: "test-key", // pragma: allowlist secret
  isAdmin: false,
  status: "active",
  authorizedEntityIds: [],
  invitedBy: null,
  createdAt: new Date(),
  updatedAt: new Date(),
};

const mockGetIdToken = vi.fn().mockResolvedValue("fake-token");
const mockRouterReplace = vi.fn();

// ── Static top-level mocks (hoisted by vitest) ───────────────────────────────

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockRouterReplace }),
  usePathname: () => "/tasks",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { getIdToken: mockGetIdToken },
    partner: mockPartner,
    signOut: vi.fn(),
  }),
}));

vi.mock("@/components/AuthGuard", () => ({
  AuthGuard: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/McpConfigBlock", () => ({
  McpConfigBlock: () => <div data-testid="mcp-config" />,
}));

vi.mock("@/components/TaskBoard", () => ({
  TaskBoard: () => <div data-testid="task-board" />,
}));

vi.mock("@/components/TaskFilters", () => ({
  TaskFilters: () => <div data-testid="task-filters" />,
}));

vi.mock("@/components/PulseBar", () => ({
  PulseBar: () => <div />,
}));

vi.mock("@/components/ProjectProgress", () => ({
  ProjectProgress: () => <div />,
}));

vi.mock("@/components/PeopleMatrix", () => ({
  PeopleMatrix: () => <div />,
}));

vi.mock("@/components/ActivityTimeline", () => ({
  ActivityTimeline: () => <div />,
}));

vi.mock("@/components/MorningReport", () => ({
  MorningReport: () => <div />,
}));

vi.mock("@/components/LoadingState", () => ({
  LoadingState: ({ label }: { label: string }) => <div>{label}</div>,
}));

vi.mock("@/components/TaskCreateDialog", () => ({
  TaskCreateDialog: () => <div />,
}));

vi.mock("@/lib/api", () => ({
  getTasks: vi.fn().mockResolvedValue([]),
  getProjectEntities: vi.fn().mockResolvedValue([]),
  getAllEntities: vi.fn().mockResolvedValue([]),
  createTask: vi.fn(),
  updateTask: vi.fn(),
  confirmTask: vi.fn(),
  getDepartments: vi.fn().mockResolvedValue(["all"]),
  createDepartment: vi.fn(),
  deleteDepartment: vi.fn(),
  renameDepartment: vi.fn(),
  updatePartnerScope: vi.fn(),
}));

vi.mock("firebase/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof import("firebase/auth")>();
  return {
    ...actual,
    onAuthStateChanged: vi.fn(),
    signInWithPopup: vi.fn(),
    signOut: vi.fn(),
    GoogleAuthProvider: vi.fn(),
    getAuth: vi.fn(),
    sendSignInLinkToEmail: vi.fn().mockResolvedValue(undefined),
  };
});

vi.mock("@/lib/firebase", () => ({
  getAuthInstance: vi.fn(() => ({})),
}));

// ── Shared reset ─────────────────────────────────────────────────────────────

afterEach(() => {
  cleanup();
  mockRouterReplace.mockClear();
});

// ─── DC-1 & DC-2: AppNav navigation items ────────────────────────────────────

describe("AppNav — scoped partner navigation", () => {
  it("DC-1: scoped partner sees only 專案 and 任務", async () => {
    mockPartner = { ...mockPartner, authorizedEntityIds: ["entity-abc"], isAdmin: false };

    const { AppNav } = await import("@/components/AppNav");
    render(<AppNav />);

    expect(screen.getByRole("link", { name: "專案" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "任務" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "知識地圖" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "客戶" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /設定/i })).not.toBeInTheDocument();
  });

  it("DC-2: internal member sees full nav (知識地圖, 客戶, 設定)", async () => {
    mockPartner = { ...mockPartner, authorizedEntityIds: [], isAdmin: false };

    const { AppNav } = await import("@/components/AppNav");
    render(<AppNav />);

    expect(screen.getByRole("link", { name: "知識地圖" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "客戶" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /設定/i })).toBeInTheDocument();
  });

  it("DC-2: admin user sees full nav including 成員 (team)", async () => {
    mockPartner = { ...mockPartner, authorizedEntityIds: [], isAdmin: true };

    const { AppNav } = await import("@/components/AppNav");
    render(<AppNav />);

    expect(screen.getByRole("link", { name: "知識地圖" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "成員" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /設定/i })).toBeInTheDocument();
  });
});

// ─── DC-3: /setup admin guard ────────────────────────────────────────────────

describe("SetupPage — admin guard", () => {
  it("DC-3: non-admin user is redirected to /", async () => {
    mockPartner = { ...mockPartner, isAdmin: false, authorizedEntityIds: [] };

    const { default: Page } = await import("@/app/setup/page");
    render(<Page />);

    await waitFor(() => {
      expect(mockRouterReplace).toHaveBeenCalledWith("/");
    });
  });

  it("DC-3: admin user renders setup content (not redirected)", async () => {
    mockPartner = { ...mockPartner, isAdmin: true, authorizedEntityIds: [] };
    mockRouterReplace.mockClear();

    const { default: Page } = await import("@/app/setup/page");
    render(<Page />);

    // The page renders the MCP config block — meaning it was not short-circuited
    await waitFor(() => {
      expect(screen.getByTestId("mcp-config")).toBeInTheDocument();
    });
    expect(mockRouterReplace).not.toHaveBeenCalled();
  });
});

// ─── DC-4: empty-scope prompt on tasks page ──────────────────────────────────

describe("TasksPage — empty scope prompt", () => {
  it("DC-4: shows 未設定存取空間 when partner has empty authorizedEntityIds (non-admin)", async () => {
    mockPartner = { ...mockPartner, isAdmin: false, authorizedEntityIds: [] };

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ partners: [] }),
    }));

    const { TasksPage } = await import("@/app/tasks/page");
    render(<TasksPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/您的帳號尚未設定存取空間，請聯繫管理員/)
      ).toBeInTheDocument();
    });

    vi.unstubAllGlobals();
  });

  it("DC-4: does NOT show prompt when partner has authorized entities", async () => {
    mockPartner = { ...mockPartner, isAdmin: false, authorizedEntityIds: ["entity-1"] };

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ partners: [] }),
    }));

    const { TasksPage } = await import("@/app/tasks/page");
    render(<TasksPage />);

    // Wait a moment — if prompt were to appear it would appear immediately
    await new Promise((r) => setTimeout(r, 100));
    expect(
      screen.queryByText(/您的帳號尚未設定存取空間/)
    ).not.toBeInTheDocument();

    vi.unstubAllGlobals();
  });

  it("DC-4: admin user does NOT see empty-scope prompt even with empty authorizedEntityIds", async () => {
    mockPartner = { ...mockPartner, isAdmin: true, authorizedEntityIds: [] };

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ partners: [] }),
    }));

    const { TasksPage } = await import("@/app/tasks/page");
    render(<TasksPage />);

    await new Promise((r) => setTimeout(r, 100));
    expect(
      screen.queryByText(/您的帳號尚未設定存取空間/)
    ).not.toBeInTheDocument();

    vi.unstubAllGlobals();
  });
});

// ─── DC-5: External client badge in team member list ────────────────────────

describe("TeamPage — external client badge", () => {
  beforeEach(() => {
    mockPartner = { ...mockPartner, isAdmin: true, authorizedEntityIds: [] };
  });

  it("DC-5: shows 外部客戶 badge for partner with authorizedEntityIds", async () => {
    const externalPartner = {
      id: "ext-partner-1",
      email: "client@external.com",
      displayName: "External Client",
      isAdmin: false,
      status: "active" as const,
      authorizedEntityIds: ["entity-1", "entity-2"],
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ partners: [externalPartner] }),
    }));

    const { default: Page } = await import("@/app/team/page");
    render(<Page />);

    await waitFor(() => {
      expect(screen.getByText("外部客戶")).toBeInTheDocument();
    });
    expect(screen.getByText(/授權 2 個專案空間/)).toBeInTheDocument();

    vi.unstubAllGlobals();
  });

  it("DC-5: does NOT show 外部客戶 badge for partner with empty authorizedEntityIds", async () => {
    const internalPartner = {
      id: "int-partner-1",
      email: "member@internal.com",
      displayName: "Internal Member",
      isAdmin: false,
      status: "active" as const,
      authorizedEntityIds: [],
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ partners: [internalPartner] }),
    }));

    const { default: Page } = await import("@/app/team/page");
    render(<Page />);

    await waitFor(() => {
      expect(screen.getByText("member@internal.com")).toBeInTheDocument();
    });
    expect(screen.queryByText("外部客戶")).not.toBeInTheDocument();

    vi.unstubAllGlobals();
  });
});
