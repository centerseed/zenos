# ADR-003：Ontology 治理觸發架構

**日期**：2026-03-22
**狀態**：已決定（待 Architect 設計實作方案）
**來源**：PM session，從 dogfooding 中發現的核心產品問題

---

## 決定了什麼

Ontology 的治理觸發採用 **Adapter 架構**，事件來源不同但治理引擎共用。Phase 0 先做 Claude Code hook，驗證「自動觸發 → ontology 更新」的完整路徑。

## 問題背景

Ontology 在 Firebase，但各專案文件四散在 local 環境各處。文件變化（修改、搬家、合併、新增、刪除）都應該觸發 ontology 更新，但目前沒有任何機制偵測「文件變了」。

使用者（包括 Barry 自己）不會記得每次改完文件要去更新 ontology。手動觸發（`/zenos-capture`）把責任放在人身上，跟 Notion 要人手動整理是同一個問題——違背 ZenOS「AI 自動治理」的核心價值。

## 架構決策

### 兩條觸發路徑，同一個引擎

```
Agent-based 工作流（Phase 0）        傳統工作流（Phase 1+）
─────────────────────────          ─────────────────────
Claude Code hook                    Google Drive webhook
Cursor hook                         Notion API webhook
Windsurf hook                       Slack event subscription
GitHub Actions                      OneDrive Graph API
     |                                    |
     └──────────┬─────────────────────────┘
                v
         ZenOS Governance Engine
         （收到事件 → 分析變化 → 更新 ontology）
```

### Phase 0 實作：Claude Code Hook

**觸發方式**：`PostToolUse` hook 監聽 Edit/Write 事件

**採用模式 B（Session 結束彙總）**：
- Session 中：hook 靜靜記錄哪些 .md 檔案被改了（不打斷工作流）
- Session 尾巴：彙總提醒「這些檔案改了，ontology 可能要更新」
- 搭配模式 C（定期掃描）：每週自動跑 staleness check

**不採用模式 A（即時提醒）**：改 10 個檔案被問 10 次太干擾。

### 文件變化的 5 種場景

| 場景 | Ontology 動作 | 觸發來源 |
|------|--------------|---------|
| 文件內容修改 | 檢查 summary 是否過時 | hook（Edit/Write） |
| 文件搬家/改名 | 更新 source.uri | hook + git diff |
| 文件合併 | 合併/archive entries | hook + 人確認 |
| 新文件建立 | 建議建 entry | hook（Write） |
| 文件刪除 | archive entry | hook + git diff |

### source.uri 的橋接

Hook 知道 local 路徑，需要能：
1. 從 local 路徑算出 GitHub URL（`git remote` + 相對路徑）
2. 用 GitHub URL 查 ontology 找到對應 entry
3. 或反過來：ontology search by file name 做模糊匹配

具體方案待 Architect 決定。

## 為什麼這樣決定

1. **Hook 是 Phase 0 的 Governance Daemon**——不需要基礎設施，Claude Code 原生支援
2. **Adapter 架構保證擴展性**——新增 Google Drive 監聽 = 新增 adapter，引擎零改動
3. **模式 B 平衡了「不漏」和「不煩」**——治理不能依賴人記得，但也不能打斷工作流
4. **ZenOS dogfooding 驗證**——Barry 自己在這次 session 體驗到「不知道什麼時候該更新 ontology」的痛點

## 放棄的選項

- **純手動（`/zenos-capture`）**：把責任放在人身上，違背核心價值
- **即時提醒（模式 A）**：太干擾，每次改檔案都問
- **純定期掃描（模式 C）**：延遲太高，對話中產生的知識可能在下次掃描前就遺忘了

## 影響

- 所有 Claude Code skills 的設計需要考慮「session 結束前的 ontology check」
- MCP server 可能需要新增 `diff_check` 或 `batch_update` 工具
- source.uri 的存儲格式需要 Architect 決定（影響 hook 的查詢邏輯）
- 這個設計直接影響未來 Google Drive / Notion adapter 的介面

## 交給 Architect 的問題

1. Hook 的具體實作：怎麼在 Claude Code settings.json 中配置 PostToolUse hook？
2. source.uri 格式：GitHub URL only？加 local path？還是 repo-relative path？
3. Governance Engine 的介面：hook 呼叫什麼 MCP tool 來觸發檢查？現有 tools 夠用嗎？
4. 跨專案掃描：hook 怎麼知道「這個 local 目錄屬於哪個 ontology instance」？
