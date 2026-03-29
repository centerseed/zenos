---
type: REF
id: REF-adapter-feasibility
status: Approved
ontology_entity: TBD
created: 2026-03-23
updated: 2026-03-27
---

## Part 7.7 — Adapter 可行性確認（2026-03-23 研究）

### 各平台的整合方式

| 平台 | 客戶要做的事 | ZenOS 要建的 | 監聽方式 | 難度 |
|------|------------|-------------|---------|------|
| GitHub | 給 repo 權限 | Webhook receiver | Push webhook（即時） | 低 |
| Google Drive | OAuth 按一次允許 | OAuth flow + token 管理 + webhook endpoint | changes.watch()（即時） | 中 |
| Notion | OAuth 按一次允許 | OAuth flow + polling job | Polling（無 webhook） | 中 |
| Confluence | OAuth 按一次允許 | Forge app + webhook | Page webhook（即時） | 中高 |

### Google Workspace 的關鍵發現

用 Google Workspace 的公司（台灣 SMB 大多數），IT admin 可以做 **domain-wide delegation**：
- Admin Console 授權一次 → ZenOS 存取整個公司 Drive
- 不需要每個員工各自 OAuth
- 但可以選擇只授權特定資料夾（漸進式信任）

### 與漸進式信任的關係

技術上可以一次授權全公司 Drive，但產品設計上要讓客戶控制範圍：
1. 先授權單一資料夾（如 `公司文件/產品/`）
2. 看到 ZenOS 的效果後，再擴大範圍
3. 最後才是整個 Drive

### 分階段實作

| Phase | 做法 | 自動化程度 |
|-------|------|-----------|
| 現在 | `/zenos-capture {目錄}` 手動掃本地目錄 | 半自動（人觸發，AI 判斷歸屬） |
| 0.5 | Git post-commit hook 觸發 `/zenos-sync` | 自動觸發，AI 判斷歸屬 |
| 1 | GitHub webhook → server 端即時收 push event | 全自動 |
| 2 | Google Drive / Notion adapter | 全自動，需客戶 OAuth 授權 |

**核心壁壘不是掃描和監聽（成熟技術），是 AI 自動歸屬的準確度。** 因為有骨架層（entity 結構 + 四維標籤），AI 判斷「這份文件跟哪個 entity 有關」的準確度比沒有 ontology 時高很多。
