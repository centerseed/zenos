/**
 * L1 entity判定 SSOT（ADR-047 D7）
 *
 * L1 的唯一判定條件：level === 1 AND no parentId。
 * type 是 UI 顯示 label，不參與判定。
 */
import type { Entity } from "@/types";

/**
 * Returns true if entity qualifies as an L1 (collaboration root) entity.
 *
 * Criteria (ADR-047 D1):
 * - entity.level === 1
 * - entity.parentId is null / undefined / empty
 *
 * type is intentionally ignored — any type (product, company, person, deal, etc.)
 * can be L1. Use type only for icon / label display purposes.
 */
export function isL1Entity(entity: Entity | null | undefined): boolean {
  if (!entity) return false;
  const parentId = entity.parentId ?? null;
  return entity.level === 1 && !parentId;
}

/**
 * Returns true for L1 entities that should appear as portfolio/workspace cards.
 *
 * CRM deals and people can be L1 collaboration scopes for task ownership and
 * graph traversal, but they are CRM records and should stay in the CRM pipeline
 * surfaces instead of being rendered as top-level Product/Workspace cards.
 */
export function isPortfolioRootEntity(entity: Entity | null | undefined): boolean {
  if (!entity || !isL1Entity(entity)) return false;
  return entity.type !== "deal" && entity.type !== "person";
}
