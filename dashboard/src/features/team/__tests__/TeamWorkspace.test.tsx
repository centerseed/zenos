/**
 * Basic render test for TeamWorkspace — B45-05
 * Mocks useTeamWorkspace so the component doesn't need Firebase/API.
 */
import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";

// Mock the hook entirely — logic lives in useTeamWorkspace; we only test UI render.
vi.mock("@/features/team/useTeamWorkspace", () => ({
  DEFAULT_ROLE_OPTIONS: ["engineering", "marketing", "product"],
  WORKSPACE_ROLE_OPTIONS: [
    { value: "member", label: "成員" },
    { value: "guest", label: "訪客" },
    { value: "unassigned", label: "未指派" },
  ],
  useTeamWorkspace: vi.fn(() => ({
    actionLoading: null,
    canManageWorkspace: true,
    departmentOptions: ["all", "engineering"],
    handleCreateDepartment: vi.fn(),
    handleDeleteDepartment: vi.fn(),
    handleDeleteInvite: vi.fn(),
    handleInvite: vi.fn(),
    handleRenameDepartment: vi.fn(),
    handleResendInvite: vi.fn(),
    handleScopeSave: vi.fn(),
    handleStatusChange: vi.fn(),
    inviteDepartment: "all",
    inviteEmail: "",
    inviteMessage: null,
    inviteWorkspaceRole: "member",
    inviting: false,
    loading: false,
    newDepartment: "",
    openScopeEditor: vi.fn(),
    partner: { id: "self-id" },
    partners: [
      {
        id: "p1",
        email: "alice@example.com",
        displayName: "Alice",
        status: "active",
        roles: ["engineering"],
        department: "engineering",
        metadata: { workspaceRole: "member" },
        authorizedEntityIds: null,
      },
      {
        id: "p2",
        email: "bob@example.com",
        displayName: "Bob",
        status: "invited",
        roles: [],
        department: "all",
        metadata: {},
        authorizedEntityIds: null,
      },
    ],
    projectEntities: [],
    scopeEditor: null,
    selectedL1Ids: [],
    selectedBootstrapL1Ids: [],
    setInviteDepartment: vi.fn(),
    setInviteEmail: vi.fn(),
    setInviteWorkspaceRole: vi.fn(),
    setNewDepartment: vi.fn(),
    setScopeEditor: vi.fn(),
    setSelectedL1Ids: vi.fn(),
    setSelectedBootstrapL1Ids: vi.fn(),
  })),
}));

// Mock LoadingState to simplify rendering
vi.mock("@/components/LoadingState", () => ({
  LoadingState: ({ label }: { label: string }) => <div>{label}</div>,
}));

// Mock partner utility functions
vi.mock("@/lib/partner", () => ({
  getPartnerAccessMode: vi.fn(() => "internal"),
  getPartnerWorkspaceRole: vi.fn(() => "member"),
  isScopedPartner: vi.fn(() => false),
}));

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: vi.fn() })),
}));

import TeamWorkspace from "../TeamWorkspace";
import * as teamHookModule from "@/features/team/useTeamWorkspace";

afterEach(() => cleanup());

describe("TeamWorkspace", () => {
  it("renders without crashing", () => {
    const { container } = render(<TeamWorkspace />);
    expect(container).toBeTruthy();
  });

  it("shows page heading 成員管理", () => {
    render(<TeamWorkspace />);
    expect(screen.getByText("成員管理")).toBeDefined();
  });

  it("shows invite form section heading", () => {
    render(<TeamWorkspace />);
    expect(screen.getByText("邀請新成員")).toBeDefined();
  });

  it("shows department section heading", () => {
    render(<TeamWorkspace />);
    expect(screen.getByText("部門清單")).toBeDefined();
  });

  it("renders member emails in table", () => {
    render(<TeamWorkspace />);
    expect(screen.getByText("alice@example.com")).toBeDefined();
    expect(screen.getByText("bob@example.com")).toBeDefined();
  });

  it("shows no className attributes on root (Zen inline-style)", () => {
    const { container } = render(<TeamWorkspace />);
    // TeamWorkspace root elements must not carry Tailwind class names
    const allElements = container.querySelectorAll("[class]");
    // Only elements from imported Zen primitives (Input/Select/Dialog/Chip etc.) may have class —
    // our outer wrappers must not. Verify outer wrappers specifically.
    const outerDiv = container.firstElementChild as HTMLElement;
    expect(outerDiv?.className ?? "").toBe("");
  });

  it("returns null when canManageWorkspace is false", () => {
    vi.spyOn(teamHookModule, "useTeamWorkspace").mockReturnValueOnce({
      canManageWorkspace: false,
      partners: [],
      departmentOptions: [],
      loading: false,
      scopeEditor: null,
    } as unknown as ReturnType<typeof teamHookModule.useTeamWorkspace>);
    const { container } = render(<TeamWorkspace />);
    expect(container.firstChild).toBeNull();
  });

  it("shows LoadingState when loading=true", () => {
    vi.spyOn(teamHookModule, "useTeamWorkspace").mockReturnValueOnce({
      actionLoading: null,
      canManageWorkspace: true,
      departmentOptions: ["all"],
      handleCreateDepartment: vi.fn(),
      handleDeleteDepartment: vi.fn(),
      handleDeleteInvite: vi.fn(),
      handleInvite: vi.fn(),
      handleRenameDepartment: vi.fn(),
      handleResendInvite: vi.fn(),
      handleScopeSave: vi.fn(),
      handleStatusChange: vi.fn(),
      inviteDepartment: "all",
      inviteEmail: "",
      inviteMessage: null,
      inviteWorkspaceRole: "member",
      inviting: false,
      loading: true,
      newDepartment: "",
      openScopeEditor: vi.fn(),
      partner: null,
      partners: [],
      projectEntities: [],
      scopeEditor: null,
      selectedL1Ids: [],
      selectedBootstrapL1Ids: [],
      setInviteDepartment: vi.fn(),
      setInviteEmail: vi.fn(),
      setInviteWorkspaceRole: vi.fn(),
      setNewDepartment: vi.fn(),
      setScopeEditor: vi.fn(),
      setSelectedL1Ids: vi.fn(),
      setSelectedBootstrapL1Ids: vi.fn(),
    } as unknown as ReturnType<typeof teamHookModule.useTeamWorkspace>);
    render(<TeamWorkspace />);
    expect(screen.getByText("正在載入成員...")).toBeDefined();
  });
});
