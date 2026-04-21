---
doc_id: ADR-017-skill-agent-install-architecture
title: 架構決策：Skill/Agent 安裝流程——SSOT 邊界、多平台分發、LOCAL.md 保護
type: ADR
ontology_entity: MCP 介面設計
status: Approved
version: "2.1"
date: 2026-04-21
supersedes: null
---

# ADR-017: Skill/Agent 安裝流程——SSOT 邊界、多平台分發、LOCAL.md 保護

## Context

ZenOS 安裝流程負責將五種元件（Skill、Agent、Workflow、Governance、Hook）分發到用戶環境。現有設計文件：

- **SPEC**: `docs/specs/SPEC-zenos-setup-redesign.md` — 定義 setup/install 職責拆分、P0 需求
- **TD**: `docs/designs/TD-agent-setup.md` — 跨平台 adapter 架構、server 端實作設計
- **Server 實作**: `src/zenos/interface/setup_adapters.py` + `setup_content.py` — 三個平台 adapter 已完成

本 ADR 不重複上述文件的內容，而是針對以下三個 SPEC/TD 未明確決策的架構問題做出選擇：

**問題 1：兩份 setup 流程定義的 SSOT 邊界不清。**
`skills/release/zenos-setup/SKILL.md`（global skill，含 bootstrap 自我更新 + curl GitHub manifest）和 `skills/workflows/setup.md`（project slash command，走 `mcp__zenos__setup()`）是兩條不同流程，步驟號不同，manifest 來源不同。維護者已經發生改了一份忘了改另一份的情況。

**問題 2：多平台的 server 端已完成，但 client-side skill 只覆蓋 Claude Code。**
Server 端三個 adapter（`build_claude_code_payload`、`build_claude_web_payload`、`build_codex_payload`）各自回傳完整 payload。但 client 端只有 Claude Code 的 `/zenos-setup` skill 定義了完整的安裝步驟（讀 payload → 寫入檔案 → 驗證）。Codex 和 Claude Web 的 payload 已可用，但缺少對應的 client-side 安裝引導。

**問題 3：`LOCAL.md` 在兩個層級面臨不同性質的覆蓋風險。**

| 層級 | 位置 | 風險來源 | 目前保護 |
|------|------|---------|---------|
| Project-level | `.claude/skills/{role}/LOCAL.md` | `/zenos-setup` 安裝步驟寫入 SKILL.md | 流程約定（只寫 SKILL.md），無程式保證 |
| Home-level | `~/.claude/skills/{role}/LOCAL.md` | `sync_skills_from_release.py` 的 `shutil.rmtree` | **無保護，會被刪除** |

## Decision

### D1: 兩份 setup 定義的角色分工

`skills/release/zenos-setup/SKILL.md` 和 `skills/workflows/setup.md` 不是「兩份 SSOT」，而是兩個不同職責：

| 檔案 | 職責 | 觸發時機 |
|------|------|---------|
| `skills/release/zenos-setup/SKILL.md` | **Bootstrap**：在 MCP 連線建立前，用 curl 從 GitHub 安裝 setup skill 本身 | 新用戶第一次執行，或 global skill 自我更新 |
| `skills/workflows/setup.md` | **正式安裝流程**：MCP 連線後，走 `mcp__zenos__setup()` 取 manifest，版本比對，寫入檔案 | `/zenos-setup` slash command，所有後續安裝/更新 |

兩者的差異（步驟號、manifest 來源）是合理的，因為它們處理的前提條件不同。但目前缺少明確的文件說明這個分工，導致維護者誤以為應該保持一致。

**決策：** 在 `skills/release/zenos-setup/SKILL.md` 開頭加入明確標注：

```markdown
> 本文件是 bootstrap 流程，僅用於 MCP 連線建立前的首次安裝。
> MCP 連線建立後，正式安裝流程由 `skills/workflows/setup.md` 定義。
> 兩者職責不同，不應保持步驟一致。
```

修改 `skills/workflows/setup.md` 中不再引用 bootstrap 邏輯（curl 自我更新 global skill）。

### D2: 多平台安裝——server payload 已完成，client-side 引導分三種模式

Server 端 `setup_adapters.py` 的三個 adapter 已經為每個平台定制了 payload：

| 平台 | Server adapter | Payload 內容 | Client-side 安裝引導 |
|------|---------------|-------------|---------------------|
| Claude Code | `build_claude_code_payload` | manifest + slash_commands + claude_md_addition + GitHub raw URL | `skills/workflows/setup.md`（完整 skill 流程） |
| Claude Web | `build_claude_web_payload` | project_instructions（精簡版，~1.5k tokens）+ project_documents_tip | payload 內的 `instructions` 欄位（3 步，貼入 Project Instructions） |
| Codex | `build_codex_payload` | manifest + agents_md_addition + GitHub raw URL + addon-aware merge 指引 | payload 內的 `instructions` 欄位（4 步，curl + merge + AGENTS.md） |

