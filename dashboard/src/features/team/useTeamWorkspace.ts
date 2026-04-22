"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { sendSignInLinkToEmail } from "firebase/auth";
import { useAuth } from "@/lib/auth";
import { getAuthInstance } from "@/lib/firebase";
import {
  createDepartment,
  deleteDepartment,
  deletePartner,
  getDepartments,
  getPartners,
  getProjectEntities,
  invitePartner,
  renameDepartment,
  updatePartnerScope,
  updatePartnerStatus,
} from "@/lib/api";
import { useToast } from "@/components/zen/Toast";
import type { Entity, Partner, PartnerAccessMode } from "@/types";
import { getPartnerAccessMode, getPartnerWorkspaceRole, resolveActiveWorkspace } from "@/lib/partner";

export const DEFAULT_ROLE_OPTIONS = [
  "engineering",
  "marketing",
  "product",
  "sales",
  "finance",
  "hr",
  "ops",
];

export const WORKSPACE_ROLE_OPTIONS = [
  { value: "member", label: "成員" },
  { value: "guest", label: "訪客" },
  { value: "unassigned", label: "未指派" },
] as const;

export type WorkspaceAssignment = (typeof WORKSPACE_ROLE_OPTIONS)[number]["value"];

export interface ScopeEditorState {
  partnerId: string;
  email: string;
  roles: string[];
  department: string;
  customRole: string;
  customDepartment: string;
  workspaceRole: WorkspaceAssignment;
  authorizedEntityIds: string[];
  homeWorkspaceBootstrapEntityIds: string[];
}

function deriveScopePayload(
  workspaceRole: WorkspaceAssignment,
  authorizedEntityIds: string[]
): {
  workspaceRole?: "member" | "guest";
  accessMode: PartnerAccessMode;
  authorizedEntityIds: string[];
} {
  if (workspaceRole === "member") {
    return {
      workspaceRole: "member",
      accessMode: "internal",
      authorizedEntityIds: [],
    };
  }
  if (workspaceRole === "guest") {
    return {
      workspaceRole: "guest",
      accessMode: "scoped",
      authorizedEntityIds,
    };
  }
  return {
    accessMode: "unassigned",
    authorizedEntityIds: [],
  };
}

