/**
 * S06: Route Guard Tests
 *
 * Verifies that /setup, /team, /clients redirect shared-workspace users
 * (isHomeWorkspace=false) to /tasks, and remain accessible to home-workspace
 * owners (isHomeWorkspace=true).
 *
 * Guard logic is based on ActiveWorkspaceContext.isHomeWorkspace, not on
 * hard-coded role comparisons.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, waitFor, cleanup } from "@testing-library/react";
import React from "react";

// ── Shared mocks ─────────────────────────────────────────────────────────────

const mockReplace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/components/AuthGuard", () => ({
  AuthGuard: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/AppNav", () => ({
  AppNav: () => <nav data-testid="app-nav" />,
}));

vi.mock("@/components/LoadingState", () => ({
  LoadingState: ({ label }: { label: string }) => <div>{label}</div>,
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ pushToast: vi.fn() }),
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

vi.mock("@/lib/api", () => ({
  getPartners: vi.fn().mockResolvedValue([]),
  getDepartments: vi.fn().mockResolvedValue(["all"]),
  getProjectEntities: vi.fn().mockResolvedValue([]),
  createDepartment: vi.fn(),
  deleteDepartment: vi.fn(),
  renameDepartment: vi.fn(),
  updatePartnerScope: vi.fn(),
}));

vi.mock("@/lib/crm-api", () => ({
  getDeals: vi.fn().mockResolvedValue([]),
  getCompanies: vi.fn().mockResolvedValue([]),
  patchDealStage: vi.fn(),
  createDeal: vi.fn(),
  createCompany: vi.fn(),
  // Regression: route-guard test omitted S04 exports — caused Vitest unhandled rejection
  // Found by QA on 2026-04-14
  fetchInsights: vi.fn().mockResolvedValue({ insights: [], pipeline_summary: { active_deals: 0, estimated_monthly_close_twd: 0, deals_needing_attention: 0 } }),
  fetchStaleThresholds: vi.fn().mockResolvedValue({}),
  updateStaleThresholds: vi.fn().mockResolvedValue({}),
}));

vi.mock("@dnd-kit/core", () => ({
  DndContext: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  DragOverlay: () => null,
  PointerSensor: vi.fn(),
  useSensor: vi.fn(() => ({})),
  useSensors: vi.fn(() => []),
  useDraggable: vi.fn(() => ({
    attributes: {},
    listeners: {},
    setNodeRef: vi.fn(),
    isDragging: false,
  })),
  useDroppable: vi.fn(() => ({ setNodeRef: vi.fn(), isOver: false })),
}));

// ── Partner fixtures ──────────────────────────────────────────────────────────

/** Home workspace owner — isHomeWorkspace=true, workspaceRole=owner */
const HOME_OWNER = {
  id: "home-owner-id",
  email: "owner@test.com",
  displayName: "Owner",
  apiKey: "test-key", // pragma: allowlist secret
  isAdmin: true,
  workspaceRole: "owner" as const,
  accessMode: "internal" as const,
  authorizedEntityIds: [] as string[],
  sharedPartnerId: null as null | string,
  status: "active" as const,
};

/** Shared workspace guest — isHomeWorkspace=false */
const SHARED_GUEST = {
  ...HOME_OWNER,
  id: "shared-guest-id",
  workspaceRole: "guest" as const,
  accessMode: "scoped" as const,
  authorizedEntityIds: ["entity-1"],
  sharedPartnerId: "owner-workspace-id",
  isAdmin: false,
};

/** Shared workspace member — isHomeWorkspace=false */
const SHARED_MEMBER = {
  ...HOME_OWNER,
  id: "shared-member-id",
  workspaceRole: "member" as const,
  accessMode: "internal" as const,
  authorizedEntityIds: [],
  sharedPartnerId: "owner-workspace-id",
  isAdmin: false,
};

let mockPartner: Record<string, unknown> = HOME_OWNER;

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { getIdToken: vi.fn().mockResolvedValue("fake-token") },
    partner: mockPartner,
    signOut: vi.fn(),
  }),
}));

beforeEach(() => {
  mockPartner = HOME_OWNER;
  mockReplace.mockClear();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: vi.fn().mockResolvedValue({}),
  }));
});

afterEach(() => {
  vi.unstubAllGlobals();
  cleanup();
});

// ─── /setup route guard ───────────────────────────────────────────────────────

