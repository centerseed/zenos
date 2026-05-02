# L2 知識節點治理規則 v2.2

> **Reference only.**
> SSOT: `docs/specs/SPEC-ontology-architecture.md` §7, §10.2, §15 and
> `governance_guide(topic="entity", level=2)` via MCP.
> This file is a human-readable mirror and MAY LAG the SSOT.
> Agents must call governance_guide before acting on rules.

## L2 的定位

L2 是跨角色公司共識概念，不是文件索引、不是 task、不是單一人的筆記。

一句話判斷：這個概念改了，是否會讓多個角色或下游流程需要重新理解、檢查或更新？如果會，才可能是 L2。

## 建立 L2 前的三問

建立或審查 L2 時，三問必須全部為 true：

1. `q1_persistent`：這是不是持久的公司核心知識，而不是短期 sprint note？
2. `q2_cross_role`：這是不是跨角色共識，而不是某個人的個人工作筆記？
3. `q3_company_consensus`：這是不是公司在不同情境都會指向同一件事的知識？

三問任一為 false：不要建 L2。改用 L3 document、task、entry，或只保留為 source。

## impacts gate

三問全過後，還要有至少一條具體 `impacts`。

`impacts` 寫法必須是「A 改了什麼 → B 的什麼要跟著看」。

好的例子：
- `MCP tool envelope 改了 → agent parser 與 dashboard error handling 要跟著檢查`
- `L2 confirm gate 改了 → write/confirm tool 的 reject 行為與 skill 指引要同步`

不合格例子：
- `A related to B`
- `影響治理`
- `需要之後看`

## MCP write 最小格式

建立 L2 必須提供 `layer_decision`，缺少會被 server reject。

```python
mcp__zenos__write(
    collection="entities",
    data={
        "type": "module",
        "name": "清楚的 L2 名稱",
        "parent_id": PRODUCT_ID,
        "summary": "跨角色可讀的公司共識摘要，避免只寫 API/schema/backend 等工程實作細節。",
        "tags": {
            "what": ["核心概念"],
            "why": "為什麼公司需要共同理解它",
            "how": "它影響哪些流程或判斷",
            "who": ["PM", "Architect", "Developer"]
        },
        "layer_decision": {
            "q1_persistent": True,
            "q2_cross_role": True,
            "q3_company_consensus": True,
            "impacts_draft": "此 L2 的邊界改了 → 下游流程或文件要跟著看"
        }
    }
)
```

## Lifecycle

L2 的 draft 不是 `status="draft"`。

合法狀態是：
- Draft：`confirmed_by_user=false` + `status="active"`，新建預設。
- Confirmed：`confirmed_by_user=true` + `status="active"`，三問與 impacts gate 通過。
- Stale：`confirmed_by_user=true` + `status="stale"`，impacts 斷鏈或久未 review。

L2 不使用 `archived/current/planned/completed/paused`。要收掉 L2，只能降級為 source、降級為 L3 document，或由 admin 物理刪除。

## Entries

L2 可以掛 `EntityEntry`，用來保存 decision / insight / limitation / change / context。

規則：
- Entry 只掛 L2，不掛 L3。
- 單一 L2 active entries 達 20 筆以上時，跑 `analyze(check_type="quality")` 看 saturation，再用 `analyze(check_type="consolidate", entity_id=...)` 做單點歸納。
- 不要把 task result 或整份文件塞成 entry；entry 是 1-200 字的結構化知識片段。

## 審查與修復流程

1. 先用 `get(collection="entities", id=..., include=["summary", "relationships", "entries"])` 看現況。
2. 再用 `analyze(check_type="entity_health", entity_id=...)` 做單點審查。
3. 若要看某個產品範圍，用 `analyze(check_type="quality", entity_id=PRODUCT_ID)` 或 `product_id=PRODUCT_ID`，避免全域噪音。
4. 缺 impacts：補 relationship，description 必須具體。
5. summary 太技術：改寫成跨角色語言。
6. 概念太窄或不可共識：降級為 L3 document / source。

## 禁止模式

- 不要用 L2 當文件資料夾。
- 不要用 `related_to` 取代 impacts gate。
- 不要建立沒有 `parent_id` 的 L2。
- 不要在 L2 create 時嘗試直接設 `confirmed_by_user=true`。
- 不要把短期任務、個人 TODO、單次會議結論建成 L2。
