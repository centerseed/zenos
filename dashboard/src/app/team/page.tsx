"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { sendSignInLinkToEmail } from "firebase/auth";
import { useAuth } from "@/lib/auth";
import { getAuthInstance } from "@/lib/firebase";
import {
  createDepartment,
  deleteDepartment,
  getDepartments,
  getPartners,
  getProjectEntities,
  renameDepartment,
  updatePartnerScope,
} from "@/lib/api";
import { AuthGuard } from "@/components/AuthGuard";
import { AppNav } from "@/components/AppNav";
import { LoadingState } from "@/components/LoadingState";
import { useToast } from "@/components/ui/toast";
import type { Entity, Partner } from "@/types";
import {
  getPartnerAccessMode,
  getPartnerWorkspaceRole,
  resolveActiveWorkspace,
  isScopedPartner,
} from "@/lib/partner";

const API_URL = process.env.NEXT_PUBLIC_MCP_API_URL || "https://zenos-mcp-165893875709.asia-east1.run.app";
const DEFAULT_ROLE_OPTIONS = [
  "engineering",
  "marketing",
  "product",
  "sales",
  "finance",
  "hr",
  "ops",
];
const ACCESS_MODE_OPTIONS = [
  { value: "internal", label: "內部成員" },
  { value: "scoped", label: "已分享空間" },
  { value: "unassigned", label: "未指派空間" },
] as const;
function TeamPage() {
  const { user, partner } = useAuth();
  const router = useRouter();
  const { pushToast } = useToast();
  const [partners, setPartners] = useState<Partner[]>([]);
  const [departments, setDepartments] = useState<string[]>(["all", ...DEFAULT_ROLE_OPTIONS]);
  const [loading, setLoading] = useState(true);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteDepartment, setInviteDepartment] = useState("all");
  const [inviteAccessMode, setInviteAccessMode] = useState<"internal" | "scoped" | "unassigned">("unassigned");
  const [inviting, setInviting] = useState(false);
  const [inviteMessage, setInviteMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [scopeEditor, setScopeEditor] = useState<{
    partnerId: string;
    email: string;
    roles: string[];
    department: string;
    customRole: string;
    customDepartment: string;
    accessMode: "internal" | "scoped" | "unassigned";
    authorizedEntityIds: string[];
  } | null>(null);
  const [newDepartment, setNewDepartment] = useState("");
  const [selectedL1Ids, setSelectedL1Ids] = useState<string[]>([]);
  const [projectEntities, setProjectEntities] = useState<Entity[]>([]);
  const { workspaceRole, isHomeWorkspace } = resolveActiveWorkspace(partner);
  const canManageWorkspace = isHomeWorkspace && workspaceRole === "owner";
  const departmentOptions = Array.isArray(departments) && departments.length > 0
    ? departments
    : ["all", ...DEFAULT_ROLE_OPTIONS];

  // Route guard: redirect non-owner or shared-workspace users away from company management UI
  useEffect(() => {
    if (partner && !canManageWorkspace) {
      router.replace("/tasks");
    }
  }, [partner, canManageWorkspace, router]);

  const fetchPartners = useCallback(async () => {
    if (!user) return;
    try {
      const token = await user.getIdToken();
      const data = await getPartners(token);
      setPartners(data);
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
      setDepartments(Array.isArray(nextDepartments) && nextDepartments.length > 0 ? nextDepartments : ["all", ...DEFAULT_ROLE_OPTIONS]);
    } catch (err) {
      console.error("Failed to fetch departments:", err);
    }
  }, [user]);

  useEffect(() => {
    if (canManageWorkspace) {
      fetchPartners();
      fetchDepartments();
      user?.getIdToken().then((token) =>
        getProjectEntities(token).then(setProjectEntities).catch(console.error)
      );
    }
  }, [canManageWorkspace, fetchPartners, fetchDepartments, user]);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user || !inviteEmail.trim()) return;

    setInviting(true);
    setInviteMessage(null);

    try {
      const effectiveAccessMode =
        inviteAccessMode === "scoped" && selectedL1Ids.length > 0 ? "scoped" : inviteAccessMode === "internal" ? "internal" : "unassigned";
      const token = await user.getIdToken();
      const res = await fetch(`${API_URL}/api/partners/invite`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: inviteEmail.trim(),
          department: inviteDepartment,
          accessMode: effectiveAccessMode,
          access_mode: effectiveAccessMode,
          authorized_entity_ids: effectiveAccessMode === "scoped" ? selectedL1Ids : [],
        }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({ message: "Unknown error" }));
        throw new Error(body.message || body.detail || `Failed: ${res.status}`);
      }

      // Send Firebase email link
      const actionCodeSettings = {
        url: `${window.location.origin}/login`,
        handleCodeInApp: true,
      };
      await sendSignInLinkToEmail(
        getAuthInstance(),
        inviteEmail.trim(),
        actionCodeSettings
      );

      setInviteMessage({ type: "success", text: `已發送邀請信至 ${inviteEmail.trim()}` });
      pushToast({ tone: "success", title: "邀請已送出", description: `${inviteEmail.trim()} 已加入待啟用名單` });
      setInviteEmail("");
      setInviteDepartment("all");
      setInviteAccessMode("unassigned");
      setSelectedL1Ids([]);
      await fetchPartners();
      await fetchDepartments();
    } catch (err) {
      console.error("Invite failed:", err);
      setInviteMessage({
        type: "error",
        text: err instanceof Error ? err.message : "邀請失敗，請稍後再試",
      });
      pushToast({ tone: "error", title: "邀請失敗", description: err instanceof Error ? err.message : "請稍後再試" });
    } finally {
      setInviting(false);
    }
  };

  const handleResendInvite = async (targetPartner: Partner) => {
    if (!user) return;
    setActionLoading(targetPartner.id);
    setInviteMessage(null);
    try {
      const actionCodeSettings = {
        url: `${window.location.origin}/login`,
        handleCodeInApp: true,
      };
      await sendSignInLinkToEmail(
        getAuthInstance(),
        targetPartner.email,
        actionCodeSettings
      );
      setInviteMessage({ type: "success", text: `已重新寄送邀請信至 ${targetPartner.email}` });
      pushToast({ tone: "success", title: "已重新寄送邀請", description: targetPartner.email });
    } catch (err) {
      console.error("Resend invite failed:", err);
      setInviteMessage({
        type: "error",
        text: err instanceof Error ? err.message : "重新寄送失敗，請稍後再試",
      });
      pushToast({ tone: "error", title: "重新寄送失敗", description: err instanceof Error ? err.message : "請稍後再試" });
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteInvite = async (targetPartner: Partner) => {
    if (!user) return;
    if (!window.confirm(`確定要刪除 ${targetPartner.email} 的邀請嗎？`)) return;
    setActionLoading(targetPartner.id);
    try {
      const token = await user.getIdToken();
      const res = await fetch(`${API_URL}/api/partners/${targetPartner.id}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ message: "Unknown error" }));
        throw new Error(body.message || body.detail || `Failed: ${res.status}`);
      }
      await fetchPartners();
      pushToast({ tone: "success", title: "邀請已刪除", description: targetPartner.email });
    } catch (err) {
      console.error("Delete invite failed:", err);
      setInviteMessage({
        type: "error",
        text: err instanceof Error ? err.message : "刪除邀請失敗，請稍後再試",
      });
      pushToast({ tone: "error", title: "刪除邀請失敗", description: err instanceof Error ? err.message : "請稍後再試" });
    } finally {
      setActionLoading(null);
    }
  };

  const handleRoleChange = async (targetPartner: Partner, isAdmin: boolean) => {
    if (!user) return;
    setActionLoading(targetPartner.id);
    try {
      const token = await user.getIdToken();
      const res = await fetch(`${API_URL}/api/partners/${targetPartner.id}/role`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ isAdmin }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ message: "Unknown error" }));
        throw new Error(body.message || body.detail || `Failed: ${res.status}`);
      }
      await fetchPartners();
      pushToast({ tone: "success", title: isAdmin ? "已升為管理員" : "已改為一般成員", description: targetPartner.email });
    } catch (err) {
      console.error("Role change failed:", err);
      pushToast({ tone: "error", title: "角色更新失敗", description: err instanceof Error ? err.message : "請稍後再試" });
    } finally {
      setActionLoading(null);
    }
  };

  const handleStatusChange = async (
    targetPartner: Partner,
    status: "active" | "suspended"
  ) => {
    if (!user) return;
    setActionLoading(targetPartner.id);
    try {
      const token = await user.getIdToken();
      const res = await fetch(
        `${API_URL}/api/partners/${targetPartner.id}/status`,
        {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ status }),
        }
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({ message: "Unknown error" }));
        throw new Error(body.message || body.detail || `Failed: ${res.status}`);
      }
      await fetchPartners();
      pushToast({ tone: "success", title: "狀態已更新", description: `${targetPartner.email} → ${status}` });
    } catch (err) {
      console.error("Status change failed:", err);
      pushToast({ tone: "error", title: "狀態更新失敗", description: err instanceof Error ? err.message : "請稍後再試" });
    } finally {
      setActionLoading(null);
    }
  };

  const handleScopeSave = async (
    targetPartner: Partner,
    data: {
      roles: string[];
      department: string;
      accessMode: "internal" | "scoped" | "unassigned";
      authorizedEntityIds?: string[];
    }
  ) => {
    if (!user) return;
    setActionLoading(targetPartner.id);
    try {
      const token = await user.getIdToken();
      await updatePartnerScope(token, targetPartner.id, {
        roles: data.roles,
        department: data.department || "all",
        accessMode: data.accessMode,
        authorizedEntityIds: data.authorizedEntityIds,
      });
      await fetchPartners();
      await fetchDepartments();
      setScopeEditor(null);
      pushToast({ tone: "success", title: "成員範圍已更新", description: targetPartner.email });
    } catch (err) {
      console.error("Scope change failed:", err);
      setInviteMessage({
        type: "error",
        text: err instanceof Error ? err.message : "更新 scope 失敗",
      });
      pushToast({ tone: "error", title: "權限範圍更新失敗", description: err instanceof Error ? err.message : "請稍後再試" });
    } finally {
      setActionLoading(null);
    }
  };

  const handleCreateDepartment = async () => {
    if (!user || !newDepartment.trim()) return;
    try {
      const token = await user.getIdToken();
      const next = await createDepartment(token, newDepartment.trim());
      setDepartments(next);
      setNewDepartment("");
      pushToast({ tone: "success", title: "已新增部門", description: newDepartment.trim() });
    } catch (err) {
      pushToast({ tone: "error", title: "新增部門失敗", description: err instanceof Error ? err.message : "請稍後再試" });
    }
  };

  const handleRenameDepartment = async (currentName: string) => {
    if (!user) return;
    const nextName = window.prompt("輸入新的部門名稱", currentName)?.trim();
    if (!nextName || nextName === currentName) return;
    try {
      const token = await user.getIdToken();
      setDepartments(await renameDepartment(token, currentName, nextName));
      await fetchPartners();
      pushToast({ tone: "success", title: "部門已重新命名", description: `${currentName} → ${nextName}` });
    } catch (err) {
      pushToast({ tone: "error", title: "部門重新命名失敗", description: err instanceof Error ? err.message : "請稍後再試" });
    }
  };

  const handleDeleteDepartment = async (name: string) => {
    if (!user) return;
    if (!window.confirm(`確定刪除部門 ${name}？現有成員會改回 all。`)) return;
    try {
      const token = await user.getIdToken();
      setDepartments(await deleteDepartment(token, name));
      await fetchPartners();
      pushToast({ tone: "success", title: "部門已刪除", description: `${name} 的成員已移回 all` });
    } catch (err) {
      pushToast({ tone: "error", title: "刪除部門失敗", description: err instanceof Error ? err.message : "請稍後再試" });
    }
  };

  const openScopeEditor = (p: Partner) => {
    const entityIds = p.authorizedEntityIds ?? [];
    const accessMode = getPartnerAccessMode(p);
    setScopeEditor({
      partnerId: p.id,
      email: p.email,
      roles: [...(p.roles || [])],
      department: p.department || "all",
      customRole: "",
      customDepartment: "",
      accessMode,
      authorizedEntityIds: [...entityIds],
    });
  };

  if (!canManageWorkspace) return null;

  const activeCount = partners.filter((p) => p.status === "active").length;
  const invitedCount = partners.filter((p) => p.status === "invited").length;

  return (
    <div className="min-h-screen">
      <AppNav />

      <main id="main-content" className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-semibold text-white">成員管理</h2>
            <p className="text-sm text-muted-foreground mt-1">
              共 {partners.length} 位成員 &middot; {activeCount} 位啟用中
              {invitedCount > 0 && ` \u00B7 ${invitedCount} 位待啟用`}
            </p>
          </div>
        </div>

        {/* Invite Form */}
        <div className="bg-card border border-border rounded-lg p-6 mb-6">
          <h3 className="text-sm font-medium text-white mb-4">邀請新成員</h3>
          <form onSubmit={handleInvite} className="flex flex-col gap-3">
            <div className="flex flex-col gap-3 md:flex-row md:items-center">
              <input
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="email@example.com"
                aria-label="邀請成員信箱"
                required
                className="flex-1 bg-background border border-border rounded-lg px-4 py-2 text-sm text-white placeholder-muted-foreground focus:outline-none focus:border-ring transition-colors"
              />
              <select
                value={inviteDepartment}
                onChange={(e) => setInviteDepartment(e.target.value)}
                className="bg-background border border-border rounded-lg px-4 py-2 text-sm text-white min-w-40"
                aria-label="邀請預設部門"
              >
                {departmentOptions.map((department) => (
                  <option key={department} value={department}>
                    {department}
                  </option>
                ))}
              </select>
              <button
                type="submit"
                aria-label="送出邀請"
                disabled={inviting || !inviteEmail.trim()}
                className="bg-primary hover:bg-primary/80 text-primary-foreground text-sm font-medium px-4 py-2 rounded-lg transition-all active:scale-95 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {inviting ? "送出中..." : "送出邀請"}
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <label className="text-sm text-foreground">存取模式</label>
              <select
                value={inviteAccessMode}
                onChange={(e) => {
                  const next = e.target.value as typeof inviteAccessMode;
                  setInviteAccessMode(next);
                  if (next !== "scoped") setSelectedL1Ids([]);
                }}
                aria-label="邀請存取模式"
                className="bg-background border border-border rounded-lg px-4 py-2 text-sm text-white min-w-40"
              >
                {ACCESS_MODE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            {inviteAccessMode === "scoped" && (
              <div className="border border-border rounded-lg p-3 space-y-2">
                <p className="text-xs text-muted-foreground">選擇可存取的專案空間：</p>
                {projectEntities.length === 0 ? (
                  <p className="text-xs text-muted-foreground">尚無專案空間</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {projectEntities.map((entity) => (
                      <label
                        key={entity.id}
                        className="flex items-center gap-1.5 text-sm text-foreground cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={selectedL1Ids.includes(entity.id)}
                          onChange={(e) => {
                            setSelectedL1Ids((prev) =>
                              e.target.checked
                                ? [...prev, entity.id]
                                : prev.filter((id) => id !== entity.id)
                            );
                          }}
                        />
                        {entity.name}
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )}
          </form>
          {inviteMessage && (
            <p
              className={`text-sm mt-3 ${
                inviteMessage.type === "success" ? "text-green-400" : "text-red-400"
              }`}
            >
              {inviteMessage.text}
            </p>
          )}
        </div>

        <div className="bg-card border border-border rounded-lg p-6 mb-6 space-y-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h3 className="text-sm font-medium text-white">部門清單</h3>
              <p className="text-xs text-muted-foreground mt-1">可新增、改名、刪除；刪除時既有成員會移回 all。</p>
            </div>
            <div className="flex w-full max-w-md items-center gap-2">
              <input
                value={newDepartment}
                onChange={(e) => setNewDepartment(e.target.value)}
                placeholder="新增部門名稱"
                className="flex-1 bg-background border border-border rounded-lg px-4 py-2 text-sm text-white"
              />
              <button
                type="button"
                onClick={handleCreateDepartment}
                className="bg-secondary hover:bg-secondary/80 text-foreground text-sm font-medium px-4 py-2 rounded-lg transition-all active:scale-95"
              >
                新增
              </button>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {departmentOptions.map((department) => (
              <div
                key={department}
                className="inline-flex items-center gap-2 rounded-full border border-border bg-background px-3 py-1.5 text-xs text-foreground"
              >
                <span>{department}</span>
                {department !== "all" && (
                  <>
                    <button
                      type="button"
                      onClick={() => handleRenameDepartment(department)}
                      className="text-blue-300 transition-all hover:text-blue-200 active:scale-95"
                    >
                      改名
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeleteDepartment(department)}
                      className="text-rose-300 transition-all hover:text-rose-200 active:scale-95"
                    >
                      刪除
                    </button>
                  </>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Partner List */}
        {loading ? (
          <LoadingState label="正在載入成員..." />
        ) : partners.length === 0 ? (
          <div className="text-center py-12 bg-card rounded-lg border border-border">
            <p className="text-muted-foreground">目前還沒有任何成員。</p>
          </div>
        ) : (
          <div className="bg-card border border-border rounded-lg overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-6 py-3">
                    信箱
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-6 py-3">
                    名稱
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-6 py-3">
                    權限範圍
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-6 py-3">
                    狀態
                  </th>
                  <th className="text-right text-xs font-medium text-muted-foreground uppercase tracking-wider px-6 py-3">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody>
                {partners.map((p) => {
                  const isSelf = p.id === partner?.id;
                  const isLoading = actionLoading === p.id;
                  const accessMode = getPartnerAccessMode(p);
                  const partnerWorkspaceRole = getPartnerWorkspaceRole(p);
                  const roleLabel =
                    partnerWorkspaceRole === "owner"
                      ? "擁有者"
                      : partnerWorkspaceRole === "member"
                        ? "成員"
                        : "訪客";
                  const accessModeLabel =
                    accessMode === "scoped"
                      ? "已分享空間"
                      : accessMode === "internal"
                        ? "內部成員"
                        : "未指派空間";
                  return (
                    <tr
                      key={p.id}
                      className={`border-b border-border last:border-b-0 transition-colors ${
                        p.status === "invited" ? "opacity-60" : ""
                      }`}
                    >
                      <td className="px-6 py-4 text-sm text-white">{p.email}</td>
                      <td className="px-6 py-4 text-sm text-muted-foreground">
                        {p.displayName || "--"}
                      </td>
                      <td className="px-6 py-4">
                        <div className="space-y-2 min-w-[220px]">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                              partnerWorkspaceRole === "owner"
                                ? "bg-purple-500/10 text-purple-400 border border-purple-500/20"
                                : "bg-secondary text-muted-foreground border border-border"
                            }`}
                          >
                            {roleLabel}
                          </span>
                          {partnerWorkspaceRole !== "owner" && (
                            <div className="space-y-1">
                              <div className="flex flex-wrap items-center gap-1">
                                <span
                                  className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium border ${
                                    accessMode === "scoped"
                                      ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                                      : accessMode === "internal"
                                        ? "bg-blue-500/10 text-blue-300 border-blue-500/20"
                                        : "bg-slate-500/10 text-slate-300 border-slate-500/20"
                                  }`}
                                >
                                  {accessModeLabel}
                                </span>
                                {isScopedPartner(p) && (
                                  <span className="text-[11px] text-muted-foreground">
                                    授權 {p.authorizedEntityIds!.length} 個專案空間
                                  </span>
                                )}
                              </div>
                              <div className="flex flex-wrap gap-1">
                                {(p.roles || []).length === 0 ? (
                                  <span className="text-[11px] text-muted-foreground">角色：（未設定）</span>
                                ) : (
                                  (p.roles || []).map((r) => (
                                    <span
                                      key={`${p.id}-${r}`}
                                      className="inline-flex items-center px-2 py-0.5 rounded text-[11px] bg-blue-500/10 text-blue-300 border border-blue-500/20"
                                    >
                                      {r}
                                    </span>
                                  ))
                                )}
                              </div>
                              <div className="text-[11px] text-muted-foreground">
                                部門：<span className="text-foreground">{p.department || "all"}</span>
                              </div>
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <StatusBadge status={p.status} />
                      </td>
                      <td className="px-6 py-4 text-right">
                        {isSelf ? (
                          <span className="text-xs text-muted-foreground">你自己</span>
                        ) : (
                          <div className="flex items-center justify-end gap-2">
                            {p.status !== "invited" && (
                            <button
                              onClick={() => handleRoleChange(p, !p.isAdmin)}
                              aria-label={partnerWorkspaceRole === "owner" ? `將 ${p.email} 改為一般成員` : `將 ${p.email} 改為擁有者`}
                              disabled={isLoading}
                              className="text-xs text-muted-foreground hover:text-white transition-all active:scale-95 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {partnerWorkspaceRole === "owner" ? "設為一般成員" : "設為擁有者"}
                            </button>
                          )}
                            {partnerWorkspaceRole !== "owner" && p.status !== "invited" && (
                              <button
                                onClick={() => openScopeEditor(p)}
                                aria-label={`編輯 ${p.email} 的權限範圍`}
                                disabled={isLoading}
                                className="text-xs text-blue-400 hover:text-blue-300 transition-all active:scale-95 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                編輯範圍
                              </button>
                            )}
                            {p.status === "active" && (
                              <button
                                onClick={() => handleStatusChange(p, "suspended")}
                                aria-label={`停用 ${p.email}`}
                                disabled={isLoading}
                                className="text-xs text-red-400 hover:text-red-300 transition-all active:scale-95 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                停用
                              </button>
                            )}
                            {p.status === "suspended" && (
                              <button
                                onClick={() => handleStatusChange(p, "active")}
                                aria-label={`重新啟用 ${p.email}`}
                                disabled={isLoading}
                                className="text-xs text-green-400 hover:text-green-300 transition-all active:scale-95 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                重新啟用
                              </button>
                            )}
                            {p.status === "invited" && (
                                <button
                                  onClick={() => handleResendInvite(p)}
                                  aria-label={`Resend invite to ${p.email}`}
                                  disabled={isLoading}
                                  className="text-xs text-muted-foreground hover:text-white transition-all active:scale-95 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                  重新寄送
                                </button>
                            )}
                            <button
                              onClick={() => handleDeleteInvite(p)}
                              aria-label={`Delete invite for ${p.email}`}
                              disabled={isLoading}
                              className="text-xs text-red-400 hover:text-red-300 transition-all active:scale-95 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              刪除
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </main>

      {scopeEditor && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-xl border border-border bg-card p-5 space-y-4">
            <div>
              <h3 className="text-base font-semibold text-white">編輯權限範圍</h3>
              <p className="text-xs text-muted-foreground mt-1">{scopeEditor.email}</p>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-muted-foreground uppercase tracking-wide">角色</label>
              <div className="grid grid-cols-2 gap-2">
                {DEFAULT_ROLE_OPTIONS.map((role) => {
                  const checked = scopeEditor.roles.includes(role);
                  return (
                    <label key={role} className="flex items-center gap-2 text-sm text-foreground">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(e) => {
                          setScopeEditor((prev) => {
                            if (!prev) return prev;
                            const next = new Set(prev.roles);
                            if (e.target.checked) next.add(role);
                            else next.delete(role);
                            return { ...prev, roles: Array.from(next).sort() };
                          });
                        }}
                      />
                      {role}
                    </label>
                  );
                })}
              </div>
              <div className="flex items-center gap-2">
                <input
                  value={scopeEditor.customRole}
                  onChange={(e) =>
                    setScopeEditor((prev) => (prev ? { ...prev, customRole: e.target.value } : prev))
                  }
                  placeholder="新增自訂角色"
                  className="flex-1 bg-background border border-border rounded px-3 py-1.5 text-sm text-white"
                />
                <button
                  className="text-xs px-3 py-1.5 rounded bg-secondary text-foreground"
                  onClick={() =>
                    setScopeEditor((prev) => {
                      if (!prev) return prev;
                      const v = prev.customRole.trim();
                      if (!v) return prev;
                      const next = new Set(prev.roles);
                      next.add(v);
                      return { ...prev, roles: Array.from(next).sort(), customRole: "" };
                    })
                  }
                >
                  新增
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-muted-foreground uppercase tracking-wide">部門</label>
              <select
                value={scopeEditor.department}
                onChange={(e) =>
                  setScopeEditor((prev) => (prev ? { ...prev, department: e.target.value } : prev))
                }
                className="w-full bg-background border border-border rounded px-3 py-2 text-sm text-white"
              >
                {departmentOptions.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
              <div className="flex items-center gap-2">
                <input
                  value={scopeEditor.customDepartment}
                  onChange={(e) =>
                    setScopeEditor((prev) => (prev ? { ...prev, customDepartment: e.target.value } : prev))
                  }
                  placeholder="自訂部門名稱（可選）"
                  className="flex-1 bg-background border border-border rounded px-3 py-1.5 text-sm text-white"
                />
                <button
                  className="text-xs px-3 py-1.5 rounded bg-secondary text-foreground"
                  onClick={() =>
                    setScopeEditor((prev) => {
                      if (!prev) return prev;
                      const v = prev.customDepartment.trim();
                      if (!v) return prev;
                      return { ...prev, department: v, customDepartment: "" };
                    })
                  }
                >
                  套用
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-muted-foreground uppercase tracking-wide">存取模式</label>
              <select
                value={scopeEditor.accessMode}
                onChange={(e) =>
                  setScopeEditor((prev) =>
                    prev
                      ? {
                          ...prev,
                          accessMode: e.target.value as "internal" | "scoped" | "unassigned",
                          authorizedEntityIds: e.target.value === "scoped" ? prev.authorizedEntityIds : [],
                        }
                      : prev
                  )
                }
                className="w-full bg-background border border-border rounded px-3 py-2 text-sm text-white"
                aria-label="成員存取模式"
              >
                {ACCESS_MODE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              {scopeEditor.accessMode === "scoped" && (
                <div className="border border-border rounded-lg p-3 space-y-2">
                  <p className="text-xs text-muted-foreground">選擇可存取的專案空間：</p>
                  {projectEntities.length === 0 ? (
                    <p className="text-xs text-muted-foreground">尚無專案空間</p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {projectEntities.map((entity) => (
                        <label
                          key={entity.id}
                          className="flex items-center gap-1.5 text-sm text-foreground cursor-pointer"
                        >
                          <input
                            type="checkbox"
                            checked={scopeEditor.authorizedEntityIds.includes(entity.id)}
                            onChange={(e) =>
                              setScopeEditor((prev) => {
                                if (!prev) return prev;
                                const next = e.target.checked
                                  ? [...prev.authorizedEntityIds, entity.id]
                                  : prev.authorizedEntityIds.filter((id) => id !== entity.id);
                                return { ...prev, authorizedEntityIds: next };
                              })
                            }
                          />
                          {entity.name}
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                className="text-sm px-3 py-2 rounded bg-secondary text-foreground transition-all active:scale-95"
                onClick={() => setScopeEditor(null)}
              >
                取消
              </button>
                <button
                  className="text-sm px-3 py-2 rounded bg-primary text-primary-foreground transition-all active:scale-95 disabled:opacity-50"
                  disabled={actionLoading === scopeEditor.partnerId}
                  onClick={() => {
                  const target = partners.find((p) => p.id === scopeEditor.partnerId);
                  if (!target) return;
                  const effectiveAccessMode =
                    scopeEditor.accessMode === "scoped" && scopeEditor.authorizedEntityIds.length > 0
                      ? "scoped"
                      : scopeEditor.accessMode === "internal"
                        ? "internal"
                        : "unassigned";
                  handleScopeSave(target, {
                    roles: scopeEditor.roles,
                    department: scopeEditor.department || "all",
                    accessMode: effectiveAccessMode,
                    authorizedEntityIds: effectiveAccessMode === "scoped"
                      ? scopeEditor.authorizedEntityIds
                      : [],
                  });
                  }}
              >
                {actionLoading === scopeEditor.partnerId ? "儲存中..." : "儲存範圍"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: Partner["status"] }) {
  const styles = {
    active: "bg-green-500/10 text-green-400 border-green-500/20",
    invited: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
    suspended: "bg-red-500/10 text-red-400 border-red-500/20",
  };

  const labels = {
    active: "啟用中",
    invited: "待啟用",
    suspended: "已停用",
  };

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${styles[status]}`}
    >
      {labels[status]}
    </span>
  );
}

export default function Page() {
  return (
    <AuthGuard>
      <TeamPage />
    </AuthGuard>
  );
}
