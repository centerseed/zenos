"use client";

import React, { useState } from "react";
import { useAuth } from "@/lib/auth";
import { AuthGuard } from "@/components/AuthGuard";
import { AppNav } from "@/components/AppNav";
import { McpConfigBlock } from "@/components/McpConfigBlock";
import Link from "next/link";

type SetupTab = "claude-code" | "claude-ai";

const SKILL_URLS: { name: string; url: string }[] = [
  {
    name: "zenos-capture",
    url: "https://raw.githubusercontent.com/centerseed/zenos/main/.claude/skills/zenos-capture/SKILL.md",
  },
  {
    name: "zenos-sync",
    url: "https://raw.githubusercontent.com/centerseed/zenos/main/.claude/skills/zenos-sync/SKILL.md",
  },
  {
    name: "zenos-governance",
    url: "https://raw.githubusercontent.com/centerseed/zenos/main/.claude/skills/zenos-governance/SKILL.md",
  },
];

const MCP_SERVER_URL = "https://zenos-mcp-165893875709.asia-east1.run.app";
const STREAMABLE_HTTP_URL = `${MCP_SERVER_URL}/mcp`;

function SetupPage() {
  const { partner } = useAuth();
  const [activeSetupTab, setActiveSetupTab] = useState<SetupTab>("claude-code");

  if (!partner) return null;

  return (
    <div className="min-h-screen">
      <AppNav />

      <main id="main-content" className="max-w-3xl mx-auto px-6 py-8">
        <h2 className="text-2xl font-bold text-foreground mb-2">
          Set up your AI Agent
        </h2>
        <p className="text-muted-foreground mb-8">
          Connect your AI agent to ZenOS so it has full context about your
          projects.
        </p>

        {/* MCP Config */}
        <div className="bg-card rounded-lg border border-border p-6 mb-8">
          <McpConfigBlock apiKey={partner.apiKey} />
        </div>

        {/* Steps */}
        <div className="bg-card rounded-lg border border-border p-6">
          <h3 className="font-semibold text-foreground mb-4">Setup steps</h3>

          {/* Tab switcher */}
          <div className="flex border-b border-border mb-6">
            <button
              onClick={() => setActiveSetupTab("claude-code")}
              className={`px-4 py-2 text-sm cursor-pointer ${
                activeSetupTab === "claude-code"
                  ? "border-b-2 border-blue-500 text-blue-400 font-medium"
                  : "text-muted-foreground hover:text-white"
              }`}
            >
              Claude Code
            </button>
            <button
              onClick={() => setActiveSetupTab("claude-ai")}
              className={`px-4 py-2 text-sm cursor-pointer ${
                activeSetupTab === "claude-ai"
                  ? "border-b-2 border-blue-500 text-blue-400 font-medium"
                  : "text-muted-foreground hover:text-white"
              }`}
            >
              Claude.ai
            </button>
          </div>

          {activeSetupTab === "claude-code" && (
            <ol className="space-y-4">
              <Step
                number={1}
                title="Install Claude Code"
                description={
                  <>
                    If you haven&apos;t already, install Claude Code from{" "}
                    <a
                      href="https://docs.anthropic.com/en/docs/claude-code/overview"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-400 hover:underline"
                    >
                      Anthropic&apos;s docs
                    </a>
                    .
                  </>
                }
              />
              <Step
                number={2}
                title="Open your MCP settings"
                description={
                  <>
                    In your project directory, create or edit{" "}
                    <code className="bg-secondary px-1.5 py-0.5 rounded text-sm text-foreground">
                      .claude/mcp.json
                    </code>
                  </>
                }
              />
              <Step
                number={3}
                title="Paste the config"
                description="Copy the config JSON above and paste it into your mcp.json file. Use the Gemini tab if your client expects an SSE endpoint."
              />
              <Step
                number={4}
                title="Install ZenOS Skills"
                description={
                  <>
                    Copy the prompt below and paste it into Claude Code. It
                    will automatically download and install the ZenOS skills.
                  </>
                }
              />

              {/* Skill install prompt */}
              <div className="ml-11 mb-4">
                <SkillInstallBlock />
              </div>

              <Step
                number={5}
                title="Restart Claude Code"
                description="Close and reopen Claude Code for the MCP settings and skills to take effect."
              />
              <Step
                number={6}
                title="Verify"
                description={
                  <>
                    Type{" "}
                    <code className="bg-secondary px-1.5 py-0.5 rounded text-sm text-foreground">
                      list all products
                    </code>{" "}
                    in Claude Code. If you see your project, you&apos;re all
                    set!
                  </>
                }
              />
            </ol>
          )}

          {activeSetupTab === "claude-ai" && (
            <ol className="space-y-4">
              <Step
                number={1}
                title="Connect MCP"
                description={
                  <div className="space-y-2">
                    <p>
                      In Claude.ai, click the &quot;+&quot; button →
                      Connectors → Add custom connector. Set the name to{" "}
                      <code className="bg-secondary px-1.5 py-0.5 rounded text-sm text-foreground">
                        zenos
                      </code>{" "}
                      and paste the URL below.
                    </p>
                    <div className="flex items-center gap-2 mt-2">
                      <code className="flex-1 bg-background border border-border rounded px-3 py-2 text-sm font-mono text-foreground break-all">
                        {`${STREAMABLE_HTTP_URL}?api_key=${partner.apiKey}`}
                      </code>
                    </div>
                  </div>
                }
              />
              <Step
                number={2}
                title="Add Skills"
                description={
                  <div className="space-y-2">
                    <p>
                      In Claude.ai, click the &quot;+&quot; button → Skills →
                      Upload a skill. Download each file below and upload it
                      one by one.
                    </p>
                    <ul className="mt-2 space-y-1">
                      {SKILL_URLS.map((skill) => (
                        <li key={skill.name}>
                          <a
                            href={skill.url}
                            download
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-400 hover:underline text-sm"
                          >
                            Download {skill.name}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                }
              />
              <Step
                number={3}
                title="Verify"
                description={
                  <>
                    In a Claude.ai conversation, try asking{" "}
                    <code className="bg-secondary px-1.5 py-0.5 rounded text-sm text-foreground">
                      list my projects in ZenOS
                    </code>
                    . If you see your projects, you&apos;re all set!
                  </>
                }
              />
            </ol>
          )}
        </div>

        <div className="mt-8 text-center">
          <Link href="/" className="text-sm text-blue-400 hover:underline">
            Back to projects
          </Link>
        </div>
      </main>
    </div>
  );
}

function Step({
  number,
  title,
  description,
}: {
  number: number;
  title: string;
  description: React.ReactNode;
}) {
  return (
    <li className="flex gap-4">
      <div className="flex-shrink-0 w-7 h-7 bg-blue-900/50 text-blue-400 rounded-full flex items-center justify-center text-sm font-medium">
        {number}
      </div>
      <div>
        <h4 className="font-medium text-white">{title}</h4>
        <p className="text-sm text-muted-foreground mt-1">{description}</p>
      </div>
    </li>
  );
}

const SKILL_INSTALL_PROMPT = `Download ZenOS skills from GitHub and install them into this project.

1. Fetch all folders starting with "zenos-" from https://github.com/centerseed/zenos/tree/main/.claude/skills/
2. For each folder (zenos-setup, zenos-capture, zenos-sync), download the SKILL.md file
3. Save them to .claude/skills/{folder-name}/SKILL.md in this project
4. Verify by listing .claude/skills/zenos-*/SKILL.md`;

function SkillInstallBlock() {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(SKILL_INSTALL_PROMPT);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-background rounded-lg border border-border overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-border">
        <span className="text-xs text-muted-foreground">Paste this into Claude Code</span>
        <button
          onClick={handleCopy}
          aria-label="Copy skill install prompt"
          className="text-xs text-blue-400 hover:text-blue-300 cursor-pointer"
        >
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>
      <pre className="px-4 py-3 text-sm text-foreground whitespace-pre-wrap font-mono leading-relaxed">
        {SKILL_INSTALL_PROMPT}
      </pre>
    </div>
  );
}

export default function Page() {
  return (
    <AuthGuard>
      <SetupPage />
    </AuthGuard>
  );
}
