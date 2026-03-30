# ZenOS Setup 工作流程

## 設定步驟
1. 呼叫 `mcp_zenos_setup()` 檢查當前平台支援度。
2. 根據推薦平台呼叫 `mcp_zenos_setup(platform='...')`。
3. 如果 `claude_code` 等 CLI 平台失敗，嘗試使用 `governance_guide` 獲取規則內容並手動寫入 `skills/` 目錄。
4. 驗證 `skills/governance/` 目錄下的文件是否完整。
5. 更新 `AGENTS.md` 或 `PROJECT_INSTRUCTIONS` 以包含 ZenOS 治理邏輯。

## 常見問題
- 如果 MCP server 回傳檔案不存在錯誤，請手動從 GitHub 或 `governance_guide` 同步內容。
- 確保 API Key 與 Project ID 正確配置於 MCP 設定中。
