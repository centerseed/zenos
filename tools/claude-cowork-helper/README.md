# Claude Cowork Local Helper

本機 bridge，讓 Web 可以呼叫本機 `claude` CLI 並接收 SSE 串流。

## Quick Start

1. 先在 terminal 完成 Claude 登入：
   - `claude auth login`
2. 啟動 helper：
   - `cd tools/claude-cowork-helper`
   - `npm run start`
3. 在 Dashboard `/marketing` 的 AI 討論面板填入：
   - Helper URL：`http://127.0.0.1:4317`

## API

- `GET /health`
- `POST /v1/chat/start`
- `POST /v1/chat/continue`
- `POST /v1/chat/cancel`

## Env Vars

- `PORT`：預設 `4317`
- `ALLOWED_ORIGINS`：可呼叫 helper 的網域（逗號分隔）
- `LOCAL_HELPER_TOKEN`：本機配對 token（若有設定，請求需帶 `X-Local-Helper-Token`）
- `ALLOWED_CWDS`：允許工作目錄白名單（逗號分隔）
- `DEFAULT_CWD`：未指定 cwd 時的預設工作目錄

## Security Notes

- 只監聽 `127.0.0.1`
- 可限制 `Origin` + token
- 清除 `ANTHROPIC_API_KEY`，優先用本機訂閱登入
