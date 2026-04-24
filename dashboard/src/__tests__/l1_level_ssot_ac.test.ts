/**
 * AC-L1SSOT-05: Dashboard surfaces use level-based L1 filtering (ADR-047 D7).
 *
 * Covers:
 * - isL1Entity helper (entity-level.ts)
 * - buildAvailableProjectOptions (tasks/page.tsx) — uses isL1Entity
 * - isPortfolioRootProduct (taskHub.ts) — delegates to isL1Entity
 * - TaskCreateDialog productOptions filter — uses isL1Entity
 * - isShareableRootEntity (api.ts) — uses isL1Entity
 */
import { describe, expect, it } from "vitest";
import { isL1Entity } from "@/lib/entity-level";
import { isShareableRootEntity } from "@/lib/api";
import { buildAvailableProjectOptions } from "@/app/(protected)/tasks/page";
import { buildTaskHubSnapshot } from "@/features/tasks/taskHub";
import type { Entity, Task } from "@/types";

// ─── Fixture helpers ──────────────────────────────────────────────────────────

function makeEntity(overrides: Partial<Entity> = {}): Entity {
  return {
    id: "e-default",
    name: "Default",
    type: "product",
    summary: "",
    tags: { what: [], why: "", how: "", who: [] },
    status: "active",
    level: 1,
    parentId: null,
    details: null,
    confirmedByUser: true,
    owner: null,
    sources: [],
    visibility: "public",
    lastReviewedAt: null,
    createdAt: new Date(),
    updatedAt: new Date(),
    ...overrides,
  };
}

// ─── isL1Entity ───────────────────────────────────────────────────────────────

describe("isL1Entity", () => {
  it("AC-L1SSOT-05: returns true for level=1 + no parentId regardless of type", () => {
    const types = ["product", "company", "person", "deal", "goal", "role"] as const;
    for (const type of types) {
      expect(isL1Entity(makeEntity({ type, level: 1, parentId: null })), `type=${type}`).toBe(true);
    }
  });

  it("returns false when level !== 1", () => {
    expect(isL1Entity(makeEntity({ level: 2, parentId: null }))).toBe(false);
    expect(isL1Entity(makeEntity({ level: 3, parentId: null }))).toBe(false);
  });

  it("returns false when level is null (strict mode — ADR-047 D1)", () => {
    expect(isL1Entity(makeEntity({ level: null, parentId: null }))).toBe(false);
  });

  it("returns false when level is undefined", () => {
    expect(isL1Entity(makeEntity({ level: undefined, parentId: null }))).toBe(false);
  });

  it("returns false when parentId is set", () => {
    expect(isL1Entity(makeEntity({ level: 1, parentId: "parent-id" }))).toBe(false);
  });

  it("returns false for null/undefined entity", () => {
    expect(isL1Entity(null)).toBe(false);
    expect(isL1Entity(undefined)).toBe(false);
  });
});

// ─── isShareableRootEntity ────────────────────────────────────────────────────

describe("isShareableRootEntity", () => {
  it("AC-L1SSOT-05: accepts company L1 entities (not type-gated)", () => {
    const company = makeEntity({ type: "company", level: 1, parentId: null, status: "active", visibility: "public" });
    expect(isShareableRootEntity(company)).toBe(true);
  });

  it("AC-L1SSOT-05: accepts person L1 entities (not type-gated)", () => {
    const person = makeEntity({ type: "person", level: 1, parentId: null, status: "active", visibility: "public" });
    expect(isShareableRootEntity(person)).toBe(true);
  });

  it("rejects entities with level=2 even if type=product", () => {
    const module = makeEntity({ type: "product", level: 2, parentId: "parent", status: "active", visibility: "public" });
    expect(isShareableRootEntity(module)).toBe(false);
  });

  it("rejects test root entities", () => {
    const test = makeEntity({ name: "Test dogfood", level: 1, parentId: null, status: "active", visibility: "public" });
    expect(isShareableRootEntity(test)).toBe(false);
  });

  it("rejects non-public entities", () => {
    const restricted = makeEntity({ level: 1, parentId: null, status: "active", visibility: "restricted" });
    expect(isShareableRootEntity(restricted)).toBe(false);
  });
});

