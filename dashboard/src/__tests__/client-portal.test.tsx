/**
 * Tests for client portal — workspaceRole-driven visibility and access control.
 *
 * DC-1: guest nav shows only shared-L1 collaboration entry points
 * DC-2: member and owner nav follow workspaceRole
 * DC-3: non-owner redirect from /setup
 * DC-4: guest empty-scope prompt on tasks page
 * DC-5: workspaceRole badges in team member list
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import React from "react";

type WorkspaceRole = "owner" | "member" | "guest";

const DEFAULT_PARTNER = {
  id: "partner-1",
  email: "user@test.com",
  displayName: "Test User",
  apiKey: "test-key", // pragma: allowlist secret
  isAdmin: false,
  workspaceRole: "guest" as WorkspaceRole,
  status: "active" as const,
  accessMode: "unassigned" as const,
  authorizedEntityIds: [] as string[],
  invitedBy: null as null,
  createdAt: new Date(),
  updatedAt: new Date(),
};

let mockPartner: Record<string, unknown> = { ...DEFAULT_PARTNER };

const mockGetIdToken = vi.fn().mockResolvedValue("fake-token");
const mockRouterReplace = vi.fn();
const getPartnersMock = vi.hoisted(() => vi.fn().mockResolvedValue([]));

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
  getPartners: (...args: unknown[]) => getPartnersMock(...args),
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

beforeEach(() => {
  mockPartner = { ...DEFAULT_PARTNER };
});

afterEach(() => {
  cleanup();
  mockRouterReplace.mockClear();
  vi.unstubAllGlobals();
});

describe("AppNav — two-stage nav (isHomeWorkspace → workspaceRole)", () => {
  it("DC-1: guest in shared workspace (sharedPartnerId set) sees only Knowledge Map / Products / Tasks", async () => {
    mockPartner = {
      ...mockPartner,
      workspaceRole: "guest",
      accessMode: "scoped",
      authorizedEntityIds: ["entity-abc"],
      sharedPartnerId: "owner-partner-id",
    };

    const { AppNav } = await import("@/components/AppNav");
    render(<AppNav />);

    expect(screen.getByRole("link", { name: "知識地圖" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Products" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Tasks" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "客戶" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /成員/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /設定/i })).not.toBeInTheDocument();
  });

  it("DC-1: member in shared workspace (sharedPartnerId set) sees only Knowledge Map / Products / Tasks", async () => {
    mockPartner = {
      ...mockPartner,
      workspaceRole: "member",
      accessMode: "internal",
      authorizedEntityIds: [],
      sharedPartnerId: "owner-partner-id",
    };

    const { AppNav } = await import("@/components/AppNav");
    render(<AppNav />);

    expect(screen.getByRole("link", { name: "知識地圖" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Products" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Tasks" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "客戶" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /成員/i })).not.toBeInTheDocument();
  });

  it("DC-2: member in home workspace sees full nav without team/setup", async () => {
    mockPartner = {
      ...mockPartner,
      workspaceRole: "member",
      accessMode: "internal",
      authorizedEntityIds: [],
    };

    const { AppNav } = await import("@/components/AppNav");
    render(<AppNav />);

    expect(screen.getByRole("link", { name: "知識地圖" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "客戶" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /成員/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /設定/i })).not.toBeInTheDocument();
  });

  it("DC-2: owner in home workspace sees team and setup entries", async () => {
    mockPartner = {
      ...mockPartner,
      workspaceRole: "owner",
      accessMode: "internal",
      authorizedEntityIds: [],
      isAdmin: true,
    };

    const { AppNav } = await import("@/components/AppNav");
    render(<AppNav />);

    expect(screen.getByRole("link", { name: "知識地圖" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "成員" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /設定/i })).toBeInTheDocument();
  });
});

describe("SetupPage — owner guard", () => {
  it("DC-3: non-owner user is redirected to /tasks", async () => {
    mockPartner = {
      ...mockPartner,
      workspaceRole: "guest",
      accessMode: "unassigned",
      authorizedEntityIds: [],
    };

    const { default: Page } = await import("@/app/setup/page");
    render(<Page />);

    await waitFor(() => {
      expect(mockRouterReplace).toHaveBeenCalledWith("/tasks");
    });
  });

  it("DC-3: owner user renders setup content (not redirected)", async () => {
    mockPartner = {
      ...mockPartner,
      workspaceRole: "owner",
      isAdmin: true,
      accessMode: "internal",
      authorizedEntityIds: [],
    };
    mockRouterReplace.mockClear();

    const { default: Page } = await import("@/app/setup/page");
    render(<Page />);

    await waitFor(() => {
      expect(screen.getByTestId("mcp-config")).toBeInTheDocument();
    });
    expect(mockRouterReplace).not.toHaveBeenCalled();
  });
});

describe("TasksPage — empty scope prompt", () => {
  it("DC-4: shows 未指派空間 prompt when guest has no shared L1 access", async () => {
    mockPartner = {
      ...mockPartner,
      workspaceRole: "guest",
      accessMode: "unassigned",
      authorizedEntityIds: [],
    };

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
  });

  it("DC-4: does NOT show prompt when guest has authorized shared L1 entities", async () => {
    mockPartner = {
      ...mockPartner,
      workspaceRole: "guest",
      accessMode: "scoped",
      authorizedEntityIds: ["entity-1"],
    };

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ partners: [] }),
    }));

    const { TasksPage } = await import("@/app/tasks/page");
    render(<TasksPage />);

    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(screen.queryByText(/您的帳號尚未設定存取空間/)).not.toBeInTheDocument();
  });

  it("DC-4: owner user does NOT see empty-scope prompt even with empty authorizedEntityIds", async () => {
    mockPartner = {
      ...mockPartner,
      workspaceRole: "owner",
      isAdmin: true,
      accessMode: "internal",
      authorizedEntityIds: [],
    };

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ partners: [] }),
    }));

    const { TasksPage } = await import("@/app/tasks/page");
    render(<TasksPage />);

    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(screen.queryByText(/您的帳號尚未設定存取空間/)).not.toBeInTheDocument();
  });
});

describe("TeamPage — workspaceRole badge", () => {
  beforeEach(() => {
    mockPartner = {
      ...mockPartner,
      workspaceRole: "owner",
      isAdmin: true,
      accessMode: "internal",
      authorizedEntityIds: [],
    };
    // Reset mock to default empty so each test fully controls its partner list
    getPartnersMock.mockReset();
    getPartnersMock.mockResolvedValue([]);
  });

  it("DC-5: shows 訪客 badge for partner with shared access", async () => {
    const externalPartner = {
      id: "ext-partner-1",
      email: "client@external.com",
      displayName: "External Client",
      isAdmin: false,
      workspaceRole: "guest" as const,
      status: "active" as const,
      accessMode: "scoped" as const,
      authorizedEntityIds: ["entity-1", "entity-2"],
    };
    getPartnersMock.mockResolvedValueOnce([externalPartner]);

    const { default: Page } = await import("@/app/team/page");
    render(<Page />);

    await waitFor(() => {
      expect(screen.getByText("訪客")).toBeInTheDocument();
    });
  });

  it("DC-5: shows 成員 badge for member partner", async () => {
    const internalPartner = {
      id: "int-partner-1",
      email: "member@internal.com",
      displayName: "Internal Member",
      isAdmin: false,
      workspaceRole: "member" as const,
      status: "active" as const,
      accessMode: "internal" as const,
      authorizedEntityIds: [],
    };
    // Use mockResolvedValue (not Once) so getPartners always returns the partner
    // even if called multiple times (e.g. React strict mode double invoke).
    getPartnersMock.mockResolvedValue([internalPartner]);

    const { default: Page } = await import("@/app/team/page");
    render(<Page />);

    await waitFor(() => {
      expect(screen.getByText("member@internal.com")).toBeInTheDocument();
    });
    // Nav link (APP_COPY.team) and the role badge both render "成員".
    // Use getAllByText to handle multiple matches, then verify the badge span exists.
    const memberTexts = screen.getAllByText("成員");
    const badgeSpan = memberTexts.find(
      (el) => el.tagName === "SPAN" && !el.closest("a")
    );
    expect(badgeSpan).toBeInTheDocument();
    expect(screen.queryByText(/授權 \d+ 個專案空間/)).not.toBeInTheDocument();
  });
});
