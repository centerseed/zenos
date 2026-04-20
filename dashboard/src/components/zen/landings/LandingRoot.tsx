// ZenOS · Landing root — client wrapper that reads ?variant query param
// This is the "use client" boundary that lets page.tsx remain a server component
// (needed so page.tsx can export metadata).
"use client";

import React, { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useInk } from "@/lib/zen-ink/tokens";
import { LandingA } from "./LandingA";
import { LandingB } from "./LandingB";
import { LandingC } from "./LandingC";

type Variant = "A" | "B" | "C";

function LandingInner() {
  const searchParams = useSearchParams();
  const variantParam = searchParams.get("variant")?.toUpperCase() as Variant | null;
  const variant: Variant =
    variantParam === "A" || variantParam === "C" ? variantParam : "B";

  // All landing pages use light mode (Zen Ink default)
  const t = useInk("light");

  if (variant === "A") return <LandingA t={t} />;
  if (variant === "C") return <LandingC t={t} />;
  return <LandingB t={t} />;
}

export function LandingRoot() {
  return (
    <Suspense
      fallback={
        <div style={{ background: "#F4EFE4", minHeight: "100vh" }} />
      }
    >
      <LandingInner />
    </Suspense>
  );
}
