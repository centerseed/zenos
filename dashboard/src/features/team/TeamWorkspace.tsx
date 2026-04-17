"use client";

import { LoadingState } from "@/components/LoadingState";
import type { Partner } from "@/types";
import {
  getPartnerAccessMode,
  getPartnerWorkspaceRole,
  isScopedPartner,
} from "@/lib/partner";
import {
  DEFAULT_ROLE_OPTIONS,
  type WorkspaceAssignment,
  WORKSPACE_ROLE_OPTIONS,
  useTeamWorkspace,
} from "@/features/team/useTeamWorkspace";
function TeamPage() {
  const {
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
    setInviteDepartment,
    setInviteEmail,
    setInviteWorkspaceRole,
    setNewDepartment,
    setScopeEditor,
    setSelectedL1Ids,
  } = useTeamWorkspace();

  if (!canManageWorkspace) return null;

  const activeCount = partners.filter((p) => p.status === "active").length;
  const invitedCount = partners.filter((p) => p.status === "invited").length;

  return (
    <div className="min-h-screen">
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
              <label className="text-sm text-foreground">工作區角色</label>
              <select
                value={inviteWorkspaceRole}
                onChange={(e) => {
                  const next = e.target.value as WorkspaceAssignment;
                  setInviteWorkspaceRole(next);
                  if (next !== "guest") setSelectedL1Ids([]);
                }}
                aria-label="邀請工作區角色"
                className="bg-background border border-border rounded-lg px-4 py-2 text-sm text-white min-w-40"
              >
                {WORKSPACE_ROLE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            {inviteWorkspaceRole === "guest" && (
              <div className="border border-border rounded-lg p-3 space-y-2">
                <p className="text-xs text-muted-foreground">選擇訪客可存取的專案空間：</p>
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
              <label className="text-xs text-muted-foreground uppercase tracking-wide">工作區角色</label>
              <select
                value={scopeEditor.workspaceRole}
                onChange={(e) =>
                  setScopeEditor((prev) =>
                    prev
                      ? {
                          ...prev,
                          workspaceRole: e.target.value as WorkspaceAssignment,
                          authorizedEntityIds: e.target.value === "guest" ? prev.authorizedEntityIds : [],
                        }
                      : prev
                  )
                }
                className="w-full bg-background border border-border rounded px-3 py-2 text-sm text-white"
                aria-label="成員工作區角色"
              >
                {WORKSPACE_ROLE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              {scopeEditor.workspaceRole === "guest" && (
                <div className="border border-border rounded-lg p-3 space-y-2">
                  <p className="text-xs text-muted-foreground">選擇訪客可存取的專案空間：</p>
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
                  handleScopeSave(target, {
                    roles: scopeEditor.roles,
                    department: scopeEditor.department || "all",
                    workspaceRole: scopeEditor.workspaceRole,
                    authorizedEntityIds: scopeEditor.workspaceRole === "guest"
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
  return <TeamPage />;
}
