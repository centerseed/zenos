---
name: zenos-capture
description: >
  從對話、單一文件、或目錄擷取知識並寫入 ZenOS ontology。
  這份 release skill 只保留 runtime 骨架；治理規則 SSOT 在 governance_guide。
version: 3.0.0
---

# /zenos-capture

> **Reference only.**
> SSOT: `governance_guide(topic="capture", level=2)` via MCP.
> This file is a human-readable mirror and MAY LAG the SSOT.
> Agents must call governance_guide before acting on rules.

## 啟動順序

1. 先讀 `skills/governance/bootstrap-protocol.md`，完成 Step 0。
2. 先 call `governance_guide(topic="capture", level=2)`。
3. 若這次會建 L2，補 call `governance_guide(topic="entity", level=2)`。
4. 若這次會建 document，補 call `governance_guide(topic="document", level=2)`。
5. 若這次其實是增量同步，不要硬走 capture，改用 `zenos-sync`。

## 三種模式

### 1. 無引數：對話捕獲

- 來源是最近對話。
- 只抽「code / git / 文件原文看不到，但下次會改變行為」的知識。
- 若內容只是執行過程或暫時討論，不要寫 entry。

### 2. 單一檔案：文件捕獲

- 先讀檔案，再做分層路由。
- 正式文件建 document metadata，不把整份原文塞進 ontology。
- `linked_entity_ids` 必填，找不到對應 L2 就先停下來做關聯判斷。

### 3. 目錄：首次建構

- 這是冷啟動模式，不是增量 sync。
- 先掃描目錄，分出骨架文件、規格文件、其餘文件。
- 先形成全景理解，再一次性提出 L2 proposals，等用戶確認後才寫入。

## 分層路由

- 公司共識概念，改了有下游影響：L2 entity
- 正式文件入口：document
- 某個 agent 下次看到會改變做法的短知識：entry
- 執行工作或修復事項：task，不要混進 capture
- 說不出 impacts、只是一次性資料、只是原文備份：不要寫或降到 source

## 寫入底線

- 所有 `search` / `write` 都帶 product scope。
- document 一律帶 `linked_entity_ids`。
- `doc_role=index` 預設成立；同主題第二份文件不要再建平行 single。
- Helper / connector 來源（Notion、GDrive、local、upload、wiki、url）要盡量帶 `snapshot_summary`；它是 10KB 內語意摘要，不是全文 mirror。
- **本地 md 檔要讓 web 顯示完整內容**：用 `initial_content` 參數（最多 1MB）在建 entity 時直接寫入 GCS revision，不必走 snapshot_summary 截斷。`initial_content` 僅限 create；update 請走 `POST /api/docs/{doc_id}/content`。
- 新建 bundle 使用 `sources: [...]` 時，要保留 `snapshot_summary`、`external_id`、`external_updated_at`、`last_synced_at`、`retrieval_mode`、`content_access`，否則後續 analyzer 只能產 metadata-aware summary。
- 需要具體治理規則時，回頭再 call `governance_guide`，不要靠這份檔案腦補。

## 完成後

- 回報這次新增 / 更新了哪些 entity、document、entry。
- 若發現規則缺口、資料不完整、或需要後續修復，建 blindspot 或 task。
- 只有實際新增/更新知識，或留下 TBD / blindspot 需要下輪接續時才寫 journal；純掃描無變更不要寫。
