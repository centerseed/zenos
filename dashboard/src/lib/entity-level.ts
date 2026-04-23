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
