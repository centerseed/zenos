# T4 — Interface Layer（MCP Tools）

> 指派：Developer | 預估：半天
> 依賴：T3, T5
> 技術設計：`docs/decisions/ADR-003-phase1-mvp-architecture.md`
> PRD MCP 介面：`docs/specs/phase1-ontology-mvp.md` 交付物 2

---

## 目標

用 FastMCP 定義所有 MCP tools，連接 Application Layer。

## 產出檔案

```
src/zenos/interface/
  tools.py          # MCP server + 所有 tool 定義
```

---

## tools.py

### Server 初始化

```python
from fastmcp import FastMCP

mcp = FastMCP("ZenOS Ontology")

# 依賴注入
entity_repo = FirestoreEntityRepository()
# ... 其他 repo
ontology_service = OntologyService(entity_repo, ...)
governance_service = GovernanceService(...)
source_service = SourceService(...)
```

### 消費端 Tools（唯讀）

| Tool | 輸入 | 輸出 |
|------|------|------|
| `get_protocol` | entity_name: str | Protocol content + gaps |
| `list_entities` | type?: str | Entity list (name, type, status, summary) |
| `get_entity` | entity_name: str | Entity + relationships |
| `list_blindspots` | entity_name?: str, severity?: str | Blindspot list |
| `get_document` | doc_id: str | Document full fields |
| `read_source` | doc_id: str | Raw file content string |
| `search_ontology` | query: str | Mixed results list with scores |

### 治理端 Tools（讀寫）

| Tool | 輸入 | 輸出 |
|------|------|------|
| `upsert_entity` | Entity fields (id optional) | Entity + governance suggestions |
| `add_relationship` | source_entity_id, target_entity_id, type, description | Relationship |
| `upsert_document` | Document fields | Document |
| `upsert_protocol` | Protocol fields | Protocol |
| `add_blindspot` | Blindspot fields | Blindspot |
| `confirm` | collection: str, id: str | Updated entry |
| `list_unconfirmed` | collection?: str | Grouped unconfirmed entries |

### 治理引擎 Tools（Architect 補充）

| Tool | 輸入 | 輸出 |
|------|------|------|
| `run_quality_check` | (無) | QualityReport |
| `run_staleness_check` | (無) | StalenessWarning list |
| `run_blindspot_analysis` | (無) | Blindspot list |

### 每個 Tool 的標準格式

```python
@mcp.tool()
async def get_protocol(entity_name: str) -> dict:
    """取得某個產品/實體的 Context Protocol。
    行銷 agent 寫素材前先讀產品 context。"""
    result = await ontology_service.get_protocol(entity_name)
    if result is None:
        return {"error": "NOT_FOUND", "message": f"No protocol found for '{entity_name}'"}
    return asdict(result)
```

### 錯誤回傳格式

統一用 dict，不拋例外（MCP tool 不應該 crash）：
```python
{"error": "NOT_FOUND", "message": "..."}
{"error": "INVALID_INPUT", "message": "..."}
{"error": "ADAPTER_ERROR", "message": "..."}
```

### 啟動入口

```python
if __name__ == "__main__":
    import sys
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        port = int(os.environ.get("PORT", "8080"))
        mcp.run(transport="sse", port=port)
    else:
        mcp.run(transport="stdio")
```

---

## Done Criteria

- [ ] 所有 17 個 MCP tools 定義完成
- [ ] 每個 tool 有 docstring（讓 AI agent 知道什麼時候該用）
- [ ] 錯誤回傳格式統一
- [ ] stdio transport 本地可跑
- [ ] SSE transport 可啟動（port 8080）
- [ ] /simplify 執行完畢