export function useTeamWorkspace() {
  const { user, partner } = useAuth();
  const router = useRouter();
  const { pushToast } = useToast();
  const [partners, setPartners] = useState<Partner[]>([]);
  const [departments, setDepartments] = useState<string[]>(["all", ...DEFAULT_ROLE_OPTIONS]);
  const [loading, setLoading] = useState(true);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteDepartment, setInviteDepartment] = useState("all");
  const [inviteWorkspaceRole, setInviteWorkspaceRole] = useState<WorkspaceAssignment>("unassigned");
  const [inviting, setInviting] = useState(false);
  const [inviteMessage, setInviteMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [scopeEditor, setScopeEditor] = useState<ScopeEditorState | null>(null);
  const [newDepartment, setNewDepartment] = useState("");
  const [selectedL1Ids, setSelectedL1Ids] = useState<string[]>([]);
  const [selectedBootstrapL1Ids, setSelectedBootstrapL1Ids] = useState<string[]>([]);
  const [projectEntities, setProjectEntities] = useState<Entity[]>([]);
  const { workspaceRole, isHomeWorkspace } = resolveActiveWorkspace(partner);
  const canManageWorkspace = isHomeWorkspace && workspaceRole === "owner";
  const departmentOptions =
    Array.isArray(departments) && departments.length > 0 ? departments : ["all", ...DEFAULT_ROLE_OPTIONS];

  useEffect(() => {
    if (partner && !canManageWorkspace) {
      router.replace("/tasks");
    }
  }, [partner, canManageWorkspace, router]);

  const fetchPartners = useCallback(async () => {
    if (!user) return;
    try {
      const token = await user.getIdToken();
      setPartners(await getPartners(token));
    } catch (err) {
      console.error("Failed to fetch partners:", err);
    } finally {
      setLoading(false);
    }
  }, [user]);

  const fetchDepartments = useCallback(async () => {
    if (!user) return;
    try {
      const token = await user.getIdToken();
      const nextDepartments = await getDepartments(token);
      setDepartments(
        Array.isArray(nextDepartments) && nextDepartments.length > 0
          ? nextDepartments
          : ["all", ...DEFAULT_ROLE_OPTIONS]
      );
    } catch (err) {
      console.error("Failed to fetch departments:", err);
    }
  }, [user]);

  useEffect(() => {
    if (!canManageWorkspace) return;
      void fetchPartners();
      void fetchDepartments();
    user
      ?.getIdToken()
      .then((token) => getProjectEntities(token, { scope: "shareableRoots" }).then(setProjectEntities))
      .catch(console.error);
  }, [canManageWorkspace, fetchDepartments, fetchPartners, user]);

  const handleInvite = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!user || !inviteEmail.trim()) return;

      setInviting(true);
      setInviteMessage(null);

      try {
        const scopePayload = deriveScopePayload(inviteWorkspaceRole, selectedL1Ids);
        const token = await user.getIdToken();
        await invitePartner(token, {
          email: inviteEmail.trim(),
          department: inviteDepartment,
          workspace_role: scopePayload.workspaceRole,
          accessMode: scopePayload.accessMode,
          access_mode: scopePayload.accessMode,
          authorized_entity_ids: scopePayload.authorizedEntityIds,
          home_workspace_bootstrap_entity_ids:
            scopePayload.accessMode === "scoped" ? selectedBootstrapL1Ids : [],
        });
        await sendSignInLinkToEmail(getAuthInstance(), inviteEmail.trim(), {
          url: `${window.location.origin}/login`,
          handleCodeInApp: true,
        });
        setInviteMessage({ type: "success", text: `已發送邀請信至 ${inviteEmail.trim()}` });
        pushToast({
          tone: "success",
          title: "邀請已送出",
          description: `${inviteEmail.trim()} 已加入待啟用名單`,
        });
        setInviteEmail("");
        setInviteDepartment("all");
        setInviteWorkspaceRole("unassigned");
        setSelectedL1Ids([]);
        setSelectedBootstrapL1Ids([]);
        await fetchPartners();
        await fetchDepartments();
      } catch (err) {
        console.error("Invite failed:", err);
        const message = err instanceof Error ? err.message : "邀請失敗，請稍後再試";
        setInviteMessage({ type: "error", text: message });
        pushToast({ tone: "error", title: "邀請失敗", description: message });
      } finally {
        setInviting(false);
      }
    },
    [
      fetchDepartments,
      fetchPartners,
      inviteDepartment,
      inviteEmail,
      inviteWorkspaceRole,
      pushToast,
      selectedBootstrapL1Ids,
      selectedL1Ids,
      user,
    ]
  );

  const handleResendInvite = useCallback(
    async (targetPartner: Partner) => {
      setActionLoading(targetPartner.id);
      setInviteMessage(null);
      try {
        await sendSignInLinkToEmail(getAuthInstance(), targetPartner.email, {
          url: `${window.location.origin}/login`,
          handleCodeInApp: true,
        });
        setInviteMessage({ type: "success", text: `已重新寄送邀請信至 ${targetPartner.email}` });
        pushToast({ tone: "success", title: "已重新寄送邀請", description: targetPartner.email });
      } catch (err) {
        console.error("Resend invite failed:", err);
        const message = err instanceof Error ? err.message : "重新寄送失敗，請稍後再試";
        setInviteMessage({ type: "error", text: message });
        pushToast({ tone: "error", title: "重新寄送失敗", description: message });
      } finally {
        setActionLoading(null);
      }
    },
    [pushToast]
  );

  const handleDeleteInvite = useCallback(
    async (targetPartner: Partner) => {
      if (!user || !window.confirm(`確定要刪除 ${targetPartner.email} 的邀請嗎？`)) return;
      setActionLoading(targetPartner.id);
      try {
        const token = await user.getIdToken();
        await deletePartner(token, targetPartner.id);
        await fetchPartners();
        pushToast({ tone: "success", title: "邀請已刪除", description: targetPartner.email });
      } catch (err) {
        console.error("Delete invite failed:", err);
        const message = err instanceof Error ? err.message : "刪除邀請失敗，請稍後再試";
        setInviteMessage({ type: "error", text: message });
        pushToast({ tone: "error", title: "刪除邀請失敗", description: message });
      } finally {
        setActionLoading(null);
      }
    },
    [fetchPartners, pushToast, user]
  );

  const handleStatusChange = useCallback(
    async (targetPartner: Partner, status: "active" | "suspended") => {
      if (!user) return;
      setActionLoading(targetPartner.id);
      try {
        const token = await user.getIdToken();
        await updatePartnerStatus(token, targetPartner.id, status);
        await fetchPartners();
        pushToast({
          tone: "success",
          title: "狀態已更新",
          description: `${targetPartner.email} → ${status}`,
        });
      } catch (err) {
        console.error("Status change failed:", err);
        pushToast({
          tone: "error",
          title: "狀態更新失敗",
          description: err instanceof Error ? err.message : "請稍後再試",
        });
      } finally {
        setActionLoading(null);
      }
    },
    [fetchPartners, pushToast, user]
  );

  const handleScopeSave = useCallback(
    async (
      targetPartner: Partner,
      data: {
        roles: string[];
        department: string;
        workspaceRole: WorkspaceAssignment;
        authorizedEntityIds?: string[];
        homeWorkspaceBootstrapEntityIds?: string[];
      }
    ) => {
      if (!user) return;
      setActionLoading(targetPartner.id);
      try {
        const token = await user.getIdToken();
        const scopePayload = deriveScopePayload(data.workspaceRole, data.authorizedEntityIds ?? []);
        await updatePartnerScope(token, targetPartner.id, {
          roles: data.roles,
          department: data.department || "all",
          workspaceRole: scopePayload.workspaceRole,
          accessMode: scopePayload.accessMode,
          authorizedEntityIds: scopePayload.authorizedEntityIds,
          homeWorkspaceBootstrapEntityIds:
            scopePayload.accessMode === "scoped"
              ? (data.authorizedEntityIds ?? []).filter((entityId) =>
                  (data.homeWorkspaceBootstrapEntityIds ?? []).includes(entityId)
                )
              : [],
        });
        await fetchPartners();
        await fetchDepartments();
        setScopeEditor(null);
        pushToast({ tone: "success", title: "成員範圍已更新", description: targetPartner.email });
      } catch (err) {
        console.error("Scope change failed:", err);
        const message = err instanceof Error ? err.message : "更新 scope 失敗";
        setInviteMessage({ type: "error", text: message });
        pushToast({ tone: "error", title: "權限範圍更新失敗", description: message });
      } finally {
        setActionLoading(null);
      }
    },
    [fetchDepartments, fetchPartners, pushToast, user]
  );

  const handleCreateDepartment = useCallback(async () => {
    if (!user || !newDepartment.trim()) return;
    try {
      const token = await user.getIdToken();
      setDepartments(await createDepartment(token, newDepartment.trim()));
      setNewDepartment("");
      pushToast({ tone: "success", title: "已新增部門", description: newDepartment.trim() });
    } catch (err) {
      pushToast({
        tone: "error",
        title: "新增部門失敗",
        description: err instanceof Error ? err.message : "請稍後再試",
      });
    }
  }, [newDepartment, pushToast, user]);

  const handleRenameDepartment = useCallback(
    async (currentName: string) => {
      if (!user) return;
      const nextName = window.prompt("輸入新的部門名稱", currentName)?.trim();
      if (!nextName || nextName === currentName) return;
      try {
        const token = await user.getIdToken();
        setDepartments(await renameDepartment(token, currentName, nextName));
        await fetchPartners();
        pushToast({
          tone: "success",
          title: "部門已重新命名",
          description: `${currentName} → ${nextName}`,
        });
      } catch (err) {
        pushToast({
          tone: "error",
          title: "部門重新命名失敗",
          description: err instanceof Error ? err.message : "請稍後再試",
        });
      }
    },
    [fetchPartners, pushToast, user]
  );

  const handleDeleteDepartment = useCallback(
    async (name: string) => {
      if (!user || !window.confirm(`確定刪除部門 ${name}？現有成員會改回 all。`)) return;
      try {
        const token = await user.getIdToken();
        setDepartments(await deleteDepartment(token, name));
        await fetchPartners();
        pushToast({ tone: "success", title: "部門已刪除", description: `${name} 的成員已移回 all` });
      } catch (err) {
        pushToast({
          tone: "error",
          title: "刪除部門失敗",
          description: err instanceof Error ? err.message : "請稍後再試",
        });
      }
    },
    [fetchPartners, pushToast, user]
  );

  const openScopeEditor = useCallback((targetPartner: Partner) => {
    const entityIds = targetPartner.authorizedEntityIds ?? [];
    const accessMode = getPartnerAccessMode(targetPartner);
    const workspaceRole: WorkspaceAssignment =
      accessMode === "unassigned"
        ? "unassigned"
        : getPartnerWorkspaceRole(targetPartner) === "member"
          ? "member"
          : "guest";
    setScopeEditor({
      partnerId: targetPartner.id,
      email: targetPartner.email,
      roles: [...(targetPartner.roles || [])],
      department: targetPartner.department || "all",
      customRole: "",
      customDepartment: "",
      workspaceRole,
      authorizedEntityIds: [...entityIds],
      homeWorkspaceBootstrapEntityIds: [
        ...(
          targetPartner.preferences?.homeWorkspaceBootstrap?.sourceEntityIds?.filter((entityId) =>
            entityIds.includes(entityId)
          ) ?? []
        ),
      ],
    });
  }, []);

  return {
    actionLoading,
    canManageWorkspace,
    departmentOptions,
    handleCreateDepartment,
    handleDeleteDepartment,
    handleDeleteInvite,
    handleInvite,
    handleRenameDepartment,
    handleResendInvite,
    handleScopeSave,
    handleStatusChange,
    inviteDepartment,
    inviteEmail,
    inviteMessage,
    inviteWorkspaceRole,
    inviting,
    loading,
    newDepartment,
    openScopeEditor,
    partner,
    partners,
    projectEntities,
    scopeEditor,
    selectedL1Ids,
    selectedBootstrapL1Ids,
    setInviteDepartment,
    setInviteEmail,
    setInviteWorkspaceRole,
    setNewDepartment,
    setScopeEditor,
    setSelectedL1Ids,
    setSelectedBootstrapL1Ids,
  };
}
