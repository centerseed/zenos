"use client";

import { useState, useMemo, useEffect, useCallback, Suspense } from "react";
import { useAuth } from "@/lib/auth";
import { AuthGuard } from "@/components/AuthGuard";
import { AppNav } from "@/components/AppNav";
import { GovernanceHealthHint } from "@/components/GovernanceHealthHint";
import { LoadingState } from "@/components/LoadingState";
import { useSearchParams } from "next/navigation";
import {
  getAllEntities,
  getAllBlindspots,
  getAllRelationships,
  getEntityContext,
  getGovernanceHealth,
  getTasks,
  getQualitySignals,
} from "@/lib/api";
import type { Entity, Blindspot, Relationship, Task, QualitySignals, ImpactChainHop } from "@/types";
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
  healthLevel = "green",
}: {
  entities: Entity[];
  focusProduct: string | null;
  setFocusProduct: (id: string | null) => void;
  className?: string;
  onDismiss?: () => void;
  healthLevel?: "green" | "yellow" | "red";
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
        <GovernanceHealthHint level={healthLevel} />
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
  const [healthLevel, setHealthLevel] = useState<"green" | "yellow" | "red">("green");
  const [loading, setLoading] = useState(true);
  const [impactChain, setImpactChain] = useState<ImpactChainHop[]>([]);
  const [reverseImpactChain, setReverseImpactChain] = useState<ImpactChainHop[]>([]);
  
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focusedNodeId, setFocusedNodeId] = useState<string | null>(null);
  const [selectedPathIds, setSelectedPathIds] = useState<string[]>([]);
  const [hoveredSidebarNodeId, setHoveredSidebarNodeId] = useState<string | null>(null);
  
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [focusProduct, setFocusProduct] = useState<string | null>(null);

  useEffect(() => {
    if (!user || !partner) return;
    async function load() {
      try {
        const token = await user!.getIdToken();
        const [fetchedEntities, fetchedBlindspots, fetchedRelationships, fetchedTasks, fetchedQuality, fetchedHealth] =
          await Promise.all([
            getAllEntities(token),
            getAllBlindspots(token),
            getAllRelationships(token),
            getTasks(token),
            getQualitySignals(token).catch(() => ({ search_unused: [], summary_poor: [] })),
            getGovernanceHealth(token).catch(() => ({ overall_level: "green" as const, cached_at: null, stale: true })),
          ]);
        setEntities(fetchedEntities);
        setBlindspots(fetchedBlindspots);
        setRelationships(fetchedRelationships);
        setTasks(fetchedTasks);
        setQualitySignals(fetchedQuality);
        setHealthLevel(fetchedHealth.overall_level);

        // Auto-select if id is in URL
        if (targetId) {
          const exists = fetchedEntities.some(e => e.id === targetId);
          if (exists) {
            setSelectedId(targetId);
            setFocusedNodeId(targetId);
            setSelectedPathIds([targetId]);
          }
        }
      } catch (err) {
        console.error("Failed to load data:", err);
      }
      setLoading(false);
    }
    load();
  }, [user, partner, targetId]);

  useEffect(() => {
    if (!user || !selectedId) {
      setImpactChain([]);
      setReverseImpactChain([]);
      return;
    }

    const activeUser = user;
    const entityId = selectedId;
    let cancelled = false;
    async function loadEntityContext() {
      try {
        const token = await activeUser.getIdToken();
        const context = await getEntityContext(token, entityId);
        if (cancelled) return;
        setImpactChain(context?.impact_chain ?? []);
        setReverseImpactChain(context?.reverse_impact_chain ?? []);
      } catch {
        if (cancelled) return;
        setImpactChain([]);
        setReverseImpactChain([]);
      }
    }

    loadEntityContext();
    return () => {
      cancelled = true;
    };
  }, [user, selectedId]);

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
  const relationshipMap = useMemo(() => {
    const map = new Map<string, Relationship>();
    for (const rel of relationships) {
      map.set(`${rel.sourceEntityId}->${rel.targetId}`, rel);
    }
    return map;
  }, [relationships]);

  const canStepToNode = useCallback((fromId: string, toId: string) => (
    relationships.some((rel) =>
      (rel.sourceEntityId === fromId && rel.targetId === toId) ||
      (rel.sourceEntityId === toId && rel.targetId === fromId)
    )
  ), [relationships]);

  const buildPathRelationships = useCallback((pathIds: string[]) => {
    const hops: Relationship[] = [];
    for (let i = 0; i < pathIds.length - 1; i += 1) {
      const fromId = pathIds[i];
      const toId = pathIds[i + 1];
      const forward = relationshipMap.get(`${fromId}->${toId}`);
      const reverse = relationshipMap.get(`${toId}->${fromId}`);
      if (forward) hops.push(forward);
      else if (reverse) hops.push(reverse);
    }
    return hops;
  }, [relationshipMap]);

  const navigateToEntity = useCallback((entity: Entity, mode: "replace" | "extend" = "replace") => {
    setSelectedId(entity.id);
    setFocusedNodeId(entity.id);
    setSelectedPathIds((prev) => {
      if (mode === "replace" || prev.length === 0) return [entity.id];

      const existingIndex = prev.indexOf(entity.id);
      if (existingIndex >= 0) return prev.slice(0, existingIndex + 1);

      const lastId = prev[prev.length - 1];
      if (canStepToNode(lastId, entity.id)) return [...prev, entity.id];

      return [entity.id];
    });
  }, [canStepToNode]);

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

  const selectedPathEntities = useMemo(
    () => selectedPathIds.map((id) => entityMap.get(id)).filter(Boolean) as Entity[],
    [selectedPathIds, entityMap]
  );

  const selectedPathRelationships = useMemo(
    () => buildPathRelationships(selectedPathIds),
    [buildPathRelationships, selectedPathIds]
  );

  const handleSelect = useCallback((e: Entity) => {
    navigateToEntity(e, selectedPathIds.length > 0 ? "extend" : "replace");
  }, [navigateToEntity, selectedPathIds.length]);

  const handleCloseDetail = useCallback(() => {
    setSelectedId(null);
    setFocusedNodeId(null);
    setSelectedPathIds([]);
  }, []);

  const handleFocusNode = useCallback((id: string) => {
    const target = entityMap.get(id);
    if (target) navigateToEntity(target, "extend");
  }, [entityMap, navigateToEntity]);

  const handleLinkSelect = useCallback((sourceId: string, targetId: string) => {
    setSelectedPathIds((prev) => {
      if (prev.length === 0) {
        setSelectedId(targetId);
        setFocusedNodeId(targetId);
        return [sourceId, targetId];
      }

      const sourceIndex = prev.indexOf(sourceId);
      const targetIndex = prev.indexOf(targetId);
      let nextPath: string[];
      let nextFocusId = targetId;

      if (sourceIndex >= 0 && targetIndex === -1) {
        nextPath = [...prev.slice(0, sourceIndex + 1), targetId];
        nextFocusId = targetId;
      } else if (targetIndex >= 0 && sourceIndex === -1) {
        nextPath = [...prev.slice(0, targetIndex + 1), sourceId];
        nextFocusId = sourceId;
      } else if (sourceIndex >= 0 && targetIndex >= 0) {
        nextPath = prev.slice(0, Math.max(sourceIndex, targetIndex) + 1);
        nextFocusId = nextPath[nextPath.length - 1];
      } else {
        nextPath = [sourceId, targetId];
      }

      setSelectedId(nextFocusId);
      setFocusedNodeId(nextFocusId);
      return nextPath;
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
            healthLevel={healthLevel}
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
              onLinkClick={handleLinkSelect}
              hoveredSidebarNodeId={hoveredSidebarNodeId}
              focusedNodeId={focusedNodeId}
              selectedPathIds={selectedPathIds}
              detailPanelOpen={!!selectedEntity}
            />
          </main>

          {selectedEntity && (
            <NodeDetailSheet
              entity={selectedEntity}
              entities={entities}
              relationships={relationships}
              selectedPathEntities={selectedPathEntities}
              selectedPathRelationships={selectedPathRelationships}
              blindspots={blindspotsByEntity.get(selectedEntity.id) ?? []}
              tasks={tasks}
              qualitySignals={qualitySignals}
              impactChain={impactChain}
              reverseImpactChain={reverseImpactChain}
              onClose={handleCloseDetail}
              onHoverNode={setHoveredSidebarNodeId}
              onFocusNode={handleFocusNode}
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
