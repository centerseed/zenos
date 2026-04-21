"use client";

import { useState } from "react";

interface McpConfigBlockProps {
  apiKey: string;
}

const MCP_SERVER_URL = "https://zenos-mcp-s5oifosv3a-de.a.run.app";
const STREAMABLE_HTTP_URL = `${MCP_SERVER_URL}/mcp`;
const SSE_URL = `${MCP_SERVER_URL}/sse`;

type AgentType = "claude-code" | "claude-ai" | "gemini";

const agentTabs: { id: AgentType; label: string }[] = [
  { id: "claude-code", label: "Claude Code" },
  { id: "claude-ai", label: "Claude.ai" },
  { id: "gemini", label: "Gemini" },
];

function getConfig(agentType: AgentType, apiKey: string): string {
  if (agentType === "claude-code") {
    return JSON.stringify(
      {
        mcpServers: {
          zenos: {
            type: "http",
            url: STREAMABLE_HTTP_URL,
            headers: {
              Authorization: `Bearer ${apiKey}`,
            },
          },
        },
      },
      null,
      2
    );
  }

  if (agentType === "claude-ai") {
    return `${STREAMABLE_HTTP_URL}?api_key=${apiKey}`;
  }

  return `MCP Server URL: ${SSE_URL}\nAuthorization header: Bearer ${apiKey}\n\nUse this SSE endpoint for Gemini or any client that requires GET-based MCP streaming.`;
}

export function McpConfigBlock({ apiKey }: McpConfigBlockProps) {
  const [activeTab, setActiveTab] = useState<AgentType>("claude-code");
  const [copied, setCopied] = useState(false);
  const [showKey, setShowKey] = useState(false);

  const config = getConfig(activeTab, apiKey);
  const maskedKey = `${apiKey.slice(0, 8)}${"•".repeat(24)}`;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(config);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      {/* API Key display */}
      <div>
        <label className="block text-sm font-medium text-foreground mb-2">
          Your API Key
        </label>
        <div className="flex items-center gap-2">
          <code className="flex-1 bg-secondary px-4 py-2 rounded text-sm font-mono text-foreground">
            {showKey ? apiKey : maskedKey}
          </code>
          <button
            onClick={() => setShowKey(!showKey)}
            aria-label={showKey ? "Hide API key" : "Show API key"}
            className="text-sm text-blue-400 hover:underline cursor-pointer whitespace-nowrap"
          >
            {showKey ? "Hide" : "Show"}
          </button>
        </div>
      </div>

      {/* Agent type tabs */}
      <div>
        <label className="block text-sm font-medium text-foreground mb-2">
          Select your agent
        </label>
        <div className="flex border-b border-border">
          {agentTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              aria-label={`Select ${tab.label} config`}
              className={`px-4 py-2 text-sm cursor-pointer ${
                activeTab === tab.id
                  ? "border-b-2 border-blue-500 text-blue-400 font-medium"
                  : "text-muted-foreground hover:text-white"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Config block */}
      <div className="relative">
        <pre className="bg-background text-foreground rounded-lg p-4 text-sm overflow-x-auto border border-border">
          {config}
        </pre>
        <button
          onClick={handleCopy}
          aria-label="Copy MCP config"
          className="absolute top-3 right-3 bg-secondary hover:bg-muted text-white text-xs px-3 py-1.5 rounded cursor-pointer transition-colors"
        >
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>

      {activeTab === "claude-ai" && (
        <p className="text-sm text-muted-foreground">
          Paste this URL into Claude.ai → Connectors → Add custom connector
        </p>
      )}
    </div>
  );
}
