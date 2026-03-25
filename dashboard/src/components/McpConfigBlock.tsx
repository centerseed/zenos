"use client";

import { useState } from "react";

interface McpConfigBlockProps {
  apiKey: string;
}

const MCP_SERVER_URL = "https://zenos-mcp-165893875709.asia-east1.run.app/mcp";

type AgentType = "claude-code" | "claude-ai" | "other";

const agentTabs: { id: AgentType; label: string }[] = [
  { id: "claude-code", label: "Claude Code" },
  { id: "claude-ai", label: "Claude.ai" },
  { id: "other", label: "Other" },
];

function getConfig(agentType: AgentType, apiKey: string): string {
  if (agentType === "claude-code") {
    return JSON.stringify(
      {
        mcpServers: {
          zenos: {
            type: "http",
            url: `${MCP_SERVER_URL}?api_key=${apiKey}`,
          },
        },
      },
      null,
      2
    );
  }

  if (agentType === "claude-ai") {
    return `MCP Server URL: ${MCP_SERVER_URL}?api_key=${apiKey}\n\nClaude.ai currently has limited MCP support.\nPlease use Claude Code for the best experience.`;
  }

  return `MCP Server URL: ${MCP_SERVER_URL}\nAPI Key: ${apiKey}\n\nUse these values to configure your MCP-compatible agent.`;
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
        <label className="block text-sm font-medium text-[#FAFAFA] mb-2">
          Your API Key
        </label>
        <div className="flex items-center gap-2">
          <code className="flex-1 bg-[#1F1F23] px-4 py-2 rounded text-sm font-mono text-[#FAFAFA]">
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
        <label className="block text-sm font-medium text-[#FAFAFA] mb-2">
          Select your agent
        </label>
        <div className="flex border-b border-[#1F1F23]">
          {agentTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              aria-label={`Select ${tab.label} config`}
              className={`px-4 py-2 text-sm cursor-pointer ${
                activeTab === tab.id
                  ? "border-b-2 border-blue-500 text-blue-400 font-medium"
                  : "text-[#71717A] hover:text-white"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Config block */}
      <div className="relative">
        <pre className="bg-[#0A0A0B] text-[#FAFAFA] rounded-lg p-4 text-sm overflow-x-auto border border-[#1F1F23]">
          {config}
        </pre>
        <button
          onClick={handleCopy}
          aria-label="Copy MCP config"
          className="absolute top-3 right-3 bg-[#1F1F23] hover:bg-[#2A2A2E] text-white text-xs px-3 py-1.5 rounded cursor-pointer transition-colors"
        >
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>
    </div>
  );
}
