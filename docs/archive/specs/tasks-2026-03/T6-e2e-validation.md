# T6 — E2E 驗證（Naruvia Ontology 導入）

> 指派：Developer + QA | 預估：半天
> 依賴：T4
> 資料來源：`docs/ontology-instances/paceriz/`、`docs/context-protocols/paceriz.md`

---

## 目標

用 Naruvia（Paceriz）的現有 ontology 資料，透過 MCP tools 完整走一遍導入流程，驗證端到端可用。

## 驗證流程

### Step 1：首次建構 Ontology（模擬 治理流程一）

```
1. 讀 docs/ontology-instances/paceriz/index.md → 識別骨架層實體
2. 呼叫 upsert_entity() 建立所有實體（Paceriz, Rizo AI, 訓練計畫, 數據整合, ACWR）
3. 呼叫 add_relationship() 建立依賴關係
4. 讀 docs/ontology-instances/paceriz/neural-layer.md → 識別文件
5. 呼叫 upsert_document() 建立文件索引（source.uri 用 GitHub URL）
6. 讀 docs/ontology-instances/paceriz/blindspots.md → 識別盲點
7. 呼叫 add_blindspot() 建立盲點
8. 讀 docs/context-protocols/paceriz.md → 組裝 Protocol
9. 呼叫 upsert_protocol() 建立 Protocol
```

### Step 2：消費端驗證（模擬 治理流程三）

```
1. get_protocol("Paceriz") → 應拿到完整 Protocol
2. list_entities(type="module") → 應拿到 4 個模組
3. get_entity("Rizo AI") → 應拿到 Rizo + 依賴關係
4. list_blindspots(severity="red") → 應拿到高優盲點
5. search_ontology("ACWR 安全") → 應匹配到 ACWR entity + 相關文件
6. read_source(doc_id) → 應拿到 GitHub 上的文件內容
```

### Step 3：治理端驗證

```
1. list_unconfirmed() → 應列出所有 draft entries
2. confirm("entities", entity_id) → 應成功確認
3. run_quality_check() → 應回傳品質報告
4. run_staleness_check() → 應回傳過時警告（如有）
```

---

## 成功條件（對應 PRD）

- [ ] 行銷 agent 呼叫 `get_protocol("Paceriz")` 拿到完整產品 context
- [ ] 行銷 agent 呼叫 `read_source(doc_id)` 拿到 GitHub 文件內容
- [ ] Barry 能透過 MCP tools 建構完整 ontology
- [ ] 所有 entries 都有 confirmedByUser 機制
- [ ] source.uri 全部是可存取的 URI

---

## Done Criteria

- [ ] Naruvia ontology 完整寫入 Firestore
- [ ] 消費端 7 個 tool 全部回傳正確結果
- [ ] 治理端 confirm 流程正常
- [ ] 治理引擎 3 個 tool 回傳合理結果
- [ ] 無 local path 出現在 source.uri
