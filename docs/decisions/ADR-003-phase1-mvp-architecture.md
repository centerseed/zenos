# ADR-003：Phase 1 Ontology MVP 技術架構

**狀態**：Proposed
**日期**：2026-03-21

## 背景

PM 交付了 Phase 1 Feature Spec（`docs/archive/specs/SPEC-phase1-ontology-mvp.md`），定義了四個交付物：Firestore Schema、MCP Tools、治理流程 MVP、GitHub Adapter。Spec 留了 6 個開放問題待 Architect 決策。

同時，`docs/reference/REF-ontology-methodology.md` 定義了完整的 ontology 治理方法論（Phase A~G），這套方法論必須編碼進 MCP server 的行為裡，而不是只停留在文件層級。

## 決定

### 決策 1：MCP Server 技術棧 → Python + FastMCP

**選擇**：Python 3.12 + FastMCP

| 選項 | 複雜度 | 團隊熟悉度 | 生態系成熟度 | MCP SDK 品質 |
|------|--------|-----------|-------------|-------------|
| Python + FastMCP | Low | ✅ 高（naru_agent 全 Python） | ✅ Firestore SDK 成熟 | ✅ FastMCP 是官方推薦 |
| TypeScript + MCP SDK | Mid | ⚠️ 中 | ✅ 成熟 | ✅ 官方 SDK |
| Go | High | ❌ 低 | ⚠️ Firestore SDK 較弱 | ❌ 無官方 SDK |

**關鍵理由**：Barry 的整個 stack 是 Python，不引入新語言。FastMCP 是 Anthropic 官方推薦的 Python MCP framework，支援 stdio 和 HTTP SSE 兩種 transport。

---

### 決策 2：Firestore Project → 新建 `zentropy-zenos-dev`

**選擇**：新建獨立 Firebase project

| 選項 | 優點 | 缺點 |
|------|------|------|
| 用現有 zentropy-4f7a5 | 零設定成本 | ZenOS 資料跟其他產品混在一起 |
| **新建 zenos-naruvia** | 乾淨隔離、符合 BYOS 精神 | 需要初始化設定 |

**最終選擇**：`zenos-naruvia`（Firestore location: asia-east1）

**命名規則**：
- Naruvia dogfooding：`zenos-naruvia`
- 未來客戶：`zenos-{client}`

---

### 決策 3：MCP Server 部署 → Cloud Run（HTTP SSE transport）

**選擇**：Cloud Run，不是 local stdio，不是 Cloud Functions

| 選項 | 多人存取 | 長連線支援 | 冷啟動 | 成本 |
|------|---------|----------|--------|------|
| Local stdio | ❌ 只有 Barry | N/A | 無 | 免費 |
| Cloud Functions | ✅ | ❌ timeout 限制（9 min max） | 有 | 低 |
| **Cloud Run** | ✅ | ✅ SSE 長連線 | 有（可設 min-instances=1） | 低（scale-to-zero） |

**關鍵理由**：MCP 用 Server-Sent Events（SSE）做 streaming，需要長連線。Cloud Functions 的 timeout 不適合。Cloud Run 支援長連線、scale-to-zero 控制成本、同一個 GCP project 直接存取 Firestore 零延遲。

**架構**：
```
Barry 的 Claude Code ──HTTP SSE──→ Cloud Run（MCP Server）──→ Firestore
行銷同事的 Agent   ──HTTP SSE──→     同一個 MCP Server    ──→ 同一個 Firestore
```

**開發流程**：本地用 stdio 開發測試，CI 部署到 Cloud Run。

---

### 決策 4：search_ontology MVP → Firestore 欄位匹配 + in-memory filter

**選擇**：不用 embedding、不用 Algolia，直接撈全部資料在 Python 裡做關鍵字匹配

| 選項 | 複雜度 | 成本 | 精確度 | 資料量限制 |
|------|--------|------|--------|----------|
| Algolia | High | 付費 | 高 | 無 |
| Firestore 全文搜尋 | Mid | 免費 | 中 | 無 |
| **In-memory keyword match** | Low | 免費 | 中 | ~1000 entries |
| Vector embedding | High | 付費（AI 呼叫） | 最高 | 無 |

**理由**：MVP 階段 Naruvia 一間公司的 ontology 不超過 100 個 entries。全部撈出來在 Python 裡用 tags + name + summary 做 keyword matching 完全夠用。Phase 2 資料量大了再加 embedding。

---

### 決策 5：消費端/治理端 → 同一個 MCP Server

**選擇**：一個 server，靠 tool naming convention 區分

