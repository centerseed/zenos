"use client";

import type { Blindspot } from "@/types";

interface BlindspotAlertProps {
  blindspots: Blindspot[];
}

export function BlindspotAlert({ blindspots }: BlindspotAlertProps) {
  const critical = blindspots.filter((b) => b.severity === "red");
  const warnings = blindspots.filter((b) => b.severity === "yellow");

  if (critical.length === 0 && warnings.length === 0) return null;

  return (
    <div className="space-y-3">
      {critical.map((b) => (
        <div
          key={b.id}
          className="bg-red-900/30 border border-red-800 rounded-lg p-4"
        >
          <div className="flex items-start gap-2">
            <span className="text-red-500 mt-0.5">●</span>
            <div>
              <p className="text-sm font-medium text-red-400">
                {b.description}
              </p>
              <p className="text-xs text-red-500 mt-1">{b.suggestedAction}</p>
            </div>
          </div>
        </div>
      ))}
      {warnings.map((b) => (
        <div
          key={b.id}
          className="bg-yellow-900/30 border border-yellow-800 rounded-lg p-4"
        >
          <div className="flex items-start gap-2">
            <span className="text-yellow-500 mt-0.5">●</span>
            <div>
              <p className="text-sm font-medium text-yellow-400">
                {b.description}
              </p>
              <p className="text-xs text-yellow-500 mt-1">
                {b.suggestedAction}
              </p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
