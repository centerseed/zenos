import { describe, it, expect } from "vitest";
import { toTask } from "@/lib/firestore";

function fakeTimestamp(date: Date) {
  return { toDate: () => date };
}

describe("toTask", () => {
  const validData = {
    title: "Fix login bug",
    description: "Users can't log in on iOS",
    status: "todo",
    priority: "high",
    priorityReason: "Blocking release",
    assignee: "developer",
    createdBy: "architect",
    linkedEntities: ["entity-1", "entity-2"],
    linkedProtocol: "proto-1",
    linkedBlindspot: "blind-1",
    contextSummary: "Auth flow broken after Firebase update",
    dueDate: fakeTimestamp(new Date("2026-04-01")),
    blockedBy: ["task-99"],
    blockedReason: null,
    acceptanceCriteria: ["Login works", "Tests pass"],
    confirmedByCreator: false,
    rejectionReason: null,
    result: null,
    completedBy: null,
    createdAt: fakeTimestamp(new Date("2026-03-01")),
    updatedAt: fakeTimestamp(new Date("2026-03-20")),
    completedAt: null,
  };

  it("converts valid Firestore data to Task", () => {
    const task = toTask("task-1", validData);

    expect(task.id).toBe("task-1");
    expect(task.title).toBe("Fix login bug");
    expect(task.description).toBe("Users can't log in on iOS");
    expect(task.status).toBe("todo");
    expect(task.priority).toBe("high");
    expect(task.assignee).toBe("developer");
    expect(task.linkedEntities).toEqual(["entity-1", "entity-2"]);
    expect(task.dueDate).toEqual(new Date("2026-04-01"));
    expect(task.blockedBy).toEqual(["task-99"]);
    expect(task.acceptanceCriteria).toEqual(["Login works", "Tests pass"]);
    expect(task.createdAt).toEqual(new Date("2026-03-01"));
    expect(task.completedAt).toBeNull();
  });

  it("defaults description to empty string when missing", () => {
    const data = { ...validData, description: undefined };
    const task = toTask("t-1", data);
    expect(task.description).toBe("");
  });

  it("defaults priority to 'medium' when missing", () => {
    const data = { ...validData, priority: undefined };
    const task = toTask("t-1", data);
    expect(task.priority).toBe("medium");
  });

  it("defaults assignee to null when missing", () => {
    const data = { ...validData, assignee: undefined };
    const task = toTask("t-1", data);
    expect(task.assignee).toBeNull();
  });

  it("defaults linkedEntities to empty array when missing", () => {
    const data = { ...validData, linkedEntities: undefined };
    const task = toTask("t-1", data);
    expect(task.linkedEntities).toEqual([]);
  });

  it("defaults blockedBy to empty array when missing", () => {
    const data = { ...validData, blockedBy: undefined };
    const task = toTask("t-1", data);
    expect(task.blockedBy).toEqual([]);
  });

  it("defaults acceptanceCriteria to empty array when missing", () => {
    const data = { ...validData, acceptanceCriteria: undefined };
    const task = toTask("t-1", data);
    expect(task.acceptanceCriteria).toEqual([]);
  });

  it("handles dueDate as null", () => {
    const data = { ...validData, dueDate: null };
    const task = toTask("t-1", data);
    expect(task.dueDate).toBeNull();
  });

  it("handles dueDate as undefined", () => {
    const data = { ...validData, dueDate: undefined };
    const task = toTask("t-1", data);
    expect(task.dueDate).toBeNull();
  });

  it("handles dueDate without toDate method (string)", () => {
    const data = { ...validData, dueDate: "2026-04-01" };
    const task = toTask("t-1", data);
    expect(task.dueDate).toBeNull();
  });

  it("handles completedAt as valid Timestamp", () => {
    const data = { ...validData, completedAt: fakeTimestamp(new Date("2026-03-22")) };
    const task = toTask("t-1", data);
    expect(task.completedAt).toEqual(new Date("2026-03-22"));
  });

  it("handles createdAt as null — falls back to new Date()", () => {
    const before = new Date();
    const data = { ...validData, createdAt: null };
    const task = toTask("t-1", data);
    expect(task.createdAt.getTime()).toBeGreaterThanOrEqual(before.getTime());
  });

  it("handles updatedAt as undefined — falls back to new Date()", () => {
    const before = new Date();
    const data = { ...validData, updatedAt: undefined };
    const task = toTask("t-1", data);
    expect(task.updatedAt.getTime()).toBeGreaterThanOrEqual(before.getTime());
  });

  it("handles completely empty data", () => {
    const task = toTask("t-1", {});
    expect(task.id).toBe("t-1");
    expect(task.description).toBe("");
    expect(task.priority).toBe("medium");
    expect(task.assignee).toBeNull();
    expect(task.linkedEntities).toEqual([]);
    expect(task.blockedBy).toEqual([]);
    expect(task.acceptanceCriteria).toEqual([]);
    expect(task.dueDate).toBeNull();
    expect(task.completedAt).toBeNull();
    expect(task.createdAt).toBeInstanceOf(Date);
    expect(task.updatedAt).toBeInstanceOf(Date);
  });

  it("defaults confirmedByCreator to false when missing", () => {
    const data = { ...validData, confirmedByCreator: undefined };
    const task = toTask("t-1", data);
    expect(task.confirmedByCreator).toBe(false);
  });
});
