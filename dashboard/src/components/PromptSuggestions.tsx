"use client";

import { useState } from "react";

interface PromptSuggestionsProps {
  projectName: string;
}

export function PromptSuggestions({ projectName }: PromptSuggestionsProps) {
  const prompts = [
    `Help me write a social media post about ${projectName}`,
    `What are the core features of ${projectName}?`,
    `What problems does ${projectName} currently have?`,
    `Summarize ${projectName}'s product positioning in one paragraph`,
    `What should I know before writing marketing copy for ${projectName}?`,
  ];

  return (
    <div>
      <h3 className="text-sm font-medium text-dim uppercase tracking-wide mb-3">
        Try these prompts
      </h3>
      <div className="grid gap-2">
        {prompts.map((prompt, i) => (
          <CopyablePrompt key={i} text={prompt} />
        ))}
      </div>
    </div>
  );
}

function CopyablePrompt({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      className="flex items-center justify-between w-full text-left bg-blue-900/20 hover:bg-blue-900/30 border border-blue-900/50 rounded-lg px-4 py-3 text-sm text-blue-300 transition-colors cursor-pointer group"
    >
      <span>&ldquo;{text}&rdquo;</span>
      <span className="text-xs text-blue-500 group-hover:text-blue-300 ml-3 whitespace-nowrap">
        {copied ? "Copied!" : "Copy"}
      </span>
    </button>
  );
}
