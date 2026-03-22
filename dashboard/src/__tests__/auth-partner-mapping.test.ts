import { describe, it, expect } from "vitest";
import type { Partner } from "@/types";

/**
 * Tests for the partner data mapping logic extracted from auth.tsx.
 *
 * The actual AuthProvider uses Firebase onAuthStateChanged + Firestore query,
 * which requires a full Firebase mock. Instead, we test the data mapping logic
 * that converts raw Firestore data to a Partner object — this is where the
 * authorizedEntityIds and date conversion bugs lived.
 */

function fakeTimestamp(date: Date) {
  return { toDate: () => date };
}

/** Replicates the partner mapping logic from auth.tsx lines 76-86 */
function mapPartnerData(docId: string, data: Record<string, unknown>): Partner {
  return {
    id: docId,
    email: data.email as string,
    displayName: data.displayName as string,
    apiKey: data.apiKey as string,
    authorizedEntityIds: (data.authorizedEntityIds as string[]) ?? [],
    isAdmin: (data.isAdmin as boolean) ?? false,
    status: data.status as Partner["status"],
    createdAt: (data.createdAt as { toDate: () => Date })?.toDate() ?? new Date(),
    updatedAt: (data.updatedAt as { toDate: () => Date })?.toDate() ?? new Date(),
  };
}

describe("Partner data mapping (from auth.tsx)", () => {
  const validData = {
    email: "barry@naruvia.com",
    displayName: "Barry",
    apiKey: "key-123",
    authorizedEntityIds: ["entity-1", "entity-2"],
    isAdmin: true,
    status: "active",
    createdAt: fakeTimestamp(new Date("2026-01-01")),
    updatedAt: fakeTimestamp(new Date("2026-03-01")),
  };

  it("maps valid data correctly", () => {
    const partner = mapPartnerData("partner-1", validData);
    expect(partner.id).toBe("partner-1");
    expect(partner.email).toBe("barry@naruvia.com");
    expect(partner.displayName).toBe("Barry");
    expect(partner.authorizedEntityIds).toEqual(["entity-1", "entity-2"]);
    expect(partner.isAdmin).toBe(true);
    expect(partner.createdAt).toEqual(new Date("2026-01-01"));
  });

  it("defaults authorizedEntityIds to empty array when missing", () => {
    const data = { ...validData, authorizedEntityIds: undefined };
    const partner = mapPartnerData("p-1", data);
    expect(partner.authorizedEntityIds).toEqual([]);
  });

  it("defaults authorizedEntityIds to empty array when null", () => {
    const data = { ...validData, authorizedEntityIds: null };
    const partner = mapPartnerData("p-1", data);
    expect(partner.authorizedEntityIds).toEqual([]);
  });

  it("defaults isAdmin to false when missing", () => {
    const data = { ...validData, isAdmin: undefined };
    const partner = mapPartnerData("p-1", data);
    expect(partner.isAdmin).toBe(false);
  });

  it("handles createdAt as null — falls back to new Date()", () => {
    const before = new Date();
    const data = { ...validData, createdAt: null };
    const partner = mapPartnerData("p-1", data);
    expect(partner.createdAt.getTime()).toBeGreaterThanOrEqual(before.getTime());
  });

  it("handles updatedAt as undefined — falls back to new Date()", () => {
    const before = new Date();
    const data = { ...validData, updatedAt: undefined };
    const partner = mapPartnerData("p-1", data);
    expect(partner.updatedAt.getTime()).toBeGreaterThanOrEqual(before.getTime());
  });

  it("handles createdAt without toDate (plain string)", () => {
    const data = { ...validData, createdAt: "2026-01-01" };
    // String has no toDate(), so ?.toDate() throws — this tests current behavior
    expect(() => mapPartnerData("p-1", data)).toThrow();
  });

  it("preserves empty authorizedEntityIds array", () => {
    const data = { ...validData, authorizedEntityIds: [] };
    const partner = mapPartnerData("p-1", data);
    expect(partner.authorizedEntityIds).toEqual([]);
  });
});
