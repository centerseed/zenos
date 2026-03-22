import { describe, it, expect } from "vitest";
import { toPartner } from "@/lib/firestore";
import { fakeTimestamp } from "./testHelpers";

describe("toPartner", () => {
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
    const partner = toPartner("partner-1", validData);
    expect(partner.id).toBe("partner-1");
    expect(partner.email).toBe("barry@naruvia.com");
    expect(partner.displayName).toBe("Barry");
    expect(partner.authorizedEntityIds).toEqual(["entity-1", "entity-2"]);
    expect(partner.isAdmin).toBe(true);
    expect(partner.createdAt).toEqual(new Date("2026-01-01"));
  });

  it("defaults authorizedEntityIds to empty array when missing", () => {
    const data = { ...validData, authorizedEntityIds: undefined };
    const partner = toPartner("p-1", data);
    expect(partner.authorizedEntityIds).toEqual([]);
  });

  it("defaults authorizedEntityIds to empty array when null", () => {
    const data = { ...validData, authorizedEntityIds: null };
    const partner = toPartner("p-1", data);
    expect(partner.authorizedEntityIds).toEqual([]);
  });

  it("defaults isAdmin to false when missing", () => {
    const data = { ...validData, isAdmin: undefined };
    const partner = toPartner("p-1", data);
    expect(partner.isAdmin).toBe(false);
  });

  it("handles createdAt as null — falls back to new Date()", () => {
    const before = new Date();
    const data = { ...validData, createdAt: null };
    const partner = toPartner("p-1", data);
    expect(partner.createdAt.getTime()).toBeGreaterThanOrEqual(before.getTime());
  });

  it("handles updatedAt as undefined — falls back to new Date()", () => {
    const before = new Date();
    const data = { ...validData, updatedAt: undefined };
    const partner = toPartner("p-1", data);
    expect(partner.updatedAt.getTime()).toBeGreaterThanOrEqual(before.getTime());
  });

  it("handles createdAt without toDate (plain string) — falls back", () => {
    const before = new Date();
    const data = { ...validData, createdAt: "2026-01-01" };
    const partner = toPartner("p-1", data);
    expect(partner.createdAt.getTime()).toBeGreaterThanOrEqual(before.getTime());
  });

  it("preserves empty authorizedEntityIds array", () => {
    const data = { ...validData, authorizedEntityIds: [] };
    const partner = toPartner("p-1", data);
    expect(partner.authorizedEntityIds).toEqual([]);
  });
});
