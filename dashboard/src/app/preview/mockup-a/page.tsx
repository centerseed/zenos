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

// ─── Mockup A: Tree Hierarchy with REAL Firestore data ───

function deriveHealth(entity: RealEntity): "healthy" | "warning" | "critical" {
  const related = REAL_BLINDSPOTS.filter(b => b.relatedEntityIds.includes(entity.id));
  if (related.some(b => b.severity === "red")) return "critical";
  if (!entity.confirmedByUser || related.some(b => b.severity === "yellow")) return "warning";
  return "healthy";
}

function HealthDot({ health }: { health: string }) {
  const c: Record<string, string> = { healthy: "bg-emerald-400", warning: "bg-amber-400", critical: "bg-red-400 animate-pulse" };
  return <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${c[health] ?? "bg-gray-400"}`} />;
}

function StatusPill({ health }: { health: string }) {
  const s: Record<string, string> = {
    healthy: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    warning: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    critical: "bg-red-500/15 text-red-400 border-red-500/30",
  };
  const l: Record<string, string> = { healthy: "健康", warning: "注意", critical: "異常" };
  return <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full border ${s[health]}`}>{l[health]}</span>;
}

function BlindspotCard({ bs }: { bs: RealBlindspot }) {
  const isRed = bs.severity === "red";
  const relatedNames = bs.relatedEntityIds
    .map(id => REAL_ENTITIES.find(e => e.id === id)?.name)
    .filter(Boolean);

  return (
    <div className={`rounded-lg p-3 border ${isRed ? "bg-red-500/8 border-red-500/25" : "bg-amber-500/8 border-amber-500/25"}`}>
      <div className="flex items-start gap-2">
        <span className={`text-sm mt-0.5 ${isRed ? "text-red-400" : "text-amber-400"}`}>
          {isRed ? "⚠" : "△"}
        </span>
        <div className="flex-1 min-w-0">
          <p className={`text-[13px] leading-snug ${isRed ? "text-red-300" : "text-amber-300"}`}>
            {bs.description}
          </p>
          <div className="flex items-center gap-3 mt-1.5 text-[11px] text-[#FAFAFA]/30">
            {relatedNames.length > 0 && (
              <span>影響 <span className="text-[#FAFAFA]/50">{relatedNames.join(", ")}</span></span>
            )}
            <span>→ {bs.suggestedAction}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function ModuleNode({ mod }: { mod: RealEntity }) {
  const health = deriveHealth(mod);
  return (
    <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-[#18181B]/60 border border-[#27272A] hover:border-[#3F3F46] transition-all">
      <HealthDot health={health} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm text-[#FAFAFA]/85 font-medium truncate">{mod.name}</span>
          {!mod.confirmedByUser && (
            <span className="text-[10px] text-orange-400/70 bg-orange-500/10 px-1.5 py-0.5 rounded shrink-0">草稿</span>
          )}
        </div>
        <p className="text-xs text-[#FAFAFA]/35 mt-0.5 truncate">{mod.summary}</p>
      </div>
      {mod.details?.knownIssues && mod.details.knownIssues.length > 0 && (
        <span className="text-[10px] text-red-400/70 bg-red-500/10 px-1.5 py-0.5 rounded shrink-0">
          {mod.details.knownIssues.length} 已知問題
        </span>
      )}
    </div>
  );
}

function ProductTree({ product }: { product: RealEntity }) {
  const [expanded, setExpanded] = useState(true);
  const modules = getModulesForProduct(product.id);
  const productBlindspots = getBlindspotsForEntity(product.id);
  const moduleBlindspots = modules.flatMap(m => getBlindspotsForEntity(m.id));
  const allBlindspots = [...productBlindspots, ...moduleBlindspots];
  const seen = new Set<string>();
  const dedupedBlindspots = allBlindspots.filter(b => { if (seen.has(b.id)) return false; seen.add(b.id); return true; });

  const confirmedModules = modules.filter(m => m.confirmedByUser).length;
  const healths = modules.map(m => deriveHealth(m));
  const productHealth = healths.includes("critical") ? "critical" : healths.includes("warning") ? "warning" : "healthy";

  const healthRingColors: Record<string, string> = {
    healthy: "border-emerald-500/50 bg-emerald-500/10",
    warning: "border-amber-500/50 bg-amber-500/10",
    critical: "border-red-500/50 bg-red-500/10",
  };

  return (
    <div className="rounded-xl border border-[#27272A] bg-[#111113] overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-4 px-5 py-4 hover:bg-[#18181B]/50 transition-colors cursor-pointer"
      >
        <div className={`w-10 h-10 rounded-full border-2 flex items-center justify-center shrink-0 ${healthRingColors[productHealth]}`}>
          <span className="text-base">{productHealth === "healthy" ? "✓" : productHealth === "warning" ? "!" : "✗"}</span>
        </div>
        <div className="flex-1 text-left min-w-0">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-[#FAFAFA]">{product.name}</h2>
            <StatusPill health={productHealth} />
          </div>
          <p className="text-sm text-[#FAFAFA]/40 mt-0.5 truncate">{product.summary}</p>
        </div>
        <div className="flex items-center gap-6 text-xs text-[#FAFAFA]/35 shrink-0">
          <div className="text-right">
            <div className="text-[#FAFAFA]/50">{modules.length} 模組</div>
            <div className={confirmedModules < modules.length ? "text-amber-400/60" : ""}>
              {confirmedModules}/{modules.length} 已確認
            </div>
          </div>
          <svg
            className={`w-4 h-4 text-[#FAFAFA]/25 transition-transform ${expanded ? "rotate-180" : ""}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {expanded && (
        <div className="px-5 pb-5 space-y-3">
          {/* Module tree */}
          <div className="space-y-1.5 relative">
            <div className="absolute left-[7px] top-0 bottom-0 w-px bg-[#27272A]" />
            {modules.map((mod, i) => (
              <div key={mod.id} className="relative pl-6">
                <div className="absolute left-[7px] top-4 w-3 h-px bg-[#27272A]" />
                {i === modules.length - 1 && (
                  <div className="absolute left-[7px] top-4 bottom-0 w-px bg-[#111113]" />
                )}
                <ModuleNode mod={mod} />
              </div>
            ))}
          </div>

          {/* Blindspots */}
          {dedupedBlindspots.length > 0 && (
            <div className="space-y-2 pt-3 border-t border-[#27272A]">
              <h4 className="text-[10px] uppercase tracking-wider text-[#FAFAFA]/25 font-semibold">
                盲點 ({dedupedBlindspots.length})
              </h4>
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

export default function MockupAReal() {
  const stats = getRealStats();
  const products = REAL_ENTITIES.filter(e => e.type === "product");
  const orphans = getOrphanBlindspots();

  return (
    <div className="min-h-screen bg-[#09090B]">
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
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-[#FAFAFA]">Naruvia</h2>
            <p className="text-sm text-[#FAFAFA]/35 mt-1">
              {stats.totalEntities} 個知識節點 · {stats.confirmedRate}% 已確認
            </p>
          </div>
          <div className="flex items-center gap-2.5">
            {stats.redBlindspots > 0 && (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-500/10 border border-red-500/20">
                <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />
                <span className="text-xs text-red-400 font-medium">{stats.redBlindspots} 個需要處理</span>
              </div>
            )}
            <div className="text-xs text-[#FAFAFA]/30">
              {stats.orphanBlindspots} 個盲點未歸屬
            </div>
          </div>
        </div>

        {/* Confirmation bar */}
        <div className="h-1.5 rounded-full bg-[#27272A] overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-emerald-400"
            style={{ width: `${stats.confirmedRate}%` }}
          />
        </div>

        {/* Product trees */}
        <div className="space-y-4">
          {products.map(product => (
            <ProductTree key={product.id} product={product} />
          ))}
        </div>

        {/* Orphan blindspots */}
        {orphans.length > 0 && (
          <div className="rounded-xl border border-[#27272A] bg-[#111113] overflow-hidden">
            <div className="px-5 pt-4 pb-3 flex items-center gap-3">
              <div className="w-10 h-10 rounded-full border-2 border-[#FAFAFA]/10 bg-[#FAFAFA]/5 flex items-center justify-center shrink-0">
                <span className="text-[#FAFAFA]/30">?</span>
              </div>
              <div>
                <h2 className="text-lg font-semibold text-[#FAFAFA]/60">未歸屬的盲點</h2>
                <p className="text-xs text-[#FAFAFA]/30">{orphans.length} 個盲點沒有連結到任何產品</p>
              </div>
            </div>
            <div className="px-5 pb-5 space-y-2">
              {orphans
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
