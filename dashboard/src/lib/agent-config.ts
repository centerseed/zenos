const MCP_BASE = "https://zenos-mcp-s5oifosv3a-de.a.run.app";
const HELPER_INSTALLER_URL =
  "https://zenos-naruvia.web.app/installers/install-claude-code-helper-macos.sh";
const DEFAULT_HELPER_WORKSPACE = "$HOME/.zenos/claude-code-helper/workspace";
const DEFAULT_HELPER_ORIGIN = "https://zenos-naruvia.web.app";

export type AgentPlatformId =
  | "claude-code"
  | "claude-cowork"
  | "chatgpt"
  | "codex"
  | "gemini-cli"
  | "antigravity";

export interface AgentPlatform {
  id: AgentPlatformId;
  name: string;
  useSSE: boolean;
}

export const AGENT_PLATFORMS: AgentPlatform[] = [
  { id: "claude-code", name: "Claude Code", useSSE: false },
  { id: "claude-cowork", name: "Claude.ai / Cowork", useSSE: false },
  { id: "chatgpt", name: "ChatGPT", useSSE: false },
  { id: "codex", name: "Codex", useSSE: false },
  { id: "gemini-cli", name: "Gemini CLI", useSSE: true },
  { id: "antigravity", name: "Antigravity", useSSE: true },
];

export function getMcpUrl(platform: Pick<AgentPlatform, "useSSE">, apiKey: string): string {
  const endpoint = platform.useSSE ? "sse" : "mcp";
  return `${MCP_BASE}/${endpoint}?api_key=${apiKey}`;
}

export function getMcpConfig(platform: AgentPlatform, apiKey: string): string {
  return JSON.stringify(
    {
      mcpServers: {
        zenos: {
          type: platform.useSSE ? "sse" : "http",
          url: getMcpUrl(platform, apiKey),
        },
      },
    },
    null,
    2,
  );
}

export function maskApiKey(apiKey: string): string {
  return apiKey ? `${apiKey.slice(0, 8)}••••••••` : "尚未取得";
}

export function canCopyAgentConfig(apiKey: string): boolean {
  return apiKey.trim().length > 0;
}

export function buildHelperInstallCommand(): string {
  return `curl -fsSL "${HELPER_INSTALLER_URL}" -o /tmp/install-claude-code-helper-macos.sh && bash /tmp/install-claude-code-helper-macos.sh`;
}

export function buildHelperInstallAndStartCommand(params: {
  apiKey: string;
  helperToken: string;
  cwd?: string;
  allowedOrigins?: string;
}): string {
  const cwd = params.cwd?.trim() || DEFAULT_HELPER_WORKSPACE;
  const allowedOrigins = params.allowedOrigins?.trim() || DEFAULT_HELPER_ORIGIN;
  return `curl -fsSL "${HELPER_INSTALLER_URL}" -o /tmp/install-claude-code-helper-macos.sh && \\
LOCAL_HELPER_TOKEN="${params.helperToken.trim()}" \\
ZENOS_API_KEY="${params.apiKey}" \\
SAFE_WORKSPACE="${cwd}" \\
ALLOWED_ORIGINS="${allowedOrigins}" \\
AUTO_START=1 \\
bash /tmp/install-claude-code-helper-macos.sh`;
}

export function buildExternalAgentPrompt(platform: AgentPlatform, apiKey: string): string {
  const url = getMcpUrl(platform, apiKey);
  const protocol = platform.useSSE ? "SSE" : "Streamable HTTP";
  return `我要連接 ZenOS MCP server，請完成以下設定：

1. MCP 連線設定
   Server URL: ${url}
   這是 ${protocol} 協議的 MCP server。
   請根據你的平台，把這個 MCP server 加入設定。

2. 安裝治理能力
   連線成功後，請先判斷你目前是 ${platform.name}，再呼叫對應的 setup(platform=...)。
   接著請主動問我要安裝在當前目錄還是家目錄；若我沒特別指定，預設推薦當前目錄。
   如果是首次安裝，先把 zenos-setup 裝進來。

3. 完成正式安裝
   zenos-setup 裝好後，請執行 /zenos-setup 完成正式安裝或後續更新。

4. 安裝完成後說明
   請用很短的方式告訴我 /zenos-setup、/zenos-capture、/zenos-sync、/zenos-governance 分別什麼時候用。`;
}
