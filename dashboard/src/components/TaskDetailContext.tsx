"use client";

import React from "react";
import { useInk } from "@/lib/zen-ink/tokens";

interface TaskDetailContextProps {
  contextualAssets?: React.ReactNode;
  richerFields?: React.ReactNode;
}

export function TaskDetailContext({ contextualAssets, richerFields }: TaskDetailContextProps) {
  const t = useInk("light");
  const { c } = t;

  return (
    <div data-testid="task-detail-context" style={{ display: "flex", flexDirection: "column", gap: 28 }}>
      {contextualAssets && (
        <section>
          <SectionLabel label="Contextual Assets" color={c.vermillion} />
          {contextualAssets}
        </section>
      )}

      {richerFields && (
        <section>
          <SectionLabel label="Rich Task Context" color={c.vermillion} />
          {richerFields}
        </section>
      )}
    </div>
  );
}

function SectionLabel({ label, color }: { label: string; color: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
      <div style={{ width: 3, height: 16, borderRadius: 999, background: color, flexShrink: 0 }} />
      <span
        style={{
          fontFamily: "var(--font-mono, ui-monospace, monospace)",
          fontSize: 10,
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: "0.16em",
        }}
      >
        {label}
      </span>
    </div>
  );
}