- 消費端（唯讀）：`get_*`, `list_*`, `search_*`, `read_*`
- 治理端（讀寫）：`upsert_*`, `add_*`, `confirm`, `run_*`

**理由**：MVP 只有 Naruvia 一個租戶，沒有權限分離的急迫性。Phase 2 多租戶時再拆成兩個 server + 加 auth。

---

### 決策 6：GitHub Adapter Token → Read-only PAT，scope `repo`

**選擇**：Fine-grained Personal Access Token

- 權限：`Contents: Read-only`
- 範圍：`havital` org 下的指定 repos
- 存放：Cloud Run 的環境變數（dev）/ Secret Manager（prod）

---

### 決策 7：治理方法論編碼 → MCP tools 內建治理邏輯

**選擇**：把 `REF-ontology-methodology.md` 的規則編碼成 MCP tool 的行為

| 方法論規則 | 對應的 MCP 實作 |
|-----------|---------------|
| 拆分粒度（滿足任 2 條件才獨立） | `upsert_entity` 寫入時自動檢查，回傳建議 |
| 4D 標籤（What/Who 自動，Why/How draft） | 所有寫入 tool 內建 `confirmedByUser` 邏輯 |
| 過時推斷（跨實體活動度異常） | 新增 `run_staleness_check` tool |
| 品質檢查（9 項清單） | 新增 `run_quality_check` tool |
| 盲點分析（7 種推斷模式） | `add_blindspot` + `run_blindspot_analysis` tool |
| 拆分/合併建議 | `run_quality_check` 的一部分 |

**新增的治理 tools（PRD 未列，Architect 補充）：**

```
run_quality_check    — 執行 REF-ontology-methodology.md 的 9 項品質檢查
run_staleness_check  — 執行過時推斷（跨實體活動度分析）
run_blindspot_analysis — 執行 7 種盲點推斷模式
```

這三個 tool 是「治理引擎」的 MVP 版本——不是自動觸發（Phase 2），是人在 session 裡手動呼叫。

---

## Code 結構

```
src/
  zenos/
    domain/                    # 純業務邏輯，不依賴外部系統
      models.py                # Entity, Document, Protocol, Blindspot 資料模型
      governance.py            # 治理規則（拆分粒度、4D 標籤、過時推斷、品質檢查）
      search.py                # 關鍵字匹配搜尋邏輯

    application/               # 用例編排
      ontology_service.py      # CRUD 用例（upsert, confirm, list...）
      governance_service.py    # 治理用例（quality check, staleness, blindspot）
      source_service.py        # read_source 用例

    infrastructure/            # 外部系統實作
      firestore_repo.py        # Firestore 讀寫
      github_adapter.py        # GitHub API 讀取文件

    interface/                 # MCP tool handlers
      tools.py                 # 所有 MCP tool 的定義與 handler

  tests/
    domain/                    # 單元測試（治理規則、搜尋邏輯）
    integration/               # Firestore + MCP 整合測試

  Dockerfile                   # Cloud Run 部署用
  pyproject.toml
  .env.example
```

**依賴方向（Dependency Rule）：**
```
interface → application → domain ← infrastructure
                              ↑
                    domain 只依賴抽象介面
                    infrastructure 實作介面
```

---

## 後果

### 變得更容易的事
- 行銷同事的 agent 可以直接透過 HTTP 連 MCP server，跟 Barry 用同一套 context
- 治理方法論有 code 保障，不會因為換人操作就走偏
- Cloud Run scale-to-zero 控制成本，沒人用時不花錢

### 變得更困難的事
- Cloud Run 部署比 local stdio 複雜，需要 Docker + CI
- 需要處理 Cloud Run 冷啟動（設 min-instances=1 可解）

### 未來需要重新評估的事
- Phase 2 多租戶時：需要加 auth + 拆分消費端/治理端 MCP server
- 資料量超過 1000 entries 時：search_ontology 需要換成 embedding
- 需要即時治理時：從手動 `run_*` 改成 Cloud Functions event-driven

## 行動項目

- [ ] 建立 Firebase project `zentropy-zenos-dev`
- [ ] 初始化 Firestore + Security Rules
- [ ] 實作 domain layer（models + governance rules）
- [ ] 實作 infrastructure layer（Firestore repo + GitHub adapter）
- [ ] 實作 application layer（service 編排）
- [ ] 實作 interface layer（MCP tools）
- [ ] 本地測試（stdio transport）
- [ ] Docker 化 + 部署 Cloud Run
- [ ] 用 Naruvia ontology 做 E2E 驗證
