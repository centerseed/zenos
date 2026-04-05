"use client";

import { useState, useMemo, useEffect, useCallback, Suspense } from "react";
import { useAuth } from "@/lib/auth";
import { AuthGuard } from "@/components/AuthGuard";
import { AppNav } from "@/components/AppNav";
import { LoadingState } from "@/components/LoadingState";
import { useSearchParams } from "next/navigation";
import {
  getAllEntities,
  getAllBlindspots,
  getAllRelationships,
  getTasks,
  getQualitySignals,
} from "@/lib/api";
import type { Entity, Blindspot, Relationship, Task, QualitySignals } from "@/types";
import { NODE_TYPE_COLORS, NODE_TYPE_LABELS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import dynamic from "next/dynamic";

const KnowledgeGraph = dynamic(() => import("@/components/KnowledgeGraph"), {
  ssr: false,
  loading: () => <LoadingState variant="graph" label="Loading graph..." className="flex-1" />,
});

const NodeDetailSheet = dynamic(() => import("@/components/NodeDetailSheet"), {
  ssr: false,
});

// ─── Left Sidebar ───

function Sidebar({
  entities,
  focusProduct,
  setFocusProduct,
  className,
  onDismiss,
}: {
  entities: Entity[];
  focusProduct: string | null;
  setFocusProduct: (id: string | null) => void;
  className?: string;
  onDismiss?: () => void;
}) {
  const products = entities.filter((e) => e.type === "product");
  const modules = entities.filter((e) => e.type === "module");
  const confirmed = entities.filter((e) => e.confirmedByUser).length;
  const confirmedRate =
    entities.length > 0 ? Math.round((confirmed / entities.length) * 100) : 0;

  return (
    <div className={cn("w-[230px] shrink-0 border-r border-border bg-card flex flex-col h-full overflow-y-auto", className)}>
      <div className="px-3 pt-4 pb-3 border-b border-border">
        {onDismiss && (
          <div className="flex justify-end mb-2 md:hidden">
            <button
              onClick={onDismiss}
              className="text-xs text-muted-foreground hover:text-foreground cursor-pointer"
            >
              Close
            </button>
          </div>
        )}
        <h2 className="text-sm font-bold text-foreground">Naruvia</h2>
        <div className="flex items-center gap-2 mt-2">
          <div className="flex-1 h-1 rounded-full bg-foreground/5 overflow-hidden">
            <div
              className="h-full rounded-full bg-emerald-400/60"
              style={{ width: `${confirmedRate}%` }}
            />
          </div>
          <span className="text-xs text-foreground/55">{confirmedRate}%</span>
        </div>
      </div>

      <div className="px-2 py-2 border-b border-border">
        <div className="text-xs text-foreground/65 uppercase tracking-widest px-1 mb-1.5">
          Knowledge Map
        </div>
        <button
          onClick={() => {
            setFocusProduct(null);
            onDismiss?.();
          }}
          className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs transition-colors cursor-pointer mb-0.5 ${
            focusProduct === null
              ? "bg-foreground/10 text-foreground/70"
              : "text-foreground/65 hover:bg-foreground/5"
          }`}
        >
          <span className="w-2 h-2 rounded-full bg-foreground/20" />
          <span className="flex-1 text-left">All Products</span>
        </button>
        {products.map((p) => (
          <button
            key={p.id}
            onClick={() => {
              setFocusProduct(p.id);
              onDismiss?.();
            }}
            className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs transition-colors cursor-pointer ${
              focusProduct === p.id
                ? "bg-blue-500/15 text-blue-300"
                : "text-foreground/65 hover:bg-foreground/5"
            }`}
          >
            <span
              className="w-2 h-2 rounded-full shrink-0"
              style={{ backgroundColor: NODE_TYPE_COLORS.product }}
            />
            <span className="flex-1 text-left truncate">{p.name}</span>
          </button>
        ))}
      </div>

      <div className="px-3 py-4 text-[10px] text-foreground/30 leading-relaxed italic">
        Select a product to focus the view. Click nodes on graph for details.
      </div>
    </div>
  );
}

// ─── Main Content ───

