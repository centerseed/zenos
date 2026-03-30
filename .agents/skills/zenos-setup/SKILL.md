---
name: zenos-setup
description: >
  ZenOS 初始化與更新——首次使用時設定 MCP 連線，之後每次執行都會
  從 GitHub 拉取最新治理 skills 並設定 agent 治理能力。
  即使 MCP 已連線，仍然需要執行完整流程（pull skills + 設定 agent）。
  當使用者說「設定 ZenOS」「更新 ZenOS skills」「setup ZenOS」「/zenos-setup」
  或「我要開始用 ZenOS」「拉最新治理 skill」「更新治理能力」時使用。
version: 3.0.0
---

# /zenos-setup

⚠️ **不要自行判斷是否需要執行。必須讀取 SSOT 並按流程走。**

請先用 Read tool 讀取 `skills/workflows/setup.md` 的完整內容，然後嚴格按照該文件的流程執行。

即使 MCP 已經連線，仍然需要執行 Step 2（拉取最新 skills）和 Step 3（設定 agent 治理能力）。
