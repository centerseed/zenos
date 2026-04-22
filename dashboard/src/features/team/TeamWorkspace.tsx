"use client";

import React, { useState } from "react";
import { useInk } from "@/lib/zen-ink/tokens";
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
import { Input } from "@/components/zen/Input";
import { Select } from "@/components/zen/Select";
import { Chip } from "@/components/zen/Chip";
import { Dialog } from "@/components/zen/Dialog";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function labelBtn(
  c: ReturnType<typeof useInk>["c"],
  fontBody: string,
  radius: number,
  opts: {
    children: React.ReactNode;
    onClick?: () => void;
    type?: "button" | "submit";
    disabled?: boolean;
    variant: "ink" | "ghost" | "danger" | "muted";
    size?: "sm" | "md";
    "aria-label"?: string;
  }
) {
  const { children, onClick, type = "button", disabled = false, variant, size = "md", "aria-label": ariaLabel } = opts;

  const bgMap: Record<string, string> = {
    ink: c.ink,
    ghost: c.paperWarm,
    danger: c.vermSoft,
    muted: "transparent",
  };
  const fgMap: Record<string, string> = {
    ink: c.paper,
    ghost: c.ink,
    danger: c.vermillion,
    muted: c.inkMuted,
  };
  const bdMap: Record<string, string> = {
    ink: "transparent",
    ghost: c.inkHair,
    danger: c.vermLine,
    muted: "transparent",
  };

  const padding = size === "sm" ? "4px 10px" : "7px 14px";
  const fontSize = size === "sm" ? 11 : 12;

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding,
        fontSize,
        fontFamily: fontBody,
        fontWeight: 500,
        letterSpacing: "0.02em",
        background: bgMap[variant],
        color: fgMap[variant],
        border: `1px solid ${bdMap[variant]}`,
        borderRadius: radius,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        transition: "all .15s",
      }}
    >
      {children}
    </button>
  );
}

// ─── StatusChip ───────────────────────────────────────────────────────────────

function StatusChip({ status, t }: { status: Partner["status"]; t: ReturnType<typeof useInk> }) {
  const toneMap: Record<Partner["status"], "jade" | "ocher" | "accent"> = {
    active: "jade",
    invited: "ocher",
    suspended: "accent",
  };
  const labelMap: Record<Partner["status"], string> = {
    active: "啟用中",
    invited: "待啟用",
    suspended: "已停用",
  };
  return (
    <Chip t={t} tone={toneMap[status]} dot>
      {labelMap[status]}
    </Chip>
  );
}

function l1EntityLabel(entity: { name: string; type: string }) {
  return `${entity.name} · ${entity.type === "company" ? "公司" : "產品"}`;
}

// ─── ScopeDialog ─────────────────────────────────────────────────────────────

interface ScopeDialogProps {
  t: ReturnType<typeof useInk>;
  open: boolean;
  onClose: () => void;
  scopeEditor: NonNullable<ReturnType<typeof useTeamWorkspace>["scopeEditor"]>;
  setScopeEditor: ReturnType<typeof useTeamWorkspace>["setScopeEditor"];
  departmentOptions: string[];
  projectEntities: ReturnType<typeof useTeamWorkspace>["projectEntities"];
  partners: Partner[];
  actionLoading: string | null;
  handleScopeSave: ReturnType<typeof useTeamWorkspace>["handleScopeSave"];
}

