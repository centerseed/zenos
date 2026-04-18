# Hand-off: 2026-04-18 ZenOS Governance Refactor

## TL;DR

這個 session 做了一輪大幅的治理系統減法。砍掉 3 個壞/多餘功能（verb、圖拓撲 blindspot、server-runtime SSOT audit），修了 2 個真實 bug（coverage 演算法、analyze schema），然後 dogfood 實測出核心痛點：**MCP `get`/`search` 回傳 eager-dump**，寫了 **ADR-040** 等審。下一個 session 要做的事：**(1) 審 ADR-040、(2) 開 SPEC-semantic-retrieval（Pillar A）**。

---

## 做完的事

### 4 個 commits（淨減 ~1055 行 code）

| Commit | 內容 | 影響 |
|--------|------|------|
| `04a0cd1` | 修 coverage 演算法納入 `entity.sources` + `.gcloudignore` 首試（失敗）| 解決 47 個假陽性 blindspot 中的大量誤報 |
| `e1118c2` | `.gcloudignore` 第二次嘗試（deploy 後仍無效）| 最終放棄此路線 |
| `ff090c0` | 砍 relationship.verb + 圖拓撲 blindspot（-1006 行）| 砍除 verb 8.8% 填寫率的死 feature + 51 筆 topology 假陽性 |
| `bf0e939` | 移除 server-runtime `governance_ssot_audit`（-49 行）| 改為 CI-only lint（`scripts/lint_governance_ssot.py` 早就在 `.github/workflows/ci.yml:24-25` 跑） |

### Production 變更

- **Cloud SQL**：跑 `migrations/20260417_0001_usage_logs_outcome.sql` 加 `outcome` column + index
- **Cloud SQL**：執行 `scripts/cleanup_topology_blindspots.sql`，清除 51 筆 topology 假陽性 blindspot（57 → 6）
- **Cloud Run**：3 次 deploy

### KPI 前後對比

| KPI | Session 開始 | Session 結束 | 變化 |
|-----|------------|-------------|------|
| `blindspot_total` | 57 red | **6 green** | -89% |
| `unconfirmed_ratio` | 49.2% yellow | **17.3% green** | -65% |
| `governance_ssot` | 7 red（假陽性）| **KPI 消失** | 架構層修好 |
| `overall red_reasons` | 3 個（含 2 個假陽性）| **1 個（真實：llm_health）** | 清掉雜音 |
| `quality_score` | 54 | 54 | 持平 |

### 關鍵產出

- **ADR-040**：`docs/decisions/ADR-040-mcp-read-api-opt-in-include.md` — MCP get/search 從 eager-dump 改 opt-in include（**status: Draft，等審**）

---

## 下一步（新 session 優先順序）

### 🔴 P0：審 ADR-040

用戶在 session 結束前寫完了 ADR-040 但還沒審。審核點：
- 分段遷移計畫（Phase A backward compat → Phase B 切換 default → Phase C 移除 legacy）是否可接受？
- 3 個月 / 6 個月時程是否合理？
- 拒絕的 3 個 alternative（拆多 tools / per-field filter / 只壓 response）理由是否夠？

審完同意 → 進 Phase 1.3（ADR 實作前的 test stubs）→ dispatch Developer。

### 🟡 P1：開 SPEC-semantic-retrieval（Pillar A）

Dogfood 實測痛點 A：純關鍵字 search 在 298 entity 規模已經回噪音。即使 ADR-040 精簡了回傳，**search 本身找不到相關 entity** 的問題仍在。需要 embedding + vector search。

這是**新功能**（migration + pgvector + embedding pipeline + hybrid re-ranking），必須走 SPEC + AC IDs + TD 流程。

建議 SPEC 涵蓋：
- P0: Entity summary + document content 的 embedding pipeline（ingest-time）
- P0: search tool 加 semantic mode（hybrid: vector + keyword fallback）
- P1: Re-ranking（結合 type prior / recency / confirmed_by_user）
- P1: Embedding cache 和 re-embed 觸發條件
- P2: Community detection / hierarchical summary（Microsoft GraphRAG 風格）

**前置依賴**：ADR-040 先落地，讓 search 回傳結構精簡，再加 embedding score。

### 🟢 P2（獨立 session，需要戰略思考）

- **Server-side AI 砍除**：`governance_ai.py` 的 4 個推斷功能（infer_all / infer_doc_entities / infer_task_links / consolidate_entries）都是「策展自動化」——用戶這次 session 質疑了必要性。砍掉後 `llm_health` KPI 也跟著消失，deploy 不需要 Gemini API key。待戰略確認。
- **Skill 升級可執行 code**：用戶想讓 skill 帶 Python/Bash 腳本，不只 prompt。`skills/release/zenos-setup/scripts/` 是現有案例。需要：(1) 定義 skill manifest 格式；(2) 2-3 個具體 use case 先列出來避免又是「無 consumer 的結構」。

