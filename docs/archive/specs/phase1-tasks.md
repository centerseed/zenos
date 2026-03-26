# Phase 1 — 實作任務總覽

> Architect 產出 | 日期：2026-03-21
> 技術設計：`docs/decisions/ADR-003-phase1-mvp-architecture.md`
> PM Spec：`docs/specs/SPEC-phase1-ontology-mvp.md`

---

## 任務依賴圖

```
T1 Domain Layer ──────┐
                      ├──→ T3 Application Layer ──→ T4 MCP Tools ──→ T6 E2E 驗證
T2 Infrastructure ────┘                              ↑
                                                     │
T5 Project Scaffold + Deploy Config ─────────────────┘
```

- T1 + T2 + T5 可並行
- T3 依賴 T1 + T2
- T4 依賴 T3 + T5
- T6 依賴 T4

---

## 任務清單

| ID | 任務 | 狀態 | 依賴 | 詳細 Spec |
|----|------|------|------|-----------|
| T1 | Domain Layer（models + governance + search） | 🔲 待開始 | 無 | `tasks/T1-domain-layer.md` |
| T2 | Infrastructure Layer（Firestore repo + GitHub adapter） | 🔲 待開始 | 無 | `tasks/T2-infrastructure-layer.md` |
| T3 | Application Layer（service 編排） | 🔲 待開始 | T1, T2 | `tasks/T3-application-layer.md` |
| T4 | Interface Layer（MCP tools） | 🔲 待開始 | T3, T5 | `tasks/T4-mcp-tools.md` |
| T5 | Project Scaffold + Deploy Config | 🔲 待開始 | 無 | `tasks/T5-scaffold-deploy.md` |
| T6 | E2E 驗證（Naruvia ontology 導入） | 🔲 待開始 | T4 | `tasks/T6-e2e-validation.md` |
| QA1 | 全功能驗收測試 | 🔲 待開始 | T6 | `tasks/QA1-acceptance-test.md` |