describe("S06: /setup route guard", () => {
  it("home workspace owner can access /setup — no redirect", async () => {
    mockPartner = HOME_OWNER;
    const { default: Page } = await import("@/app/setup/page");
    render(<Page />);

    await waitFor(() => {
      expect(mockReplace).not.toHaveBeenCalled();
    });
  });

  it("shared workspace guest accessing /setup → redirected to /tasks", async () => {
    mockPartner = SHARED_GUEST;
    const { default: Page } = await import("@/app/setup/page");
    render(<Page />);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/tasks");
    });
  });

  it("shared workspace member accessing /setup → redirected to /tasks", async () => {
    mockPartner = SHARED_MEMBER;
    const { default: Page } = await import("@/app/setup/page");
    render(<Page />);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/tasks");
    });
  });

  it("guard is based on isHomeWorkspace, not hard-coded role — member in home workspace is also blocked", async () => {
    // Member in HOME workspace (no sharedPartnerId) → isHomeWorkspace=true
    // BUT workspaceRole is "member" not "owner" → canManageWorkspace=false → redirect
    // This test confirms the compound check: isHomeWorkspace && role === "owner"
    mockPartner = {
      ...HOME_OWNER,
      workspaceRole: "member" as const,
      isAdmin: false,
      sharedPartnerId: null,
    };
    const { default: Page } = await import("@/app/setup/page");
    render(<Page />);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/tasks");
    });
  });
});

// ─── /team route guard ────────────────────────────────────────────────────────

describe("S06: /team route guard", () => {
  it("home workspace owner can access /team — no redirect", async () => {
    mockPartner = HOME_OWNER;
    const { default: Page } = await import("@/app/team/page");
    render(<Page />);

    await waitFor(() => {
      expect(mockReplace).not.toHaveBeenCalled();
    });
  });

  it("shared workspace guest accessing /team → redirected to /tasks", async () => {
    mockPartner = SHARED_GUEST;
    const { default: Page } = await import("@/app/team/page");
    render(<Page />);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/tasks");
    });
  });

  it("shared workspace member accessing /team → redirected to /tasks", async () => {
    mockPartner = SHARED_MEMBER;
    const { default: Page } = await import("@/app/team/page");
    render(<Page />);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/tasks");
    });
  });

  it("guard based on isHomeWorkspace: sharedPartnerId present → always redirect regardless of role", async () => {
    // Hypothetical: owner role but operating in shared workspace
    mockPartner = {
      ...HOME_OWNER,
      workspaceRole: "owner" as const,
      sharedPartnerId: "some-other-workspace",
    };
    const { default: Page } = await import("@/app/team/page");
    render(<Page />);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/tasks");
    });
  });
});

// ─── /clients route guard ─────────────────────────────────────────────────────

describe("S06: /clients route guard", () => {
  it("home workspace owner can access /clients — no redirect", async () => {
    mockPartner = HOME_OWNER;
    const { default: Page } = await import("@/app/clients/page");
    render(<Page />);

    await waitFor(() => {
      expect(mockReplace).not.toHaveBeenCalled();
    });
  });

  it("home workspace member can access /clients — no redirect", async () => {
    mockPartner = {
      ...HOME_OWNER,
      workspaceRole: "member" as const,
      isAdmin: false,
      sharedPartnerId: null,
    };
    const { default: Page } = await import("@/app/clients/page");
    render(<Page />);

    await waitFor(() => {
      expect(mockReplace).not.toHaveBeenCalled();
    });
  });

  it("shared workspace guest accessing /clients → redirected to /tasks", async () => {
    mockPartner = SHARED_GUEST;
    const { default: Page } = await import("@/app/clients/page");
    render(<Page />);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/tasks");
    });
  });

  it("shared workspace member accessing /clients → redirected to /tasks", async () => {
    mockPartner = SHARED_MEMBER;
    const { default: Page } = await import("@/app/clients/page");
    render(<Page />);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/tasks");
    });
  });

  it("guard based on isHomeWorkspace: presence of sharedPartnerId triggers redirect", async () => {
    // Any role with sharedPartnerId = shared workspace → block
    mockPartner = {
      ...HOME_OWNER,
      isAdmin: true,
      workspaceRole: "owner" as const,
      sharedPartnerId: "foreign-workspace-id",
    };
    const { default: Page } = await import("@/app/clients/page");
    render(<Page />);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/tasks");
    });
  });
});