**決策：** Claude Web 和 Codex 不需要獨立的 client-side skill 檔案。它們的安裝引導已內嵌在 server payload 的 `instructions` 欄位中，由呼叫端 agent 按 instructions 執行即可。這與 SPEC-zenos-setup-redesign.md 第 112 行的設計一致：「非 Claude Code 平台的安裝流程由 `mcp__zenos__setup` MCP tool 負責」。

補充約束：
- payload 必須明確回傳 `installation_targets`，至少區分「當前目錄」與「家目錄」兩種安裝目標（Claude Web 例外，固定為 Project Instructions）
- agent 必須先問使用者 target；若使用者未指定，預設推薦當前目錄
- payload 必須附 `usage_summary`，讓安裝完成後 agent 能直接用白話解釋各 skill 什麼時候用

未來若某平台的安裝步驟複雜到 `instructions` 欄位不夠用，再為該平台建立獨立的 workflow skill。

### D3: `sync_skills_from_release.py` 改為白名單覆蓋，保護 LOCAL.md

目前 `sync_skills_from_release.py` 第 35-36 行：
```python
if dst.exists():
    shutil.rmtree(dst)
shutil.copytree(src, dst)
```

這會刪掉 `~/.claude/skills/{role}/` 下所有檔案，包括 LOCAL.md。

**決策：** 改為只覆蓋 SSOT 管理的檔案，保留非 SSOT 檔案：

```python
# 覆蓋：SKILL.md、references/ 目錄下所有檔案
# 保留：LOCAL.md、其他非 SSOT 檔案
```

具體做法：列舉 release 目錄下的檔案，逐一 copy 到目標，不刪除目標目錄中不在 release 中的檔案。

Project-level `.claude/skills/{role}/LOCAL.md` 的保護仍靠流程約定（安裝步驟只寫 SKILL.md + addon merge）。但 addon-aware merge 機制（`<!-- ZENOS_ADDON_SECTION_START -->`）已提供了 SKILL.md 內部客製化的程式保證。

### D4: 安裝流程規範步驟（基於現有 SPEC/TD，本 ADR 不重新定義）

完整安裝流程定義在：
- MCP 連線設定：`SPEC-zenos-setup-redesign.md` P0 需求
- Skill 分發 payload：`TD-agent-setup.md` D1~D4
- Client-side 安裝步驟：`skills/workflows/setup.md`

本 ADR 不重複定義步驟，僅記錄分發路徑：

```
skills/release/ (SSOT)
│
├─→ Server 打包（setup_content.py 讀取，setup_adapters.py 組裝）
│     ↓ mcp__zenos__setup(platform) 回傳 payload
│     Agent 按 payload.instructions 執行安裝
│
├─→ sync_skills_from_release.py（開發者本機同步）
│     ~/.claude/skills/{role}/SKILL.md   白名單覆蓋（D3）
│     ~/.claude/agents/{name}.md         from skills/agents/
│     ~/.codex/skills/ + ~/.codex/agents/
│
└─→ Bootstrap（無 MCP 時）
      curl GitHub raw → 安裝 setup skill 本身
      → 重啟 → /zenos-setup → 走正式流程
```

## Alternatives

| 方案 | 優點 | 缺點 | 為什麼不選 |
|------|------|------|-----------|
| **D1 alt: 合併兩份 setup 為一份** | 只維護一份文件 | Bootstrap（無 MCP）和正式安裝（有 MCP）的前提條件不同，合併會讓流程充滿 if-else 分支 | 分離是合理的，問題出在缺少文件說明分工 |
| **D2 alt: 為每個平台建獨立 workflow skill** | 每個平台有完整的 client-side 流程文件 | 三份文件要各自維護，且 Claude Web/Codex 的安裝步驟很短（3-4 步），不值得獨立成 skill | Server payload 的 instructions 欄位已足夠 |
| **D3 alt: 用 .gitignore 式排除清單** | 靈活，可排除任意檔案 | 增加複雜度，LOCAL.md 是目前唯一需要保護的非 SSOT 檔案 | 白名單覆蓋更簡單直接 |

## Consequences

**正面：**
- Bootstrap 和正式安裝的角色分工明確，維護者不再誤改
- HOME-level LOCAL.md 有程式保證不被刪除
- 多平台分發路徑清楚：server adapter 已完成，client-side 引導已內嵌在 payload

**負面：**
- `sync_skills_from_release.py` 需要重構（從 rmtree+copytree 改為白名單覆蓋）
- `skills/release/zenos-setup/SKILL.md` 需要加入 bootstrap 標注
- 若未來有平台的安裝步驟超出 `instructions` 欄位能承載的範圍，需要回頭為該平台建 workflow skill

**不處理（明確排除）：**
- Setup/Install 職責拆分 → 已由 `SPEC-zenos-setup-redesign.md` 定義
- Server 端 adapter 實作細節 → 已由 `TD-agent-setup.md` 定義
- MCP 連線設定（token 管理）→ 不在本 ADR 範圍

## Implementation

1. 重構 `scripts/sync_skills_from_release.py`：rmtree → 白名單檔案級 copy
2. 在 `skills/release/zenos-setup/SKILL.md` 開頭加入 bootstrap 角色標注
3. 驗證：在有 LOCAL.md 的環境跑 `sync_skills_from_release.py`，確認 LOCAL.md 存活
