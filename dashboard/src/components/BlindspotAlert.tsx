"use client";

import type { Blindspot } from "@/types";
import { useInk } from "@/lib/zen-ink/tokens";
import { Panel } from "@/components/zen/Panel";

interface BlindspotAlertProps {
  blindspots: Blindspot[];
}

export function BlindspotAlert({ blindspots }: BlindspotAlertProps) {
  const t = useInk("light");
  const critical = blindspots.filter((b) => b.severity === "red");
  const warnings = blindspots.filter((b) => b.severity === "yellow");

  if (critical.length === 0 && warnings.length === 0) return null;

  return (
    <div className="space-y-3">
      {critical.map((b) => (
        <Panel
          t={t}
          key={b.id}
          style={{ background: "rgba(182, 58, 44, 0.08)", borderColor: t.c.vermLine }}
        >
          <div className="pt-4">
            <div className="flex items-start gap-2">
              <span className="text-red-500 mt-0.5" aria-hidden>
                ●
              </span>
              <span className="sr-only">Critical</span>
              <div>
                <p className="text-sm font-medium text-red-400">
                  {b.description}
                </p>
                <p className="text-xs text-red-500 mt-1">{b.suggestedAction}</p>
              </div>
            </div>
          </div>
        </Panel>
      ))}
      {warnings.map((b) => (
        <Panel
          t={t}
          key={b.id}
          style={{ background: "rgba(180, 132, 50, 0.08)", borderColor: t.c.ocher }}
        >
          <div className="pt-4">
            <div className="flex items-start gap-2">
              <span className="text-yellow-500 mt-0.5" aria-hidden>
                ●
              </span>
              <span className="sr-only">Warning</span>
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
        </Panel>
      ))}
    </div>
  );
}
