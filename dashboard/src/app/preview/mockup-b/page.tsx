"use client";

import { useState } from "react";
import Link from "next/link";
import {
  REAL_ENTITIES,
  REAL_BLINDSPOTS,
  getRealStats,
  getModulesForProduct,
  getBlindspotsForEntity,
  getOrphanBlindspots,
} from "../realData";
import type { RealEntity, RealBlindspot } from "../realData";

// ─── Mockup B: Card Panorama with REAL Firestore data ───

function HealthDot({ health }: { health: "healthy" | "warning" | "critical" }) {
  const c = { healthy: "bg-emerald-400", warning: "bg-amber-400", critical: "bg-red-400 animate-pulse" };
  return <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${c[health]}`} />;
}

function deriveModuleHealth(mod: RealEntity, blindspots: RealBlindspot[]): "healthy" | "warning" | "critical" {
  const related = blindspots.filter(b => b.relatedEntityIds.includes(mod.id));
  if (related.some(b => b.severity === "red")) return "critical";
  if (!mod.confirmedByUser || related.some(b => b.severity === "yellow")) return "warning";
  return "healthy";
}

function deriveProductHealth(modules: RealEntity[], blindspots: RealBlindspot[]): "healthy" | "warning" | "critical" {
  const healths = modules.map(m => deriveModuleHealth(m, blindspots));
  if (healths.includes("critical")) return "critical";
  if (healths.includes("warning")) return "warning";
  return "healthy";
}

function BlindspotCard({ bs }: { bs: RealBlindspot }) {
  const isRed = bs.severity === "red";
  // Find related entity names
  const relatedNames = bs.relatedEntityIds
    .map(id => REAL_ENTITIES.find(e => e.id === id)?.name)
    .filter(Boolean);

  return (
    <div className={`flex items-start gap-2.5 px-3 py-2.5 rounded-lg ${
      isRed ? "bg-red-500/8" : "bg-amber-500/8"
    }`}>
      <div className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 mt-0.5 text-[11px] font-bold ${
        isRed ? "bg-red-500/20 text-red-400" : "bg-amber-500/20 text-amber-400"
      }`}>!</div>
      <div className="flex-1 min-w-0">
        <p className={`text-[13px] leading-snug ${isRed ? "text-red-300" : "text-amber-300"}`}>
          {bs.description}
        </p>
        <div className="flex items-center gap-3 mt-1.5 text-[11px]">
          {relatedNames.length > 0 && (
            <span className="text-[#FAFAFA]/30">影響 <span className="text-[#FAFAFA]/50">{relatedNames.join(", ")}</span></span>
          )}
          <span className="text-[#FAFAFA]/30">→ {bs.suggestedAction}</span>
        </div>
      </div>
    </div>
  );
}

function ModuleRow({ mod, health }: { mod: RealEntity; health: "healthy" | "warning" | "critical" }) {
  const barColors = { healthy: "bg-emerald-400", warning: "bg-amber-400", critical: "bg-red-400" };
  return (
    <div className="flex items-center gap-2.5 py-1">
      <div className={`w-1 h-5 rounded-full shrink-0 ${barColors[health]}`} />
      <span className="text-sm text-[#FAFAFA]/80 flex-1 truncate">{mod.name}</span>
      {!mod.confirmedByUser && (
        <span className="text-[10px] text-orange-400/60 bg-orange-500/10 px-1.5 py-0.5 rounded shrink-0">草稿</span>
      )}
    </div>
  );
}

