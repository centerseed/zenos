import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock firebase before importing firestore
vi.mock("firebase/firestore", () => ({
  collection: vi.fn(),
  query: vi.fn(),
  where: vi.fn(),
  getDocs: vi.fn(),
  doc: vi.fn(),
  getDoc: vi.fn(),
}));
vi.mock("@/lib/firebase", () => ({
  getDbInstance: vi.fn(),
}));

import { toEntity } from "@/lib/firestore";

// Helper: fake Firestore Timestamp
function fakeTimestamp(date: Date) {
  return { toDate: () => date };
}

describe("toEntity", () => {
  const validData = {
    name: "Paceriz iOS App",
    type: "product",
    summary: "A running coach app",
    tags: { what: "app", why: "coaching", how: "AI", who: "runners" },
    status: "active",
    parentId: "parent-123",
    details: { version: "2.0" },
    confirmedByUser: true,
    createdAt: fakeTimestamp(new Date("2026-01-01")),
    updatedAt: fakeTimestamp(new Date("2026-03-01")),
  };

  it("converts valid Firestore data to Entity", () => {
    const entity = toEntity("entity-1", validData);

    expect(entity.id).toBe("entity-1");
    expect(entity.name).toBe("Paceriz iOS App");
    expect(entity.type).toBe("product");
    expect(entity.summary).toBe("A running coach app");
    expect(entity.tags).toEqual({ what: "app", why: "coaching", how: "AI", who: "runners" });
    expect(entity.status).toBe("active");
    expect(entity.parentId).toBe("parent-123");
    expect(entity.details).toEqual({ version: "2.0" });
    expect(entity.confirmedByUser).toBe(true);
    expect(entity.createdAt).toEqual(new Date("2026-01-01"));
    expect(entity.updatedAt).toEqual(new Date("2026-03-01"));
  });

  it("defaults status to 'active' when missing", () => {
    const data = { ...validData, status: undefined };
    const entity = toEntity("e-1", data);
    expect(entity.status).toBe("active");
  });

  it("defaults parentId to null when missing", () => {
    const data = { ...validData, parentId: undefined };
    const entity = toEntity("e-1", data);
    expect(entity.parentId).toBeNull();
  });

  it("defaults details to null when missing", () => {
    const data = { ...validData, details: undefined };
    const entity = toEntity("e-1", data);
    expect(entity.details).toBeNull();
  });

  it("defaults confirmedByUser to false when missing", () => {
    const data = { ...validData, confirmedByUser: undefined };
    const entity = toEntity("e-1", data);
    expect(entity.confirmedByUser).toBe(false);
  });

  it("falls back to new Date() when createdAt is null", () => {
    const before = new Date();
    const data = { ...validData, createdAt: null };
    const entity = toEntity("e-1", data);
    expect(entity.createdAt.getTime()).toBeGreaterThanOrEqual(before.getTime());
  });

  it("falls back to new Date() when updatedAt is null", () => {
    const before = new Date();
    const data = { ...validData, updatedAt: null };
    const entity = toEntity("e-1", data);
    expect(entity.updatedAt.getTime()).toBeGreaterThanOrEqual(before.getTime());
  });

  it("falls back to new Date() when createdAt is undefined", () => {
    const before = new Date();
    const data = { ...validData, createdAt: undefined };
    const entity = toEntity("e-1", data);
    expect(entity.createdAt.getTime()).toBeGreaterThanOrEqual(before.getTime());
  });

  it("falls back to new Date() when createdAt has no toDate method", () => {
    const before = new Date();
    const data = { ...validData, createdAt: "2026-01-01" };
    const entity = toEntity("e-1", data);
    // String doesn't have toDate(), so optional chaining returns undefined, fallback kicks in
    expect(entity.createdAt.getTime()).toBeGreaterThanOrEqual(before.getTime());
  });

  it("falls back to new Date() when createdAt is an empty object", () => {
    const before = new Date();
    const data = { ...validData, createdAt: {} };
    const entity = toEntity("e-1", data);
    expect(entity.createdAt.getTime()).toBeGreaterThanOrEqual(before.getTime());
  });

  it("handles completely empty data with minimal crash", () => {
    const entity = toEntity("e-1", {});
    expect(entity.id).toBe("e-1");
    expect(entity.status).toBe("active");
    expect(entity.parentId).toBeNull();
    expect(entity.details).toBeNull();
    expect(entity.confirmedByUser).toBe(false);
    expect(entity.createdAt).toBeInstanceOf(Date);
    expect(entity.updatedAt).toBeInstanceOf(Date);
  });

  it("handles numeric timestamp (not Firestore Timestamp)", () => {
    const before = new Date();
    const data = { ...validData, createdAt: 1700000000000 };
    const entity = toEntity("e-1", data);
    // Number doesn't have toDate(), falls back
    expect(entity.createdAt.getTime()).toBeGreaterThanOrEqual(before.getTime());
  });
});
