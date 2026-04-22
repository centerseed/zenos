import { describe, expect, it } from "vitest";

import {
  AGENT_PLATFORMS,
  buildExternalAgentPrompt,
  buildHelperInstallAndStartCommand,
  buildHelperInstallCommand,
  canCopyAgentConfig,
  getMcpConfig,
  getMcpUrl,
  maskApiKey,
} from "../agent-config";

describe("agent-config", () => {
  it("builds MCP URLs with the real api key", () => {
    expect(getMcpUrl(AGENT_PLATFORMS[0], "demo-user-value")).toContain("api_key=demo-user-value");
    expect(getMcpUrl(AGENT_PLATFORMS.find((platform) => platform.useSSE)!, "demo-user-value")).toContain(
      "/sse?api_key=demo-user-value",
    );
  });

  it("builds MCP config without placeholders", () => {
    const json = getMcpConfig(AGENT_PLATFORMS[0], "demo-user-value");
    expect(json).toContain('"type": "http"');
    expect(json).toContain("demo-user-value");
    expect(json).not.toContain("<your_api_key>");
  });

  it("builds helper commands with api key, token, cwd, and origin", () => {
    const command = buildHelperInstallAndStartCommand({
      apiKey: "demo-user-value", // pragma: allowlist secret
      helperToken: "demo-helper-value", // pragma: allowlist secret
      cwd: "/Users/demo/workspace",
      allowedOrigins: "https://zenos-naruvia.web.app",
    });
    expect(command).toContain('ZENOS_API_KEY="demo-user-value"'); // pragma: allowlist secret
    expect(command).toContain('LOCAL_HELPER_TOKEN="demo-helper-value"'); // pragma: allowlist secret
    expect(command).toContain('SAFE_WORKSPACE="/Users/demo/workspace"');
    expect(command).toContain('ALLOWED_ORIGINS="https://zenos-naruvia.web.app"');
    expect(command).not.toContain("<your_api_key>");
    expect(command).not.toContain("<your_token>");
  });

  it("builds external agent prompts with the real api key", () => {
    const prompt = buildExternalAgentPrompt(AGENT_PLATFORMS[0], "demo-user-value");
    expect(prompt).toContain("Server URL:");
    expect(prompt).toContain("demo-user-value");
  });

  it("masks api key and blocks copy when empty", () => {
    expect(maskApiKey("demo-user-value")).toBe("demo-use••••••••");
    expect(maskApiKey("")).toBe("尚未取得");
    expect(canCopyAgentConfig("")).toBe(false);
    expect(canCopyAgentConfig("demo-user-value")).toBe(true);
  });

  it("builds the helper installer command", () => {
    expect(buildHelperInstallCommand()).toContain("install-claude-code-helper-macos.sh");
  });
});