function ProductCard({ product }: { product: RealEntity }) {
  const [showBlindspots, setShowBlindspots] = useState(true);
  const modules = getModulesForProduct(product.id);
  const productBlindspots = getBlindspotsForEntity(product.id);
  // Also collect blindspots for child modules
  const allBlindspots = [
    ...productBlindspots,
    ...modules.flatMap(m => getBlindspotsForEntity(m.id)),
  ];
  // Deduplicate
  const seen = new Set<string>();
  const dedupedBlindspots = allBlindspots.filter(b => {
    if (seen.has(b.id)) return false;
    seen.add(b.id);
    return true;
  });

  const health = deriveProductHealth(modules, REAL_BLINDSPOTS);
  const confirmedModules = modules.filter(m => m.confirmedByUser).length;
  const totalModules = modules.length;

  const healthColors = {
    healthy: "border-emerald-500/40 bg-emerald-500/8",
    warning: "border-amber-500/40 bg-amber-500/8",
    critical: "border-red-500/40 bg-red-500/8",
  };
  const healthIcons = { healthy: "✓", warning: "!", critical: "✗" };
  const healthTextColors = { healthy: "text-emerald-400", warning: "text-amber-400", critical: "text-red-400" };

  return (
    <div className="rounded-2xl border border-[#27272A] bg-[#111113] overflow-hidden hover:border-[#3F3F46] transition-colors">
      {/* Header */}
      <div className="px-5 pt-5 pb-4 flex items-start gap-4">
        <div className={`w-11 h-11 rounded-full border-2 flex items-center justify-center shrink-0 ${healthColors[health]}`}>
          <span className={`text-base ${healthTextColors[health]}`}>{healthIcons[health]}</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-bold text-[#FAFAFA]">{product.name}</h2>
            {dedupedBlindspots.filter(b => b.severity === "red").length > 0 && (
              <span className="text-[11px] text-red-400 bg-red-500/15 px-2 py-0.5 rounded-full font-medium">
                {dedupedBlindspots.filter(b => b.severity === "red").length} red
              </span>
            )}
          </div>
          <p className="text-sm text-[#FAFAFA]/45 mt-0.5 line-clamp-2">{product.summary}</p>
          <div className="flex items-center gap-3 mt-2 text-xs text-[#FAFAFA]/30">
            <span>{totalModules} 模組</span>
            <span>·</span>
            <span className={confirmedModules < totalModules ? "text-amber-400/60" : "text-emerald-400/60"}>
              {confirmedModules}/{totalModules} 已確認
            </span>
          </div>
        </div>
      </div>

      {/* Modules */}
      {modules.length > 0 && (
        <div className="px-5 pb-3">
          <div className="flex items-center gap-3 mb-2">
            <h3 className="text-[10px] uppercase tracking-wider text-[#FAFAFA]/25 font-semibold">模組</h3>
            <div className="flex-1 h-px bg-[#27272A]" />
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
            {modules.map(mod => (
              <ModuleRow
                key={mod.id}
                mod={mod}
                health={deriveModuleHealth(mod, REAL_BLINDSPOTS)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Blindspots */}
      {dedupedBlindspots.length > 0 && (
        <div className="border-t border-[#27272A]">
          <button
            onClick={() => setShowBlindspots(!showBlindspots)}
            className="w-full flex items-center justify-between px-5 py-2.5 hover:bg-[#18181B]/50 transition-colors cursor-pointer"
          >
            <h3 className="text-[10px] uppercase tracking-wider text-[#FAFAFA]/25 font-semibold">
              盲點 ({dedupedBlindspots.length})
            </h3>
            <svg
              className={`w-3.5 h-3.5 text-[#FAFAFA]/20 transition-transform ${showBlindspots ? "rotate-180" : ""}`}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {showBlindspots && (
            <div className="px-5 pb-4 space-y-2">
              {dedupedBlindspots
                .sort((a, b) => (a.severity === "red" ? 0 : 1) - (b.severity === "red" ? 0 : 1))
                .map(bs => <BlindspotCard key={bs.id} bs={bs} />)
              }
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function MockupBReal() {
  const stats = getRealStats();
  const products = REAL_ENTITIES.filter(e => e.type === "product");
  const orphanBlindspots = getOrphanBlindspots();

  return (
    <div className="min-h-screen bg-[#09090B]">
      {/* Header */}
      <header className="border-b border-[#1F1F23]">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <h1 className="text-xl font-bold text-white tracking-tight">ZenOS</h1>
            <nav className="flex items-center gap-1 text-sm">
              <span className="px-3 py-1.5 rounded-md bg-white/10 text-white font-medium">全景圖</span>
              <Link href="/tasks" className="px-3 py-1.5 rounded-md text-[#71717A] hover:text-white hover:bg-white/5 transition-colors">任務</Link>
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/preview" className="text-xs text-[#71717A] hover:text-white">← 回 Preview</Link>
            <span className="text-sm text-[#71717A]">Barry Wu</span>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Company header */}
        <div className="flex items-end justify-between">
          <div>
            <h2 className="text-3xl font-bold text-[#FAFAFA] tracking-tight">Naruvia</h2>
            <p className="text-[#FAFAFA]/35 mt-1">
              {stats.totalEntities} 個知識節點 · {stats.confirmedRate}% 已確認 · 最後更新今天
            </p>
          </div>
          <div className="flex items-center gap-2.5">
            {stats.redBlindspots > 0 && (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-500/10 border border-red-500/20">
                <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />
                <span className="text-xs text-red-400 font-medium">{stats.redBlindspots} 個需要處理</span>
              </div>
            )}
            {stats.yellowBlindspots > 0 && (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20">
                <span className="w-2 h-2 rounded-full bg-amber-400" />
                <span className="text-xs text-amber-400">{stats.yellowBlindspots} 個待確認</span>
              </div>
            )}
          </div>
        </div>

        {/* Confirmation bar */}
        <div className="h-1 rounded-full bg-[#27272A] overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-emerald-500/80 to-emerald-400 transition-all duration-700"
            style={{ width: `${stats.confirmedRate}%` }}
          />
        </div>

        {/* Product cards */}
        <div className="space-y-4">
          {products.map(product => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>

        {/* Orphan blindspots — not linked to any product */}
        {orphanBlindspots.length > 0 && (
          <div className="rounded-2xl border border-[#27272A] bg-[#111113] overflow-hidden">
            <div className="px-5 pt-5 pb-4 flex items-start gap-4">
              <div className="w-11 h-11 rounded-full border-2 border-[#FAFAFA]/10 bg-[#FAFAFA]/5 flex items-center justify-center shrink-0">
                <span className="text-base text-[#FAFAFA]/40">?</span>
              </div>
              <div className="flex-1">
                <h2 className="text-lg font-bold text-[#FAFAFA]/70">未歸屬的盲點</h2>
                <p className="text-sm text-[#FAFAFA]/35 mt-0.5">
                  這 {orphanBlindspots.length} 個盲點沒有連結到任何產品或模組
                </p>
              </div>
            </div>
            <div className="px-5 pb-5 space-y-2">
              {orphanBlindspots
                .sort((a, b) => (a.severity === "red" ? 0 : 1) - (b.severity === "red" ? 0 : 1))
                .map(bs => <BlindspotCard key={bs.id} bs={bs} />)
              }
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
