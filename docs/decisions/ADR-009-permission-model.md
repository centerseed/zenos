---
type: ADR
id: ADR-009-permission-model
status: Superseded
superseded_by: SPEC-agent-aware-permission
ontology_entity: TBD
created: 2026-03-23
updated: 2026-03-27
---

# ADR-009: 權限模型（Phase 0 設計）

> 本文件已被 `SPEC-agent-aware-permission` 取代。保留供歷史追溯。
> 從 `docs/spec.md` Part 7.6 搬出。

### 三層權限

```
┌─────────────────────────────────────┐
│ 1. 來源層（Google Drive / GitHub）   │  ← 各平台自己管，ZenOS 不複製
├─────────────────────────────────────┤
│ 2. Ontology 層（ZenOS entity 存取） │  ← ZenOS 管
├─────────────────────────────────────┤
│ 3. 消費層（MCP token / Dashboard）  │  ← 查第 2 層的權限
└─────────────────────────────────────┘
```

第 1 層不需要 ZenOS 管。第 2 層是核心。第 3 層是第 2 層的投射。

### Phase 0 最小權限模型

```
角色           能做什麼
─────────────────────────────
admin（老闆）   全部 entity 讀寫 + 管理成員
member（員工）  全部 entity 讀 + 授權範圍內寫
agent          authorizedEntityIds 範圍內讀寫
```

Entity 加 `visibility`: `"public" | "restricted"`（預設 public）。

### 不做的事（Phase 0）

- 細粒度 RBAC
- 繼承式權限
- 來源層權限同步
