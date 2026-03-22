"use client";

import { useAuth } from "@/lib/auth";
import { AuthGuard } from "@/components/AuthGuard";
import { McpConfigBlock } from "@/components/McpConfigBlock";
import Link from "next/link";

function SetupPage() {
  const { partner, signOut } = useAuth();

  if (!partner) return null;

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-3xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="text-xl font-bold text-gray-900 hover:text-gray-600">
            ZenOS
          </Link>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500">
              {partner.displayName}
            </span>
            <button
              onClick={signOut}
              className="text-sm text-gray-400 hover:text-gray-600 cursor-pointer"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          Set up your AI Agent
        </h2>
        <p className="text-gray-500 mb-8">
          Connect your Claude Code to ZenOS so your AI agent has full context
          about your projects.
        </p>

        {/* MCP Config */}
        <div className="bg-white rounded-lg border border-gray-200 p-6 mb-8">
          <McpConfigBlock apiKey={partner.apiKey} />
        </div>

        {/* Steps */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="font-semibold text-gray-900 mb-4">
            Setup steps
          </h3>
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
                    className="text-blue-600 hover:underline"
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
                  <code className="bg-gray-100 px-1.5 py-0.5 rounded text-sm">
                    .claude/mcp.json
                  </code>
                </>
              }
            />
            <Step
              number={3}
              title="Paste the config"
              description="Copy the config JSON above and paste it into your mcp.json file."
            />
            <Step
              number={4}
              title="Restart Claude Code"
              description="Close and reopen Claude Code for the MCP settings to take effect."
            />
            <Step
              number={5}
              title="Verify"
              description={
                <>
                  Type{" "}
                  <code className="bg-gray-100 px-1.5 py-0.5 rounded text-sm">
                    list all products
                  </code>{" "}
                  in Claude Code. If you see your project, you&apos;re all set!
                </>
              }
            />
          </ol>
        </div>

        <div className="mt-8 text-center">
          <Link
            href="/"
            className="text-sm text-blue-600 hover:underline"
          >
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
      <div className="flex-shrink-0 w-7 h-7 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-sm font-medium">
        {number}
      </div>
      <div>
        <h4 className="font-medium text-gray-900">{title}</h4>
        <p className="text-sm text-gray-500 mt-1">{description}</p>
      </div>
    </li>
  );
}

export default function Page() {
  return (
    <AuthGuard>
      <SetupPage />
    </AuthGuard>
  );
}