function ScopeDialog({
  t,
  open,
  onClose,
  scopeEditor,
  setScopeEditor,
  departmentOptions,
  projectEntities,
  partners,
  actionLoading,
  handleScopeSave,
}: ScopeDialogProps) {
  const { c, fontBody, fontMono, radius } = t;
  const isSaving = actionLoading === scopeEditor.partnerId;

  return (
    <Dialog
      t={t}
      open={open}
      onOpenChange={(v) => { if (!v) onClose(); }}
      title="編輯權限範圍"
      description={scopeEditor.email}
      size="md"
      footer={
        <>
          {labelBtn(c, fontBody, radius, {
            children: "取消",
            onClick: onClose,
            variant: "ghost",
          })}
          {labelBtn(c, fontBody, radius, {
            children: isSaving ? "儲存中..." : "儲存範圍",
            disabled: isSaving,
            onClick: () => {
              const target = partners.find((p) => p.id === scopeEditor.partnerId);
              if (!target) return;
              handleScopeSave(target, {
                roles: scopeEditor.roles,
                department: scopeEditor.department || "all",
                workspaceRole: scopeEditor.workspaceRole,
                authorizedEntityIds:
                  scopeEditor.workspaceRole === "guest"
                    ? scopeEditor.authorizedEntityIds
                    : [],
                homeWorkspaceBootstrapEntityIds:
                  scopeEditor.workspaceRole === "guest"
                    ? scopeEditor.homeWorkspaceBootstrapEntityIds
                    : [],
              });
            },
            variant: "ink",
          })}
        </>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {/* Roles */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.18em", textTransform: "uppercase" }}>
            角色
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            {DEFAULT_ROLE_OPTIONS.map((role) => {
              const checked = scopeEditor.roles.includes(role);
              return (
                <label
                  key={role}
                  style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, fontFamily: fontBody, color: c.ink, cursor: "pointer" }}
                >
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
          <div style={{ display: "flex", gap: 8 }}>
            <Input
              t={t}
              value={scopeEditor.customRole}
              onChange={(v) =>
                setScopeEditor((prev) => (prev ? { ...prev, customRole: v } : prev))
              }
              placeholder="新增自訂角色"
            />
            {labelBtn(c, fontBody, radius, {
              children: "新增",
              variant: "ghost",
              size: "sm",
              onClick: () =>
                setScopeEditor((prev) => {
                  if (!prev) return prev;
                  const v = prev.customRole.trim();
                  if (!v) return prev;
                  const next = new Set(prev.roles);
                  next.add(v);
                  return { ...prev, roles: Array.from(next).sort(), customRole: "" };
                }),
            })}
          </div>
        </div>

        {/* Department */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.18em", textTransform: "uppercase" }}>
            部門
          </div>
          <Select
            t={t}
            value={scopeEditor.department}
            onChange={(v) =>
              setScopeEditor((prev) => (prev ? { ...prev, department: v ?? "all" } : prev))
            }
            options={departmentOptions.map((d) => ({ value: d, label: d }))}
          />
          <div style={{ display: "flex", gap: 8 }}>
            <Input
              t={t}
              value={scopeEditor.customDepartment}
              onChange={(v) =>
                setScopeEditor((prev) =>
                  prev ? { ...prev, customDepartment: v } : prev
                )
              }
              placeholder="自訂部門名稱（可選）"
            />
            {labelBtn(c, fontBody, radius, {
              children: "套用",
              variant: "ghost",
              size: "sm",
              onClick: () =>
                setScopeEditor((prev) => {
                  if (!prev) return prev;
                  const v = prev.customDepartment.trim();
                  if (!v) return prev;
                  return { ...prev, department: v, customDepartment: "" };
                }),
            })}
          </div>
        </div>

        {/* Workspace role */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.18em", textTransform: "uppercase" }}>
            工作區角色
          </div>
          <Select
            t={t}
            value={scopeEditor.workspaceRole}
            onChange={(v) =>
              setScopeEditor((prev) =>
                prev
                  ? {
                      ...prev,
                      workspaceRole: (v ?? "member") as WorkspaceAssignment,
                      authorizedEntityIds:
                        v === "guest" ? prev.authorizedEntityIds : [],
                      homeWorkspaceBootstrapEntityIds:
                        v === "guest" ? prev.homeWorkspaceBootstrapEntityIds : [],
                    }
                  : prev
              )
            }
            options={WORKSPACE_ROLE_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
            aria-label="成員工作區角色"
          />
          {scopeEditor.workspaceRole === "guest" && (
            <div
              style={{
                border: `1px solid ${c.inkHair}`,
                borderRadius: radius,
                padding: 12,
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              <div style={{ fontSize: 12, color: c.inkMuted, fontFamily: fontBody }}>
                選擇訪客可存取的 L1 空間：
              </div>
              {projectEntities.length === 0 ? (
                <div style={{ fontSize: 12, color: c.inkMuted, fontFamily: fontBody }}>尚無可分享的 L1 空間</div>
              ) : (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {projectEntities.map((entity) => (
                    <label
                      key={entity.id}
                      style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, fontFamily: fontBody, color: c.ink, cursor: "pointer" }}
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
                            return {
                              ...prev,
                              authorizedEntityIds: next,
                              homeWorkspaceBootstrapEntityIds: prev.homeWorkspaceBootstrapEntityIds.filter((id) =>
                                next.includes(id)
                              ),
                            };
                          })
                        }
                      />
                      {l1EntityLabel(entity)}
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}
          {scopeEditor.workspaceRole === "guest" && scopeEditor.authorizedEntityIds.length > 0 && (
            <div
              style={{
                border: `1px solid ${c.inkHair}`,
                borderRadius: radius,
                padding: 12,
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              <div style={{ fontSize: 12, color: c.inkMuted, fontFamily: fontBody }}>
                選擇要在對方 home workspace 預設匯入的 L1 空間：
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {projectEntities
                  .filter((entity) => scopeEditor.authorizedEntityIds.includes(entity.id))
                  .map((entity) => (
                    <label
                      key={`bootstrap-${entity.id}`}
                      style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, fontFamily: fontBody, color: c.ink, cursor: "pointer" }}
                    >
                      <input
                        type="checkbox"
                        checked={scopeEditor.homeWorkspaceBootstrapEntityIds.includes(entity.id)}
                        onChange={(e) =>
                          setScopeEditor((prev) => {
                            if (!prev) return prev;
                            const next = e.target.checked
                              ? [...prev.homeWorkspaceBootstrapEntityIds, entity.id]
                              : prev.homeWorkspaceBootstrapEntityIds.filter((id) => id !== entity.id);
                            return { ...prev, homeWorkspaceBootstrapEntityIds: next };
                          })
                        }
                      />
                      {l1EntityLabel(entity)}
                    </label>
                  ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </Dialog>
  );
}

// ─── TeamPage ─────────────────────────────────────────────────────────────────

function TeamPage() {
  const t = useInk("light");
  const { c, fontBody, fontHead, fontMono, radius } = t;

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
    selectedBootstrapL1Ids,
    setInviteDepartment,
    setInviteEmail,
    setInviteWorkspaceRole,
    setNewDepartment,
    setScopeEditor,
    setSelectedL1Ids,
    setSelectedBootstrapL1Ids,
  } = useTeamWorkspace();

  if (!canManageWorkspace) return null;

  const activeCount = partners.filter((p) => p.status === "active").length;
  const invitedCount = partners.filter((p) => p.status === "invited").length;

  // Table header style
  const thStyle: React.CSSProperties = {
    textAlign: "left",
    fontFamily: fontMono,
    fontSize: 10,
    fontWeight: 400,
    color: c.inkFaint,
    letterSpacing: "0.18em",
    textTransform: "uppercase",
    padding: "10px 20px",
    borderBottom: `1px solid ${c.inkHair}`,
  };

  const panelStyle: React.CSSProperties = {
    background: c.surface,
    border: `1px solid ${c.inkHair}`,
    borderRadius: radius,
    padding: 24,
    marginBottom: 16,
  };

  return (
    <div style={{ minHeight: "100vh", background: c.paper }}>
      <main
        id="main-content"
        style={{ maxWidth: 1120, margin: "0 auto", padding: "32px 24px" }}
      >
        {/* Page header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
          <div>
            <h2 style={{ fontFamily: fontHead, fontSize: 24, fontWeight: 500, color: c.ink, margin: 0, letterSpacing: "0.02em" }}>
              成員管理
            </h2>
            <p style={{ fontFamily: fontBody, fontSize: 13, color: c.inkMuted, marginTop: 4, marginBottom: 0 }}>
              共 {partners.length} 位成員 &middot; {activeCount} 位啟用中
              {invitedCount > 0 && ` · ${invitedCount} 位待啟用`}
            </p>
          </div>
        </div>

        {/* Invite Form */}
        <div style={panelStyle}>
          <h3 style={{ fontFamily: fontBody, fontSize: 13, fontWeight: 500, color: c.ink, marginTop: 0, marginBottom: 16 }}>
            邀請新成員
          </h3>
          <form onSubmit={handleInvite} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <div style={{ flex: 1, minWidth: 200 }}>
                  <Input
                    t={t}
                    type="email"
                    value={inviteEmail}
                    onChange={setInviteEmail}
                    placeholder="email@example.com"
                    aria-label="邀請成員信箱"
                  />
                </div>
                <div style={{ minWidth: 160 }}>
                  <Select
                    t={t}
                    value={inviteDepartment}
                    onChange={(v) => setInviteDepartment(v ?? "")}
                    options={departmentOptions.map((d) => ({ value: d, label: d }))}
                    aria-label="邀請預設部門"
                  />
                </div>
                {labelBtn(c, fontBody, radius, {
                  children: inviting ? "送出中..." : "送出邀請",
                  type: "submit",
                  disabled: inviting || !inviteEmail.trim(),
                  variant: "ink",
                  "aria-label": "送出邀請",
                })}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <span style={{ fontFamily: fontBody, fontSize: 13, color: c.ink }}>工作區角色</span>
                <div style={{ minWidth: 160 }}>
                  <Select
                    t={t}
                    value={inviteWorkspaceRole}
                    onChange={(v) => {
                      const next = (v ?? "member") as WorkspaceAssignment;
                      setInviteWorkspaceRole(next);
                      if (next !== "guest") {
                        setSelectedL1Ids([]);
                        setSelectedBootstrapL1Ids([]);
                      }
                    }}
                    options={WORKSPACE_ROLE_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
                    aria-label="邀請工作區角色"
                  />
                </div>
              </div>
            </div>

            {inviteWorkspaceRole === "guest" && (
              <div
                style={{
                  border: `1px solid ${c.inkHair}`,
                  borderRadius: radius,
                  padding: 12,
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                }}
              >
                <p style={{ fontSize: 12, color: c.inkMuted, fontFamily: fontBody, margin: 0 }}>
                  選擇訪客可存取的 L1 空間：
                </p>
                {projectEntities.length === 0 ? (
                  <p style={{ fontSize: 12, color: c.inkMuted, fontFamily: fontBody, margin: 0 }}>尚無可分享的 L1 空間</p>
                ) : (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                    {projectEntities.map((entity) => (
                      <label
                        key={entity.id}
                        style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, fontFamily: fontBody, color: c.ink, cursor: "pointer" }}
                      >
                        <input
                          type="checkbox"
                          checked={selectedL1Ids.includes(entity.id)}
                          onChange={(e) => {
                            setSelectedL1Ids((prev) => {
                              const next = e.target.checked
                                ? [...prev, entity.id]
                                : prev.filter((id) => id !== entity.id);
                              setSelectedBootstrapL1Ids((bootstrapPrev) =>
                                bootstrapPrev.filter((id) => next.includes(id))
                              );
                              return next;
                            });
                          }}
                        />
                        {l1EntityLabel(entity)}
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )}
            {inviteWorkspaceRole === "guest" && selectedL1Ids.length > 0 && (
              <div
                style={{
                  border: `1px solid ${c.inkHair}`,
                  borderRadius: radius,
                  padding: 12,
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                }}
              >
                <p style={{ fontSize: 12, color: c.inkMuted, fontFamily: fontBody, margin: 0 }}>
                  選擇要預設匯入到對方 home workspace 的 L1 空間：
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {projectEntities
                    .filter((entity) => selectedL1Ids.includes(entity.id))
                    .map((entity) => (
                      <label
                        key={`invite-bootstrap-${entity.id}`}
                        style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, fontFamily: fontBody, color: c.ink, cursor: "pointer" }}
                      >
                        <input
                          type="checkbox"
                          checked={selectedBootstrapL1Ids.includes(entity.id)}
                          onChange={(e) =>
                            setSelectedBootstrapL1Ids((prev) =>
                              e.target.checked
                                ? [...prev, entity.id]
                                : prev.filter((id) => id !== entity.id)
                            )
                          }
                        />
                        {l1EntityLabel(entity)}
                      </label>
                    ))}
                </div>
              </div>
            )}
          </form>

          {inviteMessage && (
            <p
              style={{
                fontFamily: fontBody,
                fontSize: 13,
                marginTop: 12,
                marginBottom: 0,
                color: inviteMessage.type === "success" ? c.jade : c.vermillion,
              }}
            >
              {inviteMessage.text}
            </p>
          )}
        </div>

        {/* Department Management */}
        <div style={{ ...panelStyle, display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
            <div>
              <h3 style={{ fontFamily: fontBody, fontSize: 13, fontWeight: 500, color: c.ink, marginTop: 0, marginBottom: 4 }}>
                部門清單
              </h3>
              <p style={{ fontFamily: fontBody, fontSize: 12, color: c.inkMuted, margin: 0 }}>
                可新增、改名、刪除；刪除時既有成員會移回 all。
              </p>
            </div>
            <div style={{ display: "flex", gap: 8, flex: 1, maxWidth: 400 }}>
              <div style={{ flex: 1 }}>
                <Input
                  t={t}
                  value={newDepartment}
                  onChange={setNewDepartment}
                  placeholder="新增部門名稱"
                />
              </div>
              {labelBtn(c, fontBody, radius, {
                children: "新增",
                onClick: handleCreateDepartment,
                variant: "ghost",
              })}
            </div>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {departmentOptions.map((department) => (
              <div
                key={department}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  border: `1px solid ${c.inkHair}`,
                  borderRadius: 2,
                  background: c.surfaceHi,
                  padding: "4px 10px",
                  fontSize: 12,
                  fontFamily: fontBody,
                  color: c.ink,
                }}
              >
                <span>{department}</span>
                {department !== "all" && (
                  <>
                    <button
                      type="button"
                      onClick={() => handleRenameDepartment(department)}
                      style={{
                        background: "none",
                        border: "none",
                        padding: 0,
                        fontSize: 11,
                        fontFamily: fontBody,
                        color: c.inkMuted,
                        cursor: "pointer",
                        transition: "color .15s",
                      }}
                    >
                      改名
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeleteDepartment(department)}
                      style={{
                        background: "none",
                        border: "none",
                        padding: 0,
                        fontSize: 11,
                        fontFamily: fontBody,
                        color: c.vermillion,
                        cursor: "pointer",
                        transition: "color .15s",
                      }}
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
          <div
            style={{
              textAlign: "center",
              padding: "48px 0",
              background: c.surface,
              borderRadius: radius,
              border: `1px solid ${c.inkHair}`,
            }}
          >
            <p style={{ fontFamily: fontBody, fontSize: 13, color: c.inkMuted, margin: 0 }}>
              目前還沒有任何成員。
            </p>
          </div>
        ) : (
          <div
            style={{
              background: c.surface,
              border: `1px solid ${c.inkHair}`,
              borderRadius: radius,
              overflow: "hidden",
            }}
          >
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th style={thStyle}>信箱</th>
                  <th style={thStyle}>名稱</th>
                  <th style={thStyle}>權限範圍</th>
                  <th style={thStyle}>狀態</th>
                  <th style={{ ...thStyle, textAlign: "right" }}>操作</th>
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

                  const accessChipTone =
                    accessMode === "scoped"
                      ? "ocher"
                      : accessMode === "internal"
                        ? "muted"
                        : "muted";

                  const tdStyle: React.CSSProperties = {
                    padding: "14px 20px",
                    borderBottom: `1px solid ${c.inkHair}`,
                    fontFamily: fontBody,
                    fontSize: 13,
                    color: c.ink,
                    opacity: p.status === "invited" ? 0.6 : 1,
                  };

                  return (
                    <tr key={p.id}>
                      <td style={tdStyle}>{p.email}</td>
                      <td style={{ ...tdStyle, color: c.inkMuted }}>
                        {p.displayName || "--"}
                      </td>
                      <td style={tdStyle}>
                        <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 220 }}>
                          <Chip
                            t={t}
                            tone={partnerWorkspaceRole === "owner" ? "accent" : "muted"}
                          >
                            {roleLabel}
                          </Chip>
                          {partnerWorkspaceRole !== "owner" && (
                            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 4 }}>
                                <Chip t={t} tone={accessChipTone}>
                                  {accessModeLabel}
                                </Chip>
                                {isScopedPartner(p) && (
                                  <span style={{ fontSize: 11, color: c.inkMuted, fontFamily: fontBody }}>
                                    授權 {p.authorizedEntityIds!.length} 個 L1 空間
                                  </span>
                                )}
                              </div>
                              <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                                {(p.roles || []).length === 0 ? (
                                  <span style={{ fontSize: 11, color: c.inkMuted, fontFamily: fontBody }}>角色：（未設定）</span>
                                ) : (
                                  (p.roles || []).map((r) => (
                                    <Chip key={`${p.id}-${r}`} t={t} tone="muted">
                                      {r}
                                    </Chip>
                                  ))
                                )}
                              </div>
                              <div style={{ fontSize: 11, color: c.inkMuted, fontFamily: fontBody }}>
                                部門：<span style={{ color: c.ink }}>{p.department || "all"}</span>
                              </div>
                            </div>
                          )}
                        </div>
                      </td>
                      <td style={tdStyle}>
                        <StatusChip status={p.status} t={t} />
                      </td>
                      <td style={{ ...tdStyle, textAlign: "right" }}>
                        {isSelf ? (
                          <span style={{ fontSize: 12, color: c.inkMuted, fontFamily: fontBody }}>你自己</span>
                        ) : (
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 8 }}>
                            {partnerWorkspaceRole !== "owner" && p.status !== "invited" && (
                              <button
                                type="button"
                                onClick={() => openScopeEditor(p)}
                                aria-label={`編輯 ${p.email} 的權限範圍`}
                                disabled={isLoading}
                                style={{
                                  background: "none",
                                  border: "none",
                                  padding: 0,
                                  fontSize: 12,
                                  fontFamily: fontBody,
                                  color: c.inkMuted,
                                  cursor: isLoading ? "not-allowed" : "pointer",
                                  opacity: isLoading ? 0.5 : 1,
                                  transition: "color .15s",
                                }}
                              >
                                編輯範圍
                              </button>
                            )}
                            {p.status === "active" && (
                              <button
                                type="button"
                                onClick={() => handleStatusChange(p, "suspended")}
                                aria-label={`停用 ${p.email}`}
                                disabled={isLoading}
                                style={{
                                  background: "none",
                                  border: "none",
                                  padding: 0,
                                  fontSize: 12,
                                  fontFamily: fontBody,
                                  color: c.vermillion,
                                  cursor: isLoading ? "not-allowed" : "pointer",
                                  opacity: isLoading ? 0.5 : 1,
                                  transition: "color .15s",
                                }}
                              >
                                停用
                              </button>
                            )}
                            {p.status === "suspended" && (
                              <button
                                type="button"
                                onClick={() => handleStatusChange(p, "active")}
                                aria-label={`重新啟用 ${p.email}`}
                                disabled={isLoading}
                                style={{
                                  background: "none",
                                  border: "none",
                                  padding: 0,
                                  fontSize: 12,
                                  fontFamily: fontBody,
                                  color: c.jade,
                                  cursor: isLoading ? "not-allowed" : "pointer",
                                  opacity: isLoading ? 0.5 : 1,
                                  transition: "color .15s",
                                }}
                              >
                                重新啟用
                              </button>
                            )}
                            {p.status === "invited" && (
                              <button
                                type="button"
                                onClick={() => handleResendInvite(p)}
                                aria-label={`Resend invite to ${p.email}`}
                                disabled={isLoading}
                                style={{
                                  background: "none",
                                  border: "none",
                                  padding: 0,
                                  fontSize: 12,
                                  fontFamily: fontBody,
                                  color: c.inkMuted,
                                  cursor: isLoading ? "not-allowed" : "pointer",
                                  opacity: isLoading ? 0.5 : 1,
                                  transition: "color .15s",
                                }}
                              >
                                重新寄送
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={() => handleDeleteInvite(p)}
                              aria-label={`Delete invite for ${p.email}`}
                              disabled={isLoading}
                              style={{
                                background: "none",
                                border: "none",
                                padding: 0,
                                fontSize: 12,
                                fontFamily: fontBody,
                                color: c.vermillion,
                                cursor: isLoading ? "not-allowed" : "pointer",
                                opacity: isLoading ? 0.5 : 1,
                                transition: "color .15s",
                              }}
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

      {/* Scope editor dialog */}
      {scopeEditor && (
        <ScopeDialog
          t={t}
          open={!!scopeEditor}
          onClose={() => setScopeEditor(null)}
          scopeEditor={scopeEditor}
          setScopeEditor={setScopeEditor}
          departmentOptions={departmentOptions}
          projectEntities={projectEntities}
          partners={partners}
          actionLoading={actionLoading}
          handleScopeSave={handleScopeSave}
        />
      )}
    </div>
  );
}

export default function Page() {
  return <TeamPage />;
}
