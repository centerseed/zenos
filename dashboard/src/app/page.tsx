// ZenOS · Landing page — Zen Ink design language (server entry point)
// Renders Variant B by default; supports ?variant=A or ?variant=C for alternatives.
// AC-ZEN-01: Landing B default
// AC-ZEN-02: variant query param
// AC-ZEN-14: brand mark shows "ZenOS", 禪作 is visual-only watermark in A

import type { Metadata } from "next";
import { LandingRoot } from "@/components/zen/landings/LandingRoot";

export const metadata: Metadata = {
  title: "ZenOS · 團隊的知識，應該是共同的資產",
  description:
    "ZenOS 把散落在訊息、文件、會議中的資料，收束成一方結構化的畫紙。",
};

export default function HomePage() {
  return <LandingRoot />;
}
