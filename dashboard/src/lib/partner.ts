import type { Partner, PartnerAccessMode, PartnerWorkspaceRole } from "@/types";

type PartnerRoleSource = Pick<
  Partner,
  "accessMode" | "authorizedEntityIds" | "isAdmin" | "workspaceRole"
> | null | undefined;

/** Resolved active workspace context. All nav, route guard, and query slicing
 *  must read from this object — never from raw partner.accessMode directly. */
export interface ActiveWorkspaceContext {
  /** True when the user is viewing their own home workspace (workspaceRole = owner). */
  isHomeWorkspace: boolean;
  /** Resolved workspace role for the current view context. */
  workspaceRole: PartnerWorkspaceRole;
  /** Entity IDs the partner is explicitly authorized to view (guest scope). Empty for owner/member. */
  authorizedEntityIds: string[];
}

function isPartnerWorkspaceRole(value: unknown): value is PartnerWorkspaceRole {
  return value === "owner" || value === "member" || value === "guest";
}

export function getPartnerWorkspaceRole(partner: PartnerRoleSource): PartnerWorkspaceRole {
  if (!partner) return "guest";
  if (isPartnerWorkspaceRole(partner.workspaceRole)) return partner.workspaceRole;
  if (partner.isAdmin) return "owner";
  if (partner.accessMode === "internal") return "member";
  if (partner.accessMode === "scoped" || partner.accessMode === "unassigned") return "guest";
  return (partner.authorizedEntityIds?.length ?? 0) > 0 ? "guest" : "member";
}

export function getPartnerAccessMode(partner: PartnerRoleSource): PartnerAccessMode {
  if (!partner) return "unassigned";
  const workspaceRole = getPartnerWorkspaceRole(partner);
  if (workspaceRole === "owner" || workspaceRole === "member") return "internal";
  return (partner.authorizedEntityIds?.length ?? 0) > 0 ? "scoped" : "unassigned";
}

export function isOwnerPartner(partner: PartnerRoleSource): boolean {
  return getPartnerWorkspaceRole(partner) === "owner";
}

export function isMemberPartner(partner: PartnerRoleSource): boolean {
  return getPartnerWorkspaceRole(partner) === "member";
}

export function isGuestPartner(partner: PartnerRoleSource): boolean {
  return getPartnerWorkspaceRole(partner) === "guest";
}

export function isScopedPartner(partner: PartnerRoleSource): boolean {
  return getPartnerWorkspaceRole(partner) === "guest" && (partner?.authorizedEntityIds?.length ?? 0) > 0;
}

export function isUnassignedPartner(partner: PartnerRoleSource): boolean {
  return getPartnerWorkspaceRole(partner) === "guest" && (partner?.authorizedEntityIds?.length ?? 0) === 0;
}

/**
 * Resolve the active workspace context from a Partner record.
 *
 * Business rules:
 * - isHomeWorkspace = true  → user is viewing their own workspace (workspaceRole = owner)
 * - isHomeWorkspace = false → user is viewing a shared workspace (guest or member of another)
 *
 * The `sharedPartnerId` field, when present on the Partner, indicates the user is
 * a guest operating inside another owner's workspace. If it is null, this is the
 * user's own home workspace.
 *
 * All nav, route guard, and page query logic must use this function rather than
 * reading partner.accessMode or partner.workspaceRole directly.
 */
export function resolveActiveWorkspace(
  partner: (PartnerRoleSource & { sharedPartnerId?: string | null }) | null | undefined
): ActiveWorkspaceContext {
  const workspaceRole = getPartnerWorkspaceRole(partner);
  // isHomeWorkspace is true when the partner has no sharedPartnerId (i.e. they
  // are operating within their own workspace, not a shared one).
  const isHomeWorkspace = !partner?.sharedPartnerId;
  const authorizedEntityIds = partner?.authorizedEntityIds ?? [];
  return {
    isHomeWorkspace,
    workspaceRole,
    authorizedEntityIds,
  };
}