---

## 重要教訓（寫進 session memory，避免重蹈）

1. **不要先相信 KPI 再推診斷**：session 早上花很多時間分析「為什麼 blindspot 57 red」，後來發現大量是**演算法 bug**（coverage 漏算 sources）。之後診斷前先驗證指標可靠。

2. **Test PASS ≠ Production OK**：`.gcloudignore` 修了兩次 local 驗證都過（`gcloud meta list-files-for-upload` 說會 upload 48 個 SPEC），deploy 後 server 還是找不到。最終才搞清楚是架構錯位（server runtime 不該讀 dev-repo filesystem），改走 CI-only 才解。

3. **「沒 consumer 的結構 = 負債」（session 最大單一教訓）**：砍掉的 3 個功能（verb 8.8%、圖拓撲 89% 假陽性、server-runtime SSOT audit 永遠 red）都是「實作完成但沒人用」。未來補 SPEC 前的 gate：**「如果刪掉這個結構誰會痛」，說不出具體 consumer 就不要建**。

4. **Challenger 挑戰過的結論要認真採納**：Session 早上我給「ZenOS 範式錯」的結論，用戶 challenger 視角打掉兩次才修正為「API eager-dump + 缺 Pillar A」的真正根因。**列 8 個第一性原理 = 警訊**，真正的根因通常 1-2 個。

5. **Dogfood 是最強診斷**：4 次 MCP call 就讓所有抽象討論具體化——「agent skill 太大、呼叫多、capture 慢」是 search 找不到 + get 回 40k 的直接後果。**動手操作一次 > 一小時抽象分析**。

---

## 關鍵檔案路徑（下次 session 快速定位）

### 待審
- `docs/decisions/ADR-040-mcp-read-api-opt-in-include.md` — 本 session 產出，等審

### 本 session 改動的 source code
- `src/zenos/domain/governance.py:479-507` — coverage 演算法（改過）
- `src/zenos/interface/mcp/analyze.py` — governance_ssot 移除（line 7, 212-213 等）
- `src/zenos/application/knowledge/governance_service.py` — `_merge_governance_ssot_signal` 移除
- `src/zenos/domain/knowledge/models.py:68` — Relationship.verb 移除
- `.gcloudignore` — docs/specs 豁免規則（最終版本，但效果未達預期，被 CI-only 路線 supersede）
- `scripts/cleanup_topology_blindspots.sql` — production 已跑

### 不要動的「看似相關但正確」
- `src/zenos/application/knowledge/governance_ssot_audit.py` — CI 用，**保留**
- `scripts/lint_governance_ssot.py` — CI entry point，**保留**
- `.github/workflows/ci.yml:24-25` — CI job，**保留**
- `tests/application/test_governance_ssot_audit.py` — 測 library 本身，**保留**

### 下一個 session 會讀的
- `src/zenos/interface/mcp/get.py` — ADR-040 的主要修改目標
- `src/zenos/interface/mcp/search.py` — ADR-040 同步修改
- `src/zenos/interface/dashboard_api.py` — 確認 dashboard 不受 MCP 改動影響（走 REST）

---

## 不要再踩的坑

1. **不要再試改 `.gcloudignore` 讓 Cloud Run image 含 docs/**——兩次都失敗，架構錯位無法用 pattern 救。若需要 server 讀 dev-repo artifact，重新設計（build-time bundle 進 Python package）
2. **不要以為「server-side AI 推斷」是必要功能**——`governance_ai.py` 的 4 個推斷被用戶質疑是多餘，等戰略確認
3. **不要在 SPEC 沒 consumer 時就寫實作**——ADR-040 有明確的 agent token cost 痛點，SPEC-semantic-retrieval 也有具體的 search 失敗實測。沒這些證據就不要補 structure
4. **不要信任「pre-existing failures」這個標籤**——session 前半一直假設 18 個 test 是 pre-existing，實際 dogfood 時發現全 PASS，之前不知道從哪個點變綠了。**每次跑 test 以當下結果為準**

---

## 如何在新 session 快速進入狀態

```
1. 讀本 hand-off（約 2 分鐘）
2. mcp__zenos__journal_read(limit=5, project="zenos") — 看最後 5 筆確認沒有新變動
3. 讀 docs/decisions/ADR-040-mcp-read-api-opt-in-include.md — 直接進入待審狀態
4. 決定：
   - 審 ADR-040 並同意 → 進 Phase 1.3 (AC test stubs) → dispatch Developer
   - 或先開 SPEC-semantic-retrieval（獨立產物，可平行）
```

建議**先 ADR-040** 因為：
- 是 session 產出的直接結論
- 實作小、一個 commit 可完成
- 落地後 agent 體驗 20x 改善
- 為 SPEC-semantic-retrieval 鋪路（search 回傳結構先精簡）