function KnowledgeMapContent() {
  const { user, partner } = useAuth();
  const searchParams = useSearchParams();
  const targetId = searchParams.get("id");

  const [entities, setEntities] = useState<Entity[]>([]);
  const [blindspots, setBlindspots] = useState<Blindspot[]>([]);
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [qualitySignals, setQualitySignals] = useState<QualitySignals>({ search_unused: [], summary_poor: [] });
  const [loading, setLoading] = useState(true);
  
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focusedNodeId, setFocusedNodeId] = useState<string | null>(null);
  const [hoveredSidebarNodeId, setHoveredSidebarNodeId] = useState<string | null>(null);
  
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [focusProduct, setFocusProduct] = useState<string | null>(null);

  useEffect(() => {
    if (!user || !partner) return;
    async function load() {
      try {
        const token = await user!.getIdToken();
        const [fetchedEntities, fetchedBlindspots, fetchedRelationships, fetchedTasks, fetchedQuality] =
          await Promise.all([
            getAllEntities(token),
            getAllBlindspots(token),
            getAllRelationships(token),
            getTasks(token),
            getQualitySignals(token).catch(() => ({ search_unused: [], summary_poor: [] })),
          ]);
        setEntities(fetchedEntities);
        setBlindspots(fetchedBlindspots);
        setRelationships(fetchedRelationships);
        setTasks(fetchedTasks);
        setQualitySignals(fetchedQuality);

        // Auto-select if id is in URL
        if (targetId) {
          const exists = fetchedEntities.some(e => e.id === targetId);
          if (exists) {
            setSelectedId(targetId);
            setFocusedNodeId(targetId);
          }
        }
      } catch (err) {
        console.error("Failed to load data:", err);
      }
      setLoading(false);
    }
    load();
  }, [user, partner, targetId]);

  const entityMap = useMemo(() => new Map(entities.map((e) => [e.id, e])), [entities]);
  const blindspotsByEntity = useMemo(() => {
    const map = new Map<string, Blindspot[]>();
    for (const b of blindspots) {
      for (const eid of b.relatedEntityIds) {
        const list = map.get(eid) ?? [];
        list.push(b);
        map.set(eid, list);
      }
    }
    return map;
  }, [blindspots]);

  const selectedEntity = useMemo(() => selectedId ? entityMap.get(selectedId) ?? null : null, [selectedId, entityMap]);

  // Filter entities based on focusProduct
  const filteredEntities = useMemo(() => {
    if (!focusProduct) return entities;
    const focusIds = new Set<string>();
    focusIds.add(focusProduct);
    entities.forEach(e => {
      if (e.parentId === focusProduct) focusIds.add(e.id);
    });
    // Add L3 nodes that belong to these parents
    entities.forEach(e => {
      if (e.parentId && focusIds.has(e.parentId)) focusIds.add(e.id);
    });
    return entities.filter(e => focusIds.has(e.id));
  }, [entities, focusProduct]);

  const handleSelect = useCallback((e: Entity) => {
    setSelectedId(prev => {
      const next = prev === e.id ? null : e.id;
      setFocusedNodeId(next);
      return next;
    });
  }, []);

  return (
    <div className="h-screen flex flex-col bg-background">
      <AppNav />
      {loading ? (
        <LoadingState variant="page" label="Loading knowledge map..." />
      ) : (
        <div className="flex-1 flex overflow-hidden relative">
          <button
            onClick={() => setSidebarOpen(true)}
            className="md:hidden absolute top-3 left-3 z-40 rounded border border-border bg-card/95 px-2.5 py-1.5 text-xs text-muted-foreground"
          >
            Menu
          </button>
          
          <Sidebar
            entities={entities}
            focusProduct={focusProduct}
            setFocusProduct={setFocusProduct}
            onDismiss={() => setSidebarOpen(false)}
            className={cn(
              "absolute inset-y-0 left-0 z-50 transition-transform md:relative md:translate-x-0",
              sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
            )}
          />

          <main className="flex-1 relative flex flex-col min-w-0">
            <KnowledgeGraph
              entities={filteredEntities}
              relationships={relationships}
              blindspotsByEntity={blindspotsByEntity}
              onNodeClick={handleSelect}
              hoveredSidebarNodeId={hoveredSidebarNodeId}
              focusedNodeId={focusedNodeId}
              detailPanelOpen={!!selectedEntity}
            />
          </main>

          {selectedEntity && (
            <NodeDetailSheet
              entity={selectedEntity}
              entities={entities}
              relationships={relationships}
              blindspots={blindspotsByEntity.get(selectedEntity.id) ?? []}
              tasks={tasks}
              qualitySignals={qualitySignals}
              onClose={() => { setSelectedId(null); setFocusedNodeId(null); }}
              onHoverNode={setHoveredSidebarNodeId}
              onFocusNode={(id) => {
                const target = entityMap.get(id);
                if (target) handleSelect(target);
              }}
            />
          )}
        </div>
      )}
    </div>
  );
}

function KnowledgeMapPage() {
  return (
    <Suspense fallback={<LoadingState variant="page" label="Loading..." />}>
      <KnowledgeMapContent />
    </Suspense>
  );
}

export default function Page() {
  return (
    <AuthGuard>
      <KnowledgeMapPage />
    </AuthGuard>
  );
}
