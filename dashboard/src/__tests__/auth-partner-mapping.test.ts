import { describe, it, expect } from "vitest";
import {
  getPartnerAccessMode,
  getPartnerWorkspaceRole,
  isGuestPartner,
  isOwnerPartner,
} from "@/lib/partner";

describe("partner role mapping", () => {
  it("prefers workspaceRole when present", () => {
    const partner = {
      workspaceRole: "guest" as const,
      accessMode: "internal" as const,
      authorizedEntityIds: ["entity-1"],
      isAdmin: true,
    };

    expect(getPartnerWorkspaceRole(partner)).toBe("guest");
    expect(getPartnerAccessMode(partner)).toBe("scoped");
    expect(isGuestPartner(partner)).toBe(true);
    expect(isOwnerPartner(partner)).toBe(false);
  });

  it("derives owner/member/guest from legacy fields when workspaceRole is missing", () => {
    expect(
      getPartnerWorkspaceRole({
        accessMode: "internal",
        authorizedEntityIds: [],
        isAdmin: true,
      })
    ).toBe("owner");

    expect(
      getPartnerWorkspaceRole({
        accessMode: "internal",
        authorizedEntityIds: [],
        isAdmin: false,
      })
    ).toBe("member");

    expect(
      getPartnerWorkspaceRole({
        accessMode: "scoped",
        authorizedEntityIds: ["entity-1"],
        isAdmin: false,
      })
    ).toBe("guest");
  });

  it("treats guests without shared entities as unassigned access", () => {
    const partner = {
      accessMode: "unassigned" as const,
      authorizedEntityIds: [],
      isAdmin: false,
    };

    expect(getPartnerWorkspaceRole(partner)).toBe("guest");
    expect(getPartnerAccessMode(partner)).toBe("unassigned");
    expect(isGuestPartner(partner)).toBe(true);
  });
});
