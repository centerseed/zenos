"use client";

import { useState } from "react";
import type { Blindspot, Entity } from "@/types";

interface BlindspotPanelProps {
  blindspots: Blindspot[];  // only status=open
  entities: Entity[];       // for resolving related entity names
}

export function BlindspotPanel({ blindspots, entities }: BlindspotPanelProps) {
  const [expanded, setExpanded] = useState(true);

  const entityMap = new Map(entities.map((e) => [e.id, e]));

  // Sort: red first, then yellow, then green
  const severityOrder: Record<string, number> = { red: 0, yellow: 1, green: 2 };
  const sorted = [...blindspots].sort(
    (a, b) => (severityOrder[a.severity] ?? 9) - (severityOrder[b.severity] ?? 9)
  );

  return (
    <div className="bg-[#111113] rounded-lg border border-[#1F1F23]">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 cursor-pointer"
      >
        <span className="text-sm font-semibold text-white">
          Blindspots ({blindspots.length})
        </span>
        <svg
          className={`w-4 h-4 text-[#71717A] transition-transform ${expanded ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3">
          {sorted.length === 0 ? (
            <p className="text-sm text-[#71717A]">No active blindspots</p>
          ) : (
            sorted.map((bs) => {
              const isRed = bs.severity === "red";
              const cardClasses = isRed
                ? "bg-red-900/30 border border-red-500/50"
                : "bg-yellow-900/30 border border-yellow-500/50";
              const badgeClasses = isRed
                ? "bg-red-500/20 text-red-400"
                : "bg-yellow-500/20 text-yellow-400";

              const relatedNames = bs.relatedEntityIds
                .map((id) => entityMap.get(id)?.name)
                .filter(Boolean);

              return (
                <div key={bs.id} className={`rounded-lg p-3 ${cardClasses}`}>
                  <div className="flex items-start gap-2">
                    <span
                      className={`inline-block px-2 py-0.5 rounded text-xs font-semibold uppercase shrink-0 ${badgeClasses}`}
                    >
                      {bs.severity}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-[#FAFAFA]/90">{bs.description}</p>
                      {relatedNames.length > 0 && (
                        <p className="text-xs text-[#FAFAFA]/50 mt-1">
                          Related: {relatedNames.join(", ")}
                        </p>
                      )}
                      {bs.suggestedAction && (
                        <p className="text-xs text-[#FAFAFA]/60 mt-1">
                          Suggested: {bs.suggestedAction}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
