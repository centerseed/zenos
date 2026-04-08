/**
 * Unit tests for resolveActiveWorkspace().
 *
 * Covers:
 * - Single workspace owner → isHomeWorkspace=true, workspaceRole=owner
 * - Member in their own workspace → isHomeWorkspace=true, workspaceRole=member
 * - Guest viewing a shared workspace → isHomeWorkspace=false, workspaceRole=guest
 * - Null/undefined partner → safe fallback
 * - authorizedEntityIds passthrough
 */

import { describe, it, expect } from "vitest";
import { resolveActiveWorkspace } from "@/lib/partner";
import type { Partner } from "@/types";

function makePartner(overrides: Partial<Partner> = {}): Partner {
  return {
    id: "p1",
    email: "owner@example.com",
    displayName: "Owner",
    apiKey: "key-test", // pragma: allowlist secret
    authorizedEntityIds: [],
    isAdmin: false,
    status: "active",
    workspaceRole: null,
    accessMode: null,
    sharedPartnerId: null,
    invitedBy: null,
    createdAt: new Date("2026-01-01"),
    updatedAt: new Date("2026-01-02"),
    ...overrides,
  };
}

describe("resolveActiveWorkspace", () => {
  describe("single workspace — owner (isHomeWorkspace = true)", () => {
    it("returns isHomeWorkspace=true and workspaceRole=owner when user is admin with no sharedPartnerId", () => {
      const partner = makePartner({ isAdmin: true, sharedPartnerId: null });
      const ctx = resolveActiveWorkspace(partner);
      expect(ctx.isHomeWorkspace).toBe(true);
      expect(ctx.workspaceRole).toBe("owner");
      expect(ctx.authorizedEntityIds).toEqual([]);
    });

    it("returns isHomeWorkspace=true when workspaceRole=owner and no sharedPartnerId", () => {
      const partner = makePartner({
        workspaceRole: "owner",
        accessMode: "internal",
        sharedPartnerId: null,
      });
      const ctx = resolveActiveWorkspace(partner);
      expect(ctx.isHomeWorkspace).toBe(true);
      expect(ctx.workspaceRole).toBe("owner");
    });

    it("returns isHomeWorkspace=true for a member in their own workspace", () => {
      const partner = makePartner({
        workspaceRole: "member",
        accessMode: "internal",
        sharedPartnerId: null,
      });
      const ctx = resolveActiveWorkspace(partner);
      expect(ctx.isHomeWorkspace).toBe(true);
      expect(ctx.workspaceRole).toBe("member");
    });
  });

  describe("multi-workspace — guest view (isHomeWorkspace = false)", () => {
    it("returns isHomeWorkspace=false when sharedPartnerId is set (guest in shared workspace)", () => {
      const partner = makePartner({
        workspaceRole: "guest",
        accessMode: "scoped",
        sharedPartnerId: "owner-partner-id",
        authorizedEntityIds: ["l1-entity-1", "l1-entity-2"],
      });
      const ctx = resolveActiveWorkspace(partner);
      expect(ctx.isHomeWorkspace).toBe(false);
      expect(ctx.workspaceRole).toBe("guest");
      expect(ctx.authorizedEntityIds).toEqual(["l1-entity-1", "l1-entity-2"]);
    });

    it("returns isHomeWorkspace=false for member with sharedPartnerId (member of another workspace)", () => {
      const partner = makePartner({
        workspaceRole: "member",
        accessMode: "internal",
        sharedPartnerId: "another-owner-id",
      });
      const ctx = resolveActiveWorkspace(partner);
      expect(ctx.isHomeWorkspace).toBe(false);
      expect(ctx.workspaceRole).toBe("member");
    });
  });

  describe("authorizedEntityIds passthrough", () => {
    it("returns empty authorizedEntityIds for owner", () => {
      const partner = makePartner({ isAdmin: true });
      const ctx = resolveActiveWorkspace(partner);
      expect(ctx.authorizedEntityIds).toEqual([]);
    });

    it("returns authorized entity IDs for guest", () => {
      const partner = makePartner({
        workspaceRole: "guest",
        accessMode: "scoped",
        sharedPartnerId: "owner-id",
        authorizedEntityIds: ["ent-a", "ent-b", "ent-c"],
      });
      const ctx = resolveActiveWorkspace(partner);
      expect(ctx.authorizedEntityIds).toEqual(["ent-a", "ent-b", "ent-c"]);
    });
  });

  describe("null / undefined partner — safe fallback", () => {
    it("returns guest + isHomeWorkspace=true for null partner", () => {
      const ctx = resolveActiveWorkspace(null);
      expect(ctx.workspaceRole).toBe("guest");
      // null partner has no sharedPartnerId, so treated as home
      expect(ctx.isHomeWorkspace).toBe(true);
      expect(ctx.authorizedEntityIds).toEqual([]);
    });

    it("returns guest + isHomeWorkspace=true for undefined partner", () => {
      const ctx = resolveActiveWorkspace(undefined);
      expect(ctx.workspaceRole).toBe("guest");
      expect(ctx.isHomeWorkspace).toBe(true);
    });
  });
});
