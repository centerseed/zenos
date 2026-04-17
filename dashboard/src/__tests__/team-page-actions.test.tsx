/**
 * Tests for Team page Resend and Delete invite actions.
 *
 * Since TeamPage relies on AuthGuard + useAuth + Firebase, we test the
 * handler logic and UI button rendering with mocked dependencies.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";

// ── Mock next/navigation ────────────────────────────────────────────────────
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
}));

// ── Mock AuthGuard to render children directly ───────────────────────────────
vi.mock("@/components/AuthGuard", () => ({
  AuthGuard: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// ── Mock AppNav ──────────────────────────────────────────────────────────────
vi.mock("@/components/AppNav", () => ({
  AppNav: () => <nav data-testid="app-nav" />,
}));

// ── Mock LoadingState ────────────────────────────────────────────────────────
vi.mock("@/components/LoadingState", () => ({
  LoadingState: ({ label }: { label: string }) => <div>{label}</div>,
}));

// ── Mock sendSignInLinkToEmail (already in setup.ts mocks firebase/auth) ─────
// setup.ts already mocks firebase/auth, but we need sendSignInLinkToEmail
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

// ── Mock useAuth ─────────────────────────────────────────────────────────────
const mockGetIdToken = vi.fn().mockResolvedValue("fake-id-token");
const getPartnersMock = vi.hoisted(() => vi.fn());
const updatePartnerScopeMock = vi.hoisted(() => vi.fn());
const deletePartnerMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { getIdToken: mockGetIdToken },
    partner: {
      id: "admin-partner-id",
      email: "admin@test.com",
      displayName: "Admin",
      isAdmin: true,
      workspaceRole: "owner",
      accessMode: "internal",
      status: "active",
    },
  }),
}));

vi.mock("@/lib/api", () => ({
  getPartners: (...args: unknown[]) => getPartnersMock(...args),
  getDepartments: vi.fn().mockResolvedValue(["all"]),
  getProjectEntities: vi.fn().mockResolvedValue([]),
  createDepartment: vi.fn(),
  deleteDepartment: vi.fn(),
  renameDepartment: vi.fn(),
  updatePartnerScope: (...args: unknown[]) => updatePartnerScopeMock(...args),
  deletePartner: (...args: unknown[]) => deletePartnerMock(...args),
}));

// ── Helpers ──────────────────────────────────────────────────────────────────
function mockFetch(body: unknown, ok = true, status = 200) {
  return vi.fn().mockResolvedValue({
    ok,
    status,
    json: vi.fn().mockResolvedValue(body),
  });
}

const INVITED_PARTNER = {
  id: "invited-partner-id",
  email: "invited@test.com",
  displayName: "invited@test.com",
  isAdmin: false,
  workspaceRole: "guest" as const,
  status: "invited" as const,
  accessMode: "unassigned" as const,
  invitedBy: "admin@test.com",
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
  sharedPartnerId: "admin-partner-id",
};

const ACTIVE_GUEST_PARTNER = {
  id: "active-guest-id",
  email: "guest@test.com",
  displayName: "Guest User",
  isAdmin: false,
  workspaceRole: "guest" as const,
  status: "active" as const,
  accessMode: "scoped" as const,
  authorizedEntityIds: ["entity-1"],
  invitedBy: "admin@test.com",
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
  sharedPartnerId: "admin-partner-id",
  roles: [],
  department: "all",
};

getPartnersMock.mockResolvedValue([INVITED_PARTNER]);

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch({ partners: [INVITED_PARTNER] }));
  vi.stubGlobal("confirm", vi.fn().mockReturnValue(true));
  deletePartnerMock.mockReset();
  deletePartnerMock.mockResolvedValue(undefined);
  updatePartnerScopeMock.mockReset();
  updatePartnerScopeMock.mockResolvedValue(ACTIVE_GUEST_PARTNER);
});

afterEach(() => {
  vi.unstubAllGlobals();
  cleanup();
});

// Lazy import to avoid module-level issues
async function renderTeamPage() {
  const { default: Page } = await import("@/app/(protected)/team/page");
  return render(<Page />);
}

// ─── Tests ───────────────────────────────────────────────────────────────────

describe("Team page — invited partner actions", () => {
  it("shows Resend button for invited partner", async () => {
    await renderTeamPage();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /resend invite to invited@test\.com/i })).toBeInTheDocument();
    });
  });

  it("shows Delete button for invited partner", async () => {
    await renderTeamPage();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /delete invite for invited@test\.com/i })).toBeInTheDocument();
    });
  });

  it("Resend button calls sendSignInLinkToEmail with correct email", async () => {
    const { sendSignInLinkToEmail } = await import("firebase/auth");
    await renderTeamPage();

    const resendBtn = await screen.findByRole("button", { name: /resend invite to invited@test\.com/i });
    fireEvent.click(resendBtn);

    await waitFor(() => {
      expect(sendSignInLinkToEmail).toHaveBeenCalledWith(
        expect.anything(),
        "invited@test.com",
        expect.objectContaining({ handleCodeInApp: true })
      );
    });
  });

  it("Resend button shows success message on success", async () => {
    await renderTeamPage();

    const resendBtn = await screen.findByRole("button", { name: /resend invite to invited@test\.com/i });
    fireEvent.click(resendBtn);

    await waitFor(() => {
      expect(screen.getByText(/已重新寄送邀請信至 invited@test\.com/)).toBeInTheDocument();
    });
  });

  it("Resend button shows error message on failure", async () => {
    const { sendSignInLinkToEmail } = await import("firebase/auth");
    vi.mocked(sendSignInLinkToEmail).mockRejectedValueOnce(new Error("Firebase error"));

    await renderTeamPage();

    const resendBtn = await screen.findByRole("button", { name: /resend invite to invited@test\.com/i });
    fireEvent.click(resendBtn);

    await waitFor(() => {
      expect(screen.getByText("Firebase error")).toBeInTheDocument();
    });
  });

  it("Delete button shows confirm dialog before deleting", async () => {
    const confirmSpy = vi.fn().mockReturnValue(false); // cancel
    vi.stubGlobal("confirm", confirmSpy);

    await renderTeamPage();

    const deleteBtn = await screen.findByRole("button", { name: /delete invite for invited@test\.com/i });
    fireEvent.click(deleteBtn);

    expect(confirmSpy).toHaveBeenCalledWith(
      expect.stringContaining("invited@test.com")
    );
  });

  it("Delete button does NOT call API when confirm is cancelled", async () => {
    vi.stubGlobal("confirm", vi.fn().mockReturnValue(false));
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ partners: [INVITED_PARTNER] }),
    });
    vi.stubGlobal("fetch", fetchSpy);

    await renderTeamPage();

    // Wait for initial fetch (list partners)
    await waitFor(() => screen.findByRole("button", { name: /delete invite for invited@test\.com/i }));

    const deleteBtn = screen.getByRole("button", { name: /delete invite for invited@test\.com/i });
    fireEvent.click(deleteBtn);

    // Confirm cancelled — no DELETE call should follow the initial GET
    const calls = fetchSpy.mock.calls;
    const deleteCalls = calls.filter(([url, opts]) => opts?.method === "DELETE");
    expect(deleteCalls).toHaveLength(0);
  });

  it("Delete button calls DELETE /api/partners/{id} on confirm", async () => {
    vi.stubGlobal("confirm", vi.fn().mockReturnValue(true));

    await renderTeamPage();

    const deleteBtn = await screen.findByRole("button", { name: /delete invite for invited@test\.com/i });
    fireEvent.click(deleteBtn);

    await waitFor(() => {
      expect(deletePartnerMock).toHaveBeenCalledWith("fake-id-token", INVITED_PARTNER.id);
    });
  });

  it("Delete button is disabled while action is loading", async () => {
    // Make DELETE slow so we can check disabled state
    const fetchSpy = vi.fn().mockImplementation((url: string, opts?: RequestInit) => {
      if (opts?.method === "DELETE") {
        return new Promise((resolve) => setTimeout(() => resolve({ ok: true, status: 204, json: vi.fn() }), 500));
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue({ partners: [INVITED_PARTNER] }),
      });
    });
    vi.stubGlobal("fetch", fetchSpy);
    vi.stubGlobal("confirm", vi.fn().mockReturnValue(true));

    await renderTeamPage();

    const deleteBtn = await screen.findByRole("button", { name: /delete invite for invited@test\.com/i });
    fireEvent.click(deleteBtn);

    // Button should be disabled immediately after click
    await waitFor(() => {
      expect(deleteBtn).toBeDisabled();
    });
  });
});

describe("Team page — workspace role editor", () => {
  it("saves member role through updatePartnerScope", async () => {
    getPartnersMock.mockResolvedValueOnce([ACTIVE_GUEST_PARTNER]).mockResolvedValue([ACTIVE_GUEST_PARTNER]);

    await renderTeamPage();

    const editButton = await screen.findByRole("button", { name: /編輯 guest@test\.com 的權限範圍/i });
    fireEvent.click(editButton);

    fireEvent.change(screen.getByLabelText("成員工作區角色"), {
      target: { value: "member" },
    });
    fireEvent.click(screen.getByRole("button", { name: "儲存範圍" }));

    await waitFor(() => {
      expect(updatePartnerScopeMock).toHaveBeenCalledWith(
        "fake-id-token",
        "active-guest-id",
        expect.objectContaining({
          roles: [],
          department: "all",
          workspaceRole: "member",
          accessMode: "internal",
          authorizedEntityIds: [],
        })
      );
    });
  });
});