// ─── buildAvailableProjectOptions ────────────────────────────────────────────

describe("buildAvailableProjectOptions (tasks/page.tsx)", () => {
  it("AC-L1SSOT-05: includes company L1 entities in project filter options", () => {
    const company = makeEntity({ id: "co-1", name: "原心生技", type: "company", level: 1, parentId: null });
    const product = makeEntity({ id: "p-1", name: "ZenOS", type: "product", level: 1, parentId: null });
    const module = makeEntity({ id: "m-1", name: "Auth Module", type: "module", level: 2, parentId: "p-1" });

    const options = buildAvailableProjectOptions([], [company, product, module]);
    const labels = options.map((o) => o.label);

    expect(labels).toContain("原心生技");
    expect(labels).toContain("ZenOS");
    expect(labels).not.toContain("Auth Module");
  });

  it("excludes person entity that is not L1 (has parentId)", () => {
    const personWithParent = makeEntity({ id: "pe-1", name: "Alice", type: "person", level: 1, parentId: "co-1" });
    const options = buildAvailableProjectOptions([], [personWithParent]);
    expect(options.map((o) => o.label)).not.toContain("Alice");
  });

  it("includes person entity that is L1 (no parentId)", () => {
    const personL1 = makeEntity({ id: "pe-2", name: "Bob CEO", type: "person", level: 1, parentId: null });
    const options = buildAvailableProjectOptions([], [personL1]);
    expect(options.map((o) => o.label)).toContain("Bob CEO");
  });
});

// ─── buildTaskHubSnapshot (isPortfolioRootProduct) ───────────────────────────

describe("buildTaskHubSnapshot — L1 product detection", () => {
  it("AC-L1SSOT-05: includes company L1 in task hub product recap", () => {
    const company = makeEntity({ id: "co-1", name: "原心生技", type: "company", level: 1, parentId: null });
    const snapshot = buildTaskHubSnapshot({ entities: [company], tasks: [], plans: [] });
    expect(snapshot.products.map((p) => p.productName)).toContain("原心生技");
  });

  it("excludes company entity with level=2", () => {
    const companyL2 = makeEntity({ id: "co-2", name: "Sub Co", type: "company", level: 2, parentId: "co-1" });
    const snapshot = buildTaskHubSnapshot({ entities: [companyL2], tasks: [], plans: [] });
    expect(snapshot.products).toHaveLength(0);
  });

  it("excludes entity with level=null (strict mode)", () => {
    const legacy = makeEntity({ id: "old-1", name: "Legacy Prod", type: "product", level: null, parentId: null });
    const snapshot = buildTaskHubSnapshot({ entities: [legacy], tasks: [], plans: [] });
    expect(snapshot.products).toHaveLength(0);
  });
});

// ─── plan?.project_id dead code removed ──────────────────────────────────────

describe("taskHub.ts — plan.project_id dead code removed (ADR-047 D3)", () => {
  it("resolves task to product via plan.product_id (not project_id)", () => {
    const company = makeEntity({ id: "co-1", name: "原心生技", type: "company", level: 1, parentId: null });
    const plan = { id: "plan-1", goal: "grow revenue", project: null, product_id: "co-1", status: "active" as const, owner: null };
    const task: Task = {
      id: "t-1",
      title: "Task under company plan",
      description: "",
      status: "in_progress",
      priority: "high",
      priorityReason: "",
      productId: null,
      project: "",
      createdBy: "test",
      linkedProtocol: null,
      linkedBlindspot: null,
      contextSummary: "",
      completedBy: null,
      planId: "plan-1",
      linkedEntities: [],
      blockedBy: [],
      blockedReason: null,
      dueDate: null,
      createdAt: new Date(),
      updatedAt: new Date(),
      completedAt: null,
      assignee: null,
      dispatcher: null,
      acceptanceCriteria: [],
      result: null,
      rejectionReason: null,
      confirmedByCreator: false,
      sourceType: "",
      parentTaskId: null,
      attachments: [],
    };

    const snapshot = buildTaskHubSnapshot({ entities: [company], tasks: [task], plans: [plan] });
    const recap = snapshot.products.find((p) => p.productId === "co-1");
    expect(recap).toBeDefined();
    expect(recap?.openTaskCount).toBe(1);
  });
});
