import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

describe("Task Ownership SSOT — Frontend AC", () => {
  it("AC-TOSC-18: 全域 /tasks 的 product filter 改用 product_id, 顯示 product entity name", () => {
    const pageFile = path.join(process.cwd(), "src/app/(protected)/tasks/page.tsx");
    const source = fs.readFileSync(pageFile, "utf8");

    expect(source).toContain("task.productId");
    expect(source).toContain("entitiesById[task.productId]?.name");
    expect(source).not.toContain("normalizeProjectKey(task.project)");
  });

  it("AC-TOSC-19: 從 /projects/[id] 建 task 時傳遞 product_id=entity.id, 不再偷塞 linked_entities", async () => {
    const testFile = path.join(process.cwd(), "src/app/(protected)/projects/page.test.tsx");
    const source = fs.readFileSync(testFile, "utf8");

    expect(source).toContain('product_id: "entity-1"');
    expect(source).toContain("not.toHaveProperty(\"linked_entities\")");
  });

  it("AC-TOSC-20: createTask client 型別 product_id: string 為必填欄位 (TypeScript 強制)", () => {
    const apiFile = path.join(process.cwd(), "src/lib/api.ts");
    const source = fs.readFileSync(apiFile, "utf8");

    expect(source).toMatch(/export async function createTask[\s\S]*data:\s*\{[\s\S]*product_id:\s*string/);
  });
});
