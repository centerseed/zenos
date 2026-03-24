"use client";

import { useState, useMemo, useEffect, useRef, useCallback } from "react";
import { useAuth } from "@/lib/auth";
import { AuthGuard } from "@/components/AuthGuard";
import { AppNav } from "@/components/AppNav";
import {
  getAllEntities,
  getAllBlindspots,
  getAllRelationships,
  getTasks,
} from "@/lib/firestore";
import type { Entity, Blindspot, Relationship, Task } from "@/types";

// ─── Types ───

/** All expandable types (entity L3 + task) */
const EXPANDABLE_TYPES = ["document", "task", "goal", "role", "project"] as const;
type ExpandableType = (typeof EXPANDABLE_TYPES)[number];

/** Pure entity L3 types (non-task) */
const ENTITY_L3_TYPES = ["document", "goal", "role", "project"] as const;

/** Default expand types when clicking a module */
const DEFAULT_EXPAND_TYPES: ExpandableType[] = ["document", "task"];

/** Expanded modules state: moduleId -> list of expanded types */
type ExpandedModules = Record<string, ExpandableType[]>;

// ─── Helpers ───

function daysAgo(d: Date): number {
  return Math.floor((Date.now() - d.getTime()) / 86400000);
}

function inferTasksForEntity(entity: Entity, tasks: Task[]): Task[] {
  const name = entity.name.toLowerCase();
  const whatTag = entity.tags.what;
  const whatStr = Array.isArray(whatTag) ? whatTag.join(" ") : whatTag;
  const keywords = whatStr
    .toLowerCase()
    .split(/[,、，\s]+/)
    .filter((k) => k.length > 2);
  return tasks.filter((t) => {
    // Priority: linkedEntities
    if (t.linkedEntities && t.linkedEntities.length > 0) {
      return t.linkedEntities.includes(entity.id);
    }
    // Fallback: text match
    const title = t.title.toLowerCase();
    return title.includes(name) || keywords.some((kw) => title.includes(kw));
  });
}

/** Find tasks for a module: prefer linkedEntities, fall back to text matching */
function findTasksForModule(module: Entity, tasks: Task[]): Task[] {
  const linked = tasks.filter(
    (t) => t.linkedEntities && t.linkedEntities.length > 0 && t.linkedEntities.includes(module.id)
  );
  return linked.length > 0 ? linked : inferTasksForEntity(module, tasks);
}

const TYPE_COLORS: Record<string, string> = {
  product: "#3B82F6",
  module: "#8B5CF6",
  goal: "#10B981",
  role: "#F59E0B",
  document: "#06B6D4",
  project: "#F43F5E",
  task: "#F97316",
};

const TYPE_LABELS: Record<string, string> = {
  product: "Product",
  module: "Module",
  goal: "Goal",
  role: "Role",
  document: "Document",
  project: "Project",
  task: "Task",
};

const ROLE_COLORS: Record<string, string> = {
  architect: "bg-violet-500/20 text-violet-300",
  developer: "bg-blue-500/20 text-blue-300",
  qa: "bg-emerald-500/20 text-emerald-300",
  pm: "bg-amber-500/20 text-amber-300",
};
const ROLE_LABELS: Record<string, string> = {
  architect: "Arch",
  developer: "Dev",
  qa: "QA",
  pm: "PM",
};

// ─── Source Type Icons ───

function SourceIcon({ type }: { type: string }) {
  const t = type.toLowerCase();
  if (t === "github" || t === "git") {
    return (
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-[#FAFAFA]/40 shrink-0">
        <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" />
      </svg>
    );
  }
  if (t === "gdrive" || t === "google" || t === "google_drive") {
    return (
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-[#FAFAFA]/40 shrink-0">
        <path d="M12 2L2 19.5h20L12 2z" />
        <path d="M2 19.5l5-8.5" />
        <path d="M22 19.5l-5-8.5" />
        <path d="M7 11h10" />
      </svg>
    );
  }
  if (t === "notion") {
    return (
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-[#FAFAFA]/40 shrink-0">
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
        <path d="M8 7h8M8 12h5M8 17h3" />
      </svg>
    );
  }
  // Default: external link icon
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-[#FAFAFA]/40 shrink-0">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <polyline points="15 3 21 3 21 9" />
      <line x1="10" y1="14" x2="21" y2="3" />
    </svg>
  );
}

// ─── Type Filter Popover ───

function TypeFilterPopover({
  moduleId,
  moduleName,
  expandedTypes,
  availableTypes,
  onToggle,
  onClose,
  style,
}: {
  moduleId: string;
  moduleName: string;
  expandedTypes: ExpandableType[];
  availableTypes: Record<ExpandableType, number>;
  onToggle: (moduleId: string, type: ExpandableType) => void;
  onClose: () => void;
  style?: React.CSSProperties;
}) {
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [onClose]);

  // Display order: Document → Task → Goal → Role → Project
  const displayOrder: ExpandableType[] = ["document", "task", "goal", "role", "project"];

  return (
    <div
      ref={popoverRef}
      className="bg-[#111113] border border-[#2A2A2E] rounded-lg shadow-xl p-3 z-[100]"
      style={{ minWidth: 180, ...style }}
    >
      <div className="text-xs text-[#FAFAFA]/50 mb-2 truncate">
        Expand: {moduleName}
      </div>
      {displayOrder.map((type) => {
        const count = availableTypes[type] ?? 0;
        if (count === 0) return null;
        const checked = expandedTypes.includes(type);
        return (
          <label
            key={type}
            className="flex items-center gap-2 py-1 cursor-pointer hover:bg-[#FAFAFA]/[0.03] rounded px-1"
          >
            <input
              type="checkbox"
              checked={checked}
              onChange={() => onToggle(moduleId, type)}
              className="w-3 h-3 rounded accent-purple-500"
            />
            <span
              className="w-2 h-2 rounded-full shrink-0"
              style={{ backgroundColor: TYPE_COLORS[type] ?? "#6366F1" }}
            />
            <span className="text-xs text-[#FAFAFA]/70 flex-1">
              {TYPE_LABELS[type] ?? type}
            </span>
            <span className="text-xs text-[#FAFAFA]/40">{count}</span>
          </label>
        );
      })}
    </div>
  );
}

// ─── Entity Chip ───

function EntityChip({
  entity,
  onClick,
}: {
  entity: Entity;
  onClick: (e: Entity) => void;
}) {
  const color = TYPE_COLORS[entity.type] ?? "#6366F1";
  return (
    <button
      onClick={(ev) => {
        ev.stopPropagation();
        onClick(entity);
      }}
      className="inline-flex items-center gap-1.5 rounded-md border border-[#FAFAFA]/8 bg-[#FAFAFA]/[0.03] hover:bg-[#FAFAFA]/[0.07] transition-colors cursor-pointer px-1.5 py-0.5 text-xs"
    >
      <span
        className="w-1.5 h-1.5 rounded-full shrink-0"
        style={{ backgroundColor: color }}
      />
      <span className="text-[#FAFAFA]/70 truncate max-w-[140px]">
        {entity.name}
      </span>
    </button>
  );
}

// ─── Left Sidebar ───

function Sidebar({
  entities,
  blindspots,
  tasks,
  relationships,
  focusProduct,
  setFocusProduct,
  expandedModules,
  onToggleModuleType,
}: {
  entities: Entity[];
  blindspots: Blindspot[];
  tasks: Task[];
  relationships: Relationship[];
  focusProduct: string | null;
  setFocusProduct: (id: string | null) => void;
  expandedModules: ExpandedModules;
  onToggleModuleType: (moduleId: string, type: ExpandableType) => void;
}) {
  const products = entities.filter((e) => e.type === "product");
  const modules = entities.filter((e) => e.type === "module");
  const openBs = blindspots.filter((b) => b.status === "open");
  const confirmed = entities.filter((e) => e.confirmedByUser).length;
  const confirmedRate =
    entities.length > 0 ? Math.round((confirmed / entities.length) * 100) : 0;
  const docCount = entities.filter((e) => e.type === "document").length;

  // Track which module popover is open
  const [popoverModuleId, setPopoverModuleId] = useState<string | null>(null);

  // Compute available types per module (entity L3 + task)
  const availableTypesPerModule = useMemo(() => {
    const result: Record<string, Record<ExpandableType, number>> = {};
    for (const m of modules) {
      const counts: Record<ExpandableType, number> = { document: 0, task: 0, goal: 0, role: 0, project: 0 };
      for (const e of entities) {
        if (e.parentId === m.id && ENTITY_L3_TYPES.includes(e.type as (typeof ENTITY_L3_TYPES)[number])) {
          counts[e.type as ExpandableType]++;
        }
      }
      counts.task = findTasksForModule(m, tasks).length;
      result[m.id] = counts;
    }
    return result;
  }, [modules, entities, tasks]);

  // Count total L3 children per module
  const l3CountPerModule = useMemo(() => {
    const result: Record<string, number> = {};
    for (const m of modules) {
      result[m.id] = entities.filter(
        (e) => e.parentId === m.id && ENTITY_L3_TYPES.includes(e.type as (typeof ENTITY_L3_TYPES)[number])
      ).length;
    }
    return result;
  }, [modules, entities]);

  return (
    <div className="w-[230px] shrink-0 border-r border-[#1F1F23] bg-[#0C0C0E] flex flex-col h-full overflow-y-auto">
      {/* Company header */}
      <div className="px-3 pt-4 pb-3 border-b border-[#1F1F23]">
        <h2 className="text-sm font-bold text-[#FAFAFA]">Naruvia</h2>
        <div className="flex items-center gap-2 mt-2">
          <div className="flex-1 h-1 rounded-full bg-[#FAFAFA]/5 overflow-hidden">
            <div
              className="h-full rounded-full bg-emerald-400/60"
              style={{ width: `${confirmedRate}%` }}
            />
          </div>
          <span className="text-xs text-[#FAFAFA]/55">{confirmedRate}%</span>
        </div>
        <div className="text-xs text-[#FAFAFA]/65 mt-1">
          {entities.length} nodes · {docCount} docs ·{" "}
          {relationships.length} rels
        </div>
      </div>

      {/* Products & Modules tree */}
      <div className="px-2 py-2 border-b border-[#1F1F23]">
        <div className="text-xs text-[#FAFAFA]/65 uppercase tracking-widest px-1 mb-1.5">
          Products
        </div>
        <button
          onClick={() => setFocusProduct(null)}
          className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs transition-colors cursor-pointer mb-0.5 ${
            focusProduct === null
              ? "bg-[#FAFAFA]/8 text-[#FAFAFA]/70"
              : "text-[#FAFAFA]/65 hover:bg-[#FAFAFA]/[0.03]"
          }`}
        >
          <span className="w-2 h-2 rounded-full bg-[#FAFAFA]/15" />
          <span className="flex-1 text-left">All</span>
        </button>
        {products.map((p) => {
          const productModules = modules.filter((m) => m.parentId === p.id);
          const moduleCount = productModules.length;
          const pBs = blindspots.filter(
            (b) =>
              b.status === "open" && b.relatedEntityIds.includes(p.id)
          );
          return (
            <div key={p.id}>
              <button
                onClick={() =>
                  setFocusProduct(focusProduct === p.id ? null : p.id)
                }
                className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs transition-colors cursor-pointer ${
                  focusProduct === p.id
                    ? "bg-blue-500/15 text-blue-300"
                    : "text-[#FAFAFA]/65 hover:bg-[#FAFAFA]/[0.03]"
                }`}
              >
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: TYPE_COLORS.product }}
                />
                <span className="flex-1 text-left truncate">{p.name}</span>
                <span className="text-xs text-[#FAFAFA]/65">{moduleCount}</span>
                {pBs.length > 0 && (
                  <span className="w-1.5 h-1.5 rounded-full bg-red-400 shrink-0" />
                )}
              </button>
              {/* Module children */}
              {productModules.map((m) => {
                const l3Count = l3CountPerModule[m.id] ?? 0;
                const isExpanded = (expandedModules[m.id]?.length ?? 0) > 0;
                return (
                  <div key={m.id} className="relative">
                    <div className="flex items-center gap-0 pl-4">
                      {/* Expand arrow button */}
                      {l3Count > 0 ? (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setPopoverModuleId(popoverModuleId === m.id ? null : m.id);
                          }}
                          className="w-4 h-4 flex items-center justify-center text-[#FAFAFA]/40 hover:text-[#FAFAFA]/70 cursor-pointer shrink-0"
                          title="Expand L3 nodes"
                        >
                          <svg
                            width="8"
                            height="8"
                            viewBox="0 0 8 8"
                            fill="currentColor"
                            className={`transition-transform ${isExpanded ? "rotate-90" : ""}`}
                          >
                            <path d="M2 1l4 3-4 3V1z" />
                          </svg>
                        </button>
                      ) : (
                        <span className="w-4 h-4 shrink-0" />
                      )}
                      <div className="flex items-center gap-1.5 py-1 text-xs text-[#FAFAFA]/55 truncate flex-1 min-w-0">
                        <span
                          className="w-1.5 h-1.5 rounded-full shrink-0"
                          style={{ backgroundColor: TYPE_COLORS.module }}
                        />
                        <span className="truncate">{m.name}</span>
                        {l3Count > 0 && (
                          <span className="text-[#FAFAFA]/30 text-[10px]">{l3Count}</span>
                        )}
                      </div>
                    </div>
                    {/* Type filter popover */}
                    {popoverModuleId === m.id && (
                      <div className="absolute left-6 top-full z-50">
                        <TypeFilterPopover
                          moduleId={m.id}
                          moduleName={m.name}
                          expandedTypes={expandedModules[m.id] ?? []}
                          availableTypes={availableTypesPerModule[m.id] ?? { document: 0, task: 0, goal: 0, role: 0, project: 0 }}
                          onToggle={onToggleModuleType}
                          onClose={() => setPopoverModuleId(null)}
                        />
                      </div>
                    )}
                    {/* Show expanded L3 children */}
                    {isExpanded && (
                      <div className="pl-9">
                        {entities
                          .filter(
                            (e) =>
                              e.parentId === m.id &&
                              expandedModules[m.id]?.includes(e.type as ExpandableType)
                          )
                          .map((e) => (
                            <div
                              key={e.id}
                              className="flex items-center gap-1.5 py-0.5 text-[10px] text-[#FAFAFA]/45"
                            >
                              <span
                                className="w-1 h-1 rounded-full shrink-0"
                                style={{ backgroundColor: TYPE_COLORS[e.type] ?? "#6366F1" }}
                              />
                              <span className="truncate">{e.name}</span>
                            </div>
                          ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>

      {/* Blindspots */}
      <div className="px-2 py-2 border-b border-[#1F1F23]">
        <div className="text-xs text-[#FAFAFA]/65 uppercase tracking-widest px-1 mb-1">
          Blindspots ({openBs.length})
        </div>
        <div className="space-y-1 max-h-[140px] overflow-y-auto">
          {openBs
            .sort(
              (a, b) =>
                (a.severity === "red" ? 0 : 1) -
                (b.severity === "red" ? 0 : 1)
            )
            .slice(0, 6)
            .map((bs) => (
              <div key={bs.id} className="flex items-start gap-1.5 px-1">
                <span
                  className={`w-1.5 h-1.5 rounded-full shrink-0 mt-1 ${
                    bs.severity === "red"
                      ? "bg-red-400"
                      : "bg-amber-400/40"
                  }`}
                />
                <span className="text-xs text-[#FAFAFA]/60 leading-snug line-clamp-2">
                  {bs.description}
                </span>
              </div>
            ))}
          {openBs.length > 6 && (
            <div className="text-xs text-[#FAFAFA]/50 px-1">
              +{openBs.length - 6} more
            </div>
          )}
        </div>
      </div>

      {/* Tasks */}
      <div className="px-2 py-2 mt-auto">
        <div className="text-xs text-[#FAFAFA]/65 uppercase tracking-widest px-1 mb-1">
          Tasks ({tasks.length})
        </div>
        <div className="space-y-0.5 px-1">
          {[
            {
              l: "Done",
              c: tasks.filter((t) => t.status === "done").length,
              color: "bg-emerald-400",
            },
            {
              l: "Active",
              c: tasks.filter((t) =>
                ["in_progress", "review"].includes(t.status)
              ).length,
              color: "bg-blue-400",
            },
            {
              l: "Pending",
              c: tasks.filter((t) =>
                ["backlog", "todo"].includes(t.status)
              ).length,
              color: "bg-[#FAFAFA]/12",
            },
          ].map((s) => (
            <div key={s.l} className="flex items-center gap-1.5">
              <span className={`w-1.5 h-2.5 rounded-sm ${s.color}`} />
              <span className="text-xs text-[#FAFAFA]/60 flex-1">{s.l}</span>
              <span className="text-xs text-[#FAFAFA]/65">{s.c}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Center: Force-Directed Graph ───

function GraphCanvas({
  entities,
  relationships,
  blindspots,
  tasks,
  selectedId,
  onSelect,
  focusProduct,
  expandedModules,
  onToggleModuleType,
  onExpandModule,
  onCollapseModule,
}: {
  entities: Entity[];
  relationships: Relationship[];
  blindspots: Blindspot[];
  tasks: Task[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  focusProduct: string | null;
  expandedModules: ExpandedModules;
  onToggleModuleType: (moduleId: string, type: ExpandableType) => void;
  onExpandModule: (moduleId: string) => void;
  onCollapseModule: (moduleId: string) => void;
}) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [ForceGraph, setForceGraph] = useState<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fgRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ width: 800, height: 600 });
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  // Click popover state (shown when module is expanded)
  const [clickPopover, setClickPopover] = useState<{
    moduleId: string;
    x: number;
    y: number;
  } | null>(null);

  useEffect(() => {
    import("react-force-graph-2d").then((mod) =>
      setForceGraph(() => mod.default)
    );
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) setDims({ width, height });
      }
    });
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    if (!fgRef.current) return;
    fgRef.current.d3Force("charge")?.strength(-150).distanceMax(250);
    fgRef.current.d3Force("link")?.distance(70);
    fgRef.current.d3Force("center")?.strength(0.15);
  }, [ForceGraph]);

  const blindspotSet = useMemo(() => {
    const s = new Set<string>();
    for (const b of blindspots)
      if (b.status === "open")
        for (const id of b.relatedEntityIds) s.add(id);
    return s;
  }, [blindspots]);

  // Entity map for looking up modules by ID
  const entityMap = useMemo(
    () => new Map(entities.map((e) => [e.id, e])),
    [entities]
  );

  // Available expandable types per module (entity L3 + task)
  const availableTypesPerModule = useMemo(() => {
    const result: Record<string, Record<ExpandableType, number>> = {};
    for (const e of entities) {
      if (e.type === "module") {
        const counts: Record<ExpandableType, number> = { document: 0, task: 0, goal: 0, role: 0, project: 0 };
        for (const child of entities) {
          if (child.parentId === e.id && ENTITY_L3_TYPES.includes(child.type as (typeof ENTITY_L3_TYPES)[number])) {
            counts[child.type as ExpandableType]++;
          }
        }
        counts.task = findTasksForModule(e, tasks).length;
        result[e.id] = counts;
      }
    }
    return result;
  }, [entities, tasks]);

  const graphData = useMemo(() => {
    const entityIds = new Set(entities.map((e) => e.id));

    // Layered visibility: L1 (product) + L2 (module) always visible,
    // L3 (document/goal/role/project) only if parent module is expanded for that type
    const isVisible = (e: Entity): boolean => {
      if (e.type === "product" || e.type === "module") return true;
      // L3: check if parent module has this type expanded
      if (e.parentId) {
        const expandedTypes = expandedModules[e.parentId];
        if (expandedTypes?.includes(e.type as ExpandableType)) return true;
      }
      return false;
    };

    let visibleIds: Set<string>;

    if (focusProduct) {
      visibleIds = new Set<string>();
      for (const e of entities) {
        if (!isVisible(e)) continue;
        if (e.id === focusProduct) {
          visibleIds.add(e.id);
        } else if (e.parentId === focusProduct) {
          visibleIds.add(e.id);
        } else if (e.parentId) {
          // L3 node: check if its grandparent is the focusProduct
          const parent = entityMap.get(e.parentId);
          if (parent && parent.parentId === focusProduct) {
            visibleIds.add(e.id);
          }
        }
      }
      // Also add related entities via relationships
      for (const r of relationships) {
        if (visibleIds.has(r.sourceEntityId) && entityIds.has(r.targetId)) {
          const target = entityMap.get(r.targetId);
          if (target && isVisible(target)) visibleIds.add(r.targetId);
        }
        if (visibleIds.has(r.targetId) && entityIds.has(r.sourceEntityId)) {
          const source = entityMap.get(r.sourceEntityId);
          if (source && isVisible(source)) visibleIds.add(r.sourceEntityId);
        }
      }
    } else {
      visibleIds = new Set<string>();
      for (const e of entities) {
        if (isVisible(e)) visibleIds.add(e.id);
      }
    }

    // Track which module nodes have newly expanded children (for initial positioning)
    const modulePositions: Record<string, boolean> = {};
    for (const moduleId of Object.keys(expandedModules)) {
      if (expandedModules[moduleId].length > 0) {
        modulePositions[moduleId] = true;
      }
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const nodes: any[] = entities
      .filter((e) => visibleIds.has(e.id))
      .map((e) => ({
        id: e.id,
        name: e.name,
        type: e.type,
        parentId: e.parentId,
        confirmed: e.confirmedByUser,
        hasBlindspot: blindspotSet.has(e.id),
        days: daysAgo(e.updatedAt),
        taskCount: inferTasksForEntity(e, tasks).length,
        val:
          e.type === "product"
            ? 20
            : e.type === "module"
              ? 8
              : e.type === "document"
                ? 6
                : e.type === "goal"
                  ? 10
                  : 7,
      }));

    const nodeIds = new Set(nodes.map((n) => n.id));
    const links: { source: string; target: string; type: string }[] =
      relationships
        .filter(
          (r) => nodeIds.has(r.sourceEntityId) && nodeIds.has(r.targetId)
        )
        .map((r) => ({
          source: r.sourceEntityId,
          target: r.targetId,
          type: r.type,
        }));

    // Add part_of links from parentId
    for (const e of entities) {
      if (e.parentId && nodeIds.has(e.id) && nodeIds.has(e.parentId)) {
        const exists = links.some(
          (l) => l.source === e.id && l.target === e.parentId
        );
        if (!exists) {
          links.push({ source: e.id, target: e.parentId, type: "part_of" });
        }
      }
    }

    // Task nodes for expanded modules
    const taskNodeIds = new Set<string>();
    for (const [moduleId, types] of Object.entries(expandedModules)) {
      if (!types.includes("task")) continue;
      if (!visibleIds.has(moduleId)) continue;
      const moduleEntity = entityMap.get(moduleId);
      const moduleTasks = moduleEntity ? findTasksForModule(moduleEntity, tasks) : [];
      for (const t of moduleTasks) {
        const nodeId = `task:${t.id}`;
        if (!taskNodeIds.has(nodeId)) {
          taskNodeIds.add(nodeId);
          nodes.push({
            id: nodeId,
            name: t.title,
            type: "task",
            parentId: moduleId,
            confirmed: true,
            hasBlindspot: false,
            days: Math.floor((Date.now() - t.updatedAt.getTime()) / 86400000),
            taskCount: 0,
            val: 5,
            taskStatus: t.status,
            taskPriority: t.priority,
          });
          links.push({ source: nodeId, target: moduleId, type: "task" });
        }
      }
    }

    return { nodes, links };
  }, [entities, relationships, blindspotSet, tasks, focusProduct, expandedModules, entityMap]);

  // Place newly expanded L3 nodes at their parent module's position
  useEffect(() => {
    if (!fgRef.current) return;
    const fg = fgRef.current;
    if (!fg.graphData || typeof fg.graphData !== "function") return;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const currentData = fg.graphData() as any;
    if (!currentData?.nodes) return;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const nodeMap = new Map<string, any>();
    for (const n of graphData.nodes) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const fgNode = currentData.nodes.find((gn: any) => gn.id === n.id);
      if (fgNode) nodeMap.set(n.id, fgNode);
    }

    for (const n of graphData.nodes) {
      if (n.type !== "product" && n.type !== "module" && n.parentId) {
        const fgNode = nodeMap.get(n.id);
        const parentNode = nodeMap.get(n.parentId);
        if (fgNode && parentNode && fgNode.x === undefined) {
          // Place at parent position with slight random offset
          fgNode.x = (parentNode.x ?? 0) + (Math.random() - 0.5) * 20;
          fgNode.y = (parentNode.y ?? 0) + (Math.random() - 0.5) * 20;
        }
      }
    }
  }, [graphData]);

  const connectedNodes = useMemo(() => {
    if (!hoveredNode) return new Set<string>();
    const s = new Set<string>([hoveredNode]);
    for (const l of graphData.links) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const src =
        typeof l.source === "string"
          ? l.source
          : (l.source as any).id;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const tgt =
        typeof l.target === "string"
          ? l.target
          : (l.target as any).id;
      if (src === hoveredNode) s.add(tgt);
      if (tgt === hoveredNode) s.add(src);
    }
    return s;
  }, [hoveredNode, graphData.links]);

  const nodeCanvasObject = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const x = node.x as number;
      const y = node.y as number;
      const r = Math.sqrt(node.val as number) * 2.8;
      const isTaskNode = node.type === "task";
      const taskStatus = node.taskStatus as string | undefined;
      const isBlocked = isTaskNode && taskStatus === "blocked";
      const color = isBlocked ? "#EF4444" : (TYPE_COLORS[node.type as string] ?? "#6366F1");
      const isSelected = selectedId === node.id;
      const isHovered = hoveredNode === node.id;
      const isDimmed =
        hoveredNode !== null && !connectedNodes.has(node.id as string);
      const days = node.days as number;
      const activity =
        days <= 1 ? 1 : days <= 3 ? 0.7 : days <= 7 ? 0.45 : 0.2;

      ctx.save();
      if (isDimmed) ctx.globalAlpha = 0.12;

      // Blocked task glow
      if (isBlocked && !isDimmed) {
        ctx.shadowBlur = 20;
        ctx.shadowColor = "#EF4444";
      }
      // Blindspot glow
      if (node.hasBlindspot && !isDimmed) {
        ctx.shadowBlur = 25;
        ctx.shadowColor = "#EF4444";
      }
      // Selected glow
      if (isSelected) {
        ctx.shadowBlur = 20;
        ctx.shadowColor = color;
      }
      if (isHovered) {
        ctx.shadowBlur = 18;
        ctx.shadowColor = color;
      }

      // Node circle
      ctx.beginPath();
      ctx.arc(x, y, r, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.globalAlpha = isDimmed ? 0.12 : activity;
      ctx.fill();
      ctx.globalAlpha = isDimmed ? 0.12 : 1;

      // Confirmation ring (dashed = draft)
      if (!node.confirmed && !isDimmed) {
        ctx.strokeStyle = "rgba(251,191,36,0.5)";
        ctx.lineWidth = 1.5;
        ctx.setLineDash([3, 3]);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      // Selected ring
      if (isSelected) {
        ctx.strokeStyle = "rgba(255,255,255,0.6)";
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      ctx.shadowBlur = 0;
      ctx.shadowColor = "transparent";

      // Task count badge (only for non-task nodes)
      if (!isTaskNode && (node.taskCount as number) > 0 && !isDimmed) {
        const badgeR = 5;
        const bx = x + r * 0.7;
        const by = y - r * 0.7;
        ctx.beginPath();
        ctx.arc(bx, by, badgeR, 0, 2 * Math.PI);
        ctx.fillStyle = "#111";
        ctx.fill();
        ctx.beginPath();
        ctx.arc(bx, by, badgeR - 1, 0, 2 * Math.PI);
        ctx.fillStyle = "#60A5FA";
        ctx.fill();
        ctx.font = `bold ${8}px -apple-system, sans-serif`;
        ctx.fillStyle = "#fff";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(String(node.taskCount), bx, by);
      }

      // Task status badge
      if (isTaskNode && taskStatus && !isDimmed) {
        const statusAbbr =
          taskStatus === "done" ? "✓" :
          taskStatus === "in_progress" ? "▶" :
          taskStatus === "blocked" ? "!" :
          taskStatus === "review" ? "R" : "·";
        const statusColor =
          taskStatus === "done" ? "#10B981" :
          taskStatus === "in_progress" ? "#3B82F6" :
          taskStatus === "blocked" ? "#EF4444" : "#F97316";
        const badgeR = 4.5;
        const bx = x + r * 0.7;
        const by = y - r * 0.7;
        ctx.beginPath();
        ctx.arc(bx, by, badgeR, 0, 2 * Math.PI);
        ctx.fillStyle = "#111";
        ctx.fill();
        ctx.beginPath();
        ctx.arc(bx, by, badgeR - 0.5, 0, 2 * Math.PI);
        ctx.fillStyle = statusColor;
        ctx.fill();
        ctx.font = `bold 7px -apple-system, sans-serif`;
        ctx.fillStyle = "#fff";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(statusAbbr, bx, by);
      }

      // Label
      const fontSize = Math.max(14 / globalScale, 4.5);
      ctx.font = `500 ${fontSize}px -apple-system, BlinkMacSystemFont, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "top";

      const label = node.name as string;
      const maxChars = 16;
      const displayLabel =
        label.length > maxChars ? label.slice(0, maxChars) + "\u2026" : label;
      const textW = ctx.measureText(displayLabel).width;
      const textY = y + r + 4;

      // Text bg
      ctx.fillStyle = "rgba(9,9,11,0.8)";
      ctx.fillRect(x - textW / 2 - 2, textY - 1, textW + 4, fontSize + 3);

      ctx.fillStyle =
        isSelected || isHovered
          ? "#FFFFFF"
          : `rgba(250,250,250,${isDimmed ? 0.12 : 0.9})`;
      ctx.fillText(displayLabel, x, textY);

      ctx.restore();
    },
    [selectedId, hoveredNode, connectedNodes]
  );

  const linkColor = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (link: any) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const src =
        typeof link.source === "string"
          ? link.source
          : (link.source as any)?.id;
      // Task edges use orange
      if (String(src).startsWith("task:")) return "rgba(249,115,22,0.4)";
      if (!hoveredNode && !selectedId) return "rgba(255,255,255,0.08)";
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const tgt =
        typeof link.target === "string"
          ? link.target
          : (link.target as any)?.id;
      const focusId = hoveredNode ?? selectedId;
      if (src === focusId || tgt === focusId)
        return "rgba(255,255,255,0.45)";
      return "rgba(255,255,255,0.03)";
    },
    [hoveredNode, selectedId]
  );

  const linkWidth = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (link: any) => {
      const focusId = hoveredNode ?? selectedId;
      if (!focusId) return 0.8;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const src =
        typeof link.source === "string"
          ? link.source
          : (link.source as any)?.id;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const tgt =
        typeof link.target === "string"
          ? link.target
          : (link.target as any)?.id;
      if (src === focusId || tgt === focusId) return 1.5;
      return 0.3;
    },
    [hoveredNode, selectedId]
  );


  if (!ForceGraph) {
    return (
      <div
        ref={containerRef}
        className="flex-1 flex items-center justify-center bg-[#09090B]"
      >
        <span className="text-[#FAFAFA]/50 text-sm">Loading graph...</span>
      </div>
    );
  }

  const FG = ForceGraph;
  return (
    <div
      ref={containerRef}
      className="flex-1 relative bg-[#09090B] overflow-hidden"
    >
      <FG
        ref={fgRef}
        graphData={graphData}
        width={dims.width}
        height={dims.height}
        backgroundColor="#09090B"
        nodeRelSize={6}
        nodeCanvasObject={nodeCanvasObject}
        nodeCanvasObjectMode={() => "replace"}
        nodePointerAreaPaint={(
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          node: any,
          color: string,
          ctx: CanvasRenderingContext2D
        ) => {
          const r = Math.sqrt(node.val as number) * 2.8;
          ctx.beginPath();
          ctx.arc(
            node.x as number,
            node.y as number,
            r + 5,
            0,
            2 * Math.PI
          );
          ctx.fillStyle = color;
          ctx.fill();
        }}
        linkColor={linkColor}
        linkWidth={linkWidth}
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={1}
        linkDirectionalArrowColor={() => "rgba(255,255,255,0.15)"}
        linkCurvature={0.15}
        onNodeClick={(
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          node: any
        ) => {
          if (node.type === "module") {
            const isExpanded = (expandedModules[node.id as string] ?? []).length > 0;
            // Pin module node position to prevent drift during simulation reheat
            node.fx = node.x;
            node.fy = node.y;
            // Unpin after simulation settles
            setTimeout(() => { node.fx = undefined; node.fy = undefined; }, 2000);
            if (isExpanded) {
              onCollapseModule(node.id as string);
              setClickPopover(null);
            } else {
              onExpandModule(node.id as string);
              const fg = fgRef.current;
              if (fg && fg.graph2ScreenCoords) {
                const screen = fg.graph2ScreenCoords(node.x as number, node.y as number);
                setClickPopover({ moduleId: node.id as string, x: screen.x, y: screen.y });
              } else {
                setClickPopover({ moduleId: node.id as string, x: 0, y: 0 });
              }
            }
            onSelect(node.id as string);
          } else {
            onSelect(node.id as string);
          }
        }}
        onNodeHover={(
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          node: any
        ) => setHoveredNode(node ? (node.id as string) : null)}
        cooldownTicks={80}
        warmupTicks={30}
        d3AlphaDecay={0.035}
        d3VelocityDecay={0.4}
        linkCanvasObjectMode={(link: any) => {
          const type = link.type as string;
          if (type === "task" || type === "part_of") return "after";
          return undefined;
        }}
        linkCanvasObject={(link: any, ctx: CanvasRenderingContext2D) => {
          const type = link.type as string;
          if (type !== "task" && type !== "part_of") return;
          const srcId = typeof link.source === "string" ? link.source : (link.source as any)?.id;
          const isTaskLink = type === "task" || String(srcId).startsWith("task:");
          const label = isTaskLink ? "task" : "ref";
          const sx = typeof link.source === "string" ? 0 : (link.source as any)?.x ?? 0;
          const sy = typeof link.source === "string" ? 0 : (link.source as any)?.y ?? 0;
          const tx = typeof link.target === "string" ? 0 : (link.target as any)?.x ?? 0;
          const ty = typeof link.target === "string" ? 0 : (link.target as any)?.y ?? 0;
          const mx = (sx + tx) / 2;
          const my = (sy + ty) / 2;
          ctx.font = "9px -apple-system, sans-serif";
          ctx.fillStyle = isTaskLink ? "rgba(249,115,22,0.7)" : "rgba(255,255,255,0.3)";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(label, mx, my);
        }}
        enableZoomInteraction={true}
        enablePanInteraction={true}
      />

      {/* Click popover on canvas (shown when module is expanded) */}
      {clickPopover && (() => {
        const mod = entityMap.get(clickPopover.moduleId);
        if (!mod) return null;
        return (
          <div
            className="absolute z-50"
            style={{
              left: clickPopover.x,
              top: clickPopover.y,
            }}
          >
            <TypeFilterPopover
              moduleId={clickPopover.moduleId}
              moduleName={mod.name}
              expandedTypes={expandedModules[clickPopover.moduleId] ?? []}
              availableTypes={availableTypesPerModule[clickPopover.moduleId] ?? { document: 0, task: 0, goal: 0, role: 0, project: 0 }}
              onToggle={onToggleModuleType}
              onClose={() => setClickPopover(null)}
            />
          </div>
        );
      })()}

      {/* Legend */}
      <div className="absolute top-3 right-3 bg-[#111113]/90 border border-[#1F1F23] rounded-lg px-3 py-2 flex flex-col gap-1.5">
        {Object.entries(TYPE_COLORS).map(([type, color]) => (
          <div key={type} className="flex items-center gap-2">
            <div
              className="w-2.5 h-2.5 rounded-full"
              style={{ backgroundColor: color }}
            />
            <span className="text-[10px] text-[#A1A1AA]">
              {TYPE_LABELS[type] ?? type}
            </span>
          </div>
        ))}
        <div className="flex items-center gap-2 mt-0.5 pt-1 border-t border-[#1F1F23]">
          <div className="w-2.5 h-2.5 rounded-full border border-red-500 bg-red-500/30" />
          <span className="text-[10px] text-[#A1A1AA]">Has Blindspot</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full border border-dashed border-amber-400/50 bg-transparent" />
          <span className="text-[10px] text-[#A1A1AA]">Draft</span>
        </div>
      </div>

      {/* Hint */}
      <div className="absolute bottom-3 left-3 text-[10px] text-[#FAFAFA]/25">
        Click a module to expand • click again to collapse
      </div>
    </div>
  );
}

// ─── Right Detail Sheet ───

function DetailSheet({
  entity,
  entities,
  blindspots,
  tasks,
  relationships,
  onClose,
  onSelect,
}: {
  entity: Entity;
  entities: Entity[];
  blindspots: Blindspot[];
  tasks: Task[];
  relationships: Relationship[];
  onClose: () => void;
  onSelect: (e: Entity) => void;
}) {
  const entityMap = useMemo(
    () => new Map(entities.map((e) => [e.id, e])),
    [entities]
  );
  const parent = entity.parentId ? entityMap.get(entity.parentId) : null;
  const children = entities.filter((e) => e.parentId === entity.id);
  const relatedBs = blindspots.filter(
    (b) => b.status === "open" && b.relatedEntityIds.includes(entity.id)
  );

  // Tasks: prefer linkedEntities, fallback to text match
  const relatedTasks = useMemo(() => {
    const linked = tasks.filter(
      (t) =>
        t.linkedEntities &&
        t.linkedEntities.length > 0 &&
        t.linkedEntities.includes(entity.id)
    );
    if (linked.length > 0) return linked;
    return inferTasksForEntity(entity, tasks);
  }, [entity, tasks]);

  const days = daysAgo(entity.updatedAt);

  // Connected entities via explicit relationships
  const connectedEntities = useMemo(() => {
    const connected: {
      entity: Entity;
      type: string;
      direction: "out" | "in";
    }[] = [];
    for (const r of relationships) {
      if (r.sourceEntityId === entity.id) {
        const target = entityMap.get(r.targetId);
        if (target)
          connected.push({ entity: target, type: r.type, direction: "out" });
      }
      if (r.targetId === entity.id) {
        const source = entityMap.get(r.sourceEntityId);
        if (source)
          connected.push({
            entity: source,
            type: r.type,
            direction: "in",
          });
      }
    }
    return connected;
  }, [entity.id, relationships, entityMap]);

  // Document entities that are children of this entity
  const childDocs = entities.filter(
    (e) => e.type === "document" && e.parentId === entity.id
  );

  // Tags display helper
  const formatTagValue = (val: string | string[]): string => {
    if (Array.isArray(val)) return val.join(", ");
    return val;
  };

  return (
    <div className="w-[350px] shrink-0 border-l border-[#1F1F23] bg-[#0C0C0E] h-full overflow-y-auto">
      <div className="px-4 pt-4 pb-3 border-b border-[#1F1F23]">
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-2">
            <span
              className="w-2.5 h-2.5 rounded-full"
              style={{
                backgroundColor: TYPE_COLORS[entity.type] ?? "#6366F1",
              }}
            />
            <span className="text-xs text-[#FAFAFA]/55 uppercase tracking-wider">
              {TYPE_LABELS[entity.type] ?? entity.type}
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-[#FAFAFA]/65 hover:text-[#FAFAFA]/90 text-xs cursor-pointer"
          >
            ✕
          </button>
        </div>
        <h3 className="text-base font-bold text-[#FAFAFA]/85">
          {entity.name}
        </h3>
        <p className="text-xs text-[#FAFAFA]/65 mt-1 leading-relaxed">
          {entity.summary}
        </p>
        <div className="flex items-center gap-2 mt-2 text-xs text-[#FAFAFA]/50">
          {!entity.confirmedByUser && (
            <span className="text-orange-400/50 bg-orange-400/8 px-1 py-0.5 rounded">
              Draft
            </span>
          )}
          <span>{days === 0 ? "Today" : `${days}d ago`}</span>
        </div>
      </div>

      {/* Tags */}
      <div className="px-4 py-3 border-b border-[#1F1F23]">
        <div className="text-xs text-[#FAFAFA]/65 uppercase tracking-widest mb-1.5">
          Tags
        </div>
        <div className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-1 text-xs">
          {(["what", "why", "how", "who"] as const).map((k) => (
            <span
              key={k}
              className={`font-medium ${
                k === "what"
                  ? "text-blue-400/60"
                  : k === "why"
                    ? "text-emerald-400/60"
                    : k === "how"
                      ? "text-violet-400/60"
                      : "text-amber-400/60"
              }`}
            >
              {k.charAt(0).toUpperCase() + k.slice(1)}
            </span>
          ))}
          {(["what", "why", "how", "who"] as const).map((k) => (
            <span key={k + "v"} className="text-[#FAFAFA]/65">
              {formatTagValue(entity.tags[k])}
            </span>
          ))}
        </div>
      </div>

      {/* Linked entities */}
      <div className="px-4 py-3 border-b border-[#1F1F23]">
        <div className="text-xs text-[#FAFAFA]/65 uppercase tracking-widest mb-1.5">
          Relations
        </div>
        {parent && (
          <div className="mb-2">
            <div className="text-xs text-[#FAFAFA]/65 mb-0.5">Parent</div>
            <EntityChip entity={parent} onClick={onSelect} />
          </div>
        )}
        {children.length > 0 && (
          <div className="mb-2">
            <div className="text-xs text-[#FAFAFA]/65 mb-0.5">
              Children ({children.length})
            </div>
            <div className="flex flex-wrap gap-1">
              {children.map((c) => (
                <EntityChip key={c.id} entity={c} onClick={onSelect} />
              ))}
            </div>
          </div>
        )}
        {connectedEntities.length > 0 && (
          <div>
            <div className="text-xs text-[#FAFAFA]/65 mb-0.5">
              Dependencies
            </div>
            <div className="space-y-1">
              {connectedEntities.map((c, i) => (
                <div key={i} className="flex items-center gap-1.5">
                  <span className="text-xs text-[#FAFAFA]/65 w-3">
                    {c.direction === "out" ? "\u2192" : "\u2190"}
                  </span>
                  <EntityChip entity={c.entity} onClick={onSelect} />
                  <span className="text-xs text-[#FAFAFA]/10">
                    {c.type.replace("_", " ")}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
        {!parent && children.length === 0 && connectedEntities.length === 0 && (
          <div className="text-xs text-[#FAFAFA]/50">No relations</div>
        )}
      </div>

      {/* Blindspots */}
      {relatedBs.length > 0 && (
        <div className="px-4 py-3 border-b border-[#1F1F23]">
          <div className="text-xs text-[#FAFAFA]/65 uppercase tracking-widest mb-1.5">
            Blindspots ({relatedBs.length})
          </div>
          {relatedBs.map((bs) => (
            <div
              key={bs.id}
              className={`rounded p-2 text-xs mb-1.5 ${
                bs.severity === "red"
                  ? "bg-red-500/8 text-red-300/60"
                  : "bg-amber-500/8 text-amber-300/60"
              }`}
            >
              {bs.description}
              <div className="text-xs opacity-40 mt-0.5">
                {bs.suggestedAction}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Documents & Sources */}
      <div className="px-4 py-3 border-b border-[#1F1F23]">
        <div className="text-xs text-[#FAFAFA]/65 uppercase tracking-widest mb-1.5">
          Documents (
          {childDocs.length + (entity.sources?.length ?? 0)})
        </div>
        {childDocs.length === 0 && (!entity.sources || entity.sources.length === 0) ? (
          <div className="text-xs text-[#FAFAFA]/50">No documents</div>
        ) : (
          <>
            {childDocs.map((d) => (
              <button
                key={d.id}
                onClick={() => onSelect(d)}
                className="flex items-center gap-1.5 py-0.5 text-xs w-full text-left hover:bg-[#FAFAFA]/[0.03] rounded px-1 cursor-pointer"
              >
                <span className="text-cyan-400/60 shrink-0">
                  <svg
                    width="12"
                    height="12"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                  </svg>
                </span>
                <span className="text-[#FAFAFA]/70 truncate">{d.name}</span>
              </button>
            ))}
            {entity.sources?.map((src, i) => (
              <a
                key={i}
                href={src.uri}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 py-0.5 text-xs hover:bg-[#FAFAFA]/[0.03] rounded px-1"
              >
                <SourceIcon type={src.type} />
                <span className="text-[#FAFAFA]/70 truncate flex-1">
                  {src.label}
                </span>
                <span className="text-[#FAFAFA]/25 text-[10px] shrink-0">
                  {src.type}
                </span>
              </a>
            ))}
          </>
        )}
      </div>

      {/* Tasks */}
      <div className="px-4 py-3">
        <div className="text-xs text-[#FAFAFA]/65 uppercase tracking-widest mb-1.5">
          Tasks ({relatedTasks.length})
        </div>
        {relatedTasks.length === 0 ? (
          <div className="text-xs text-[#FAFAFA]/50">No linked tasks</div>
        ) : (
          relatedTasks.map((t) => (
            <div
              key={t.id}
              className="flex items-center gap-1.5 py-0.5 text-xs"
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  t.status === "done"
                    ? "bg-emerald-400"
                    : t.status === "in_progress" || t.status === "review"
                      ? "bg-blue-400"
                      : "bg-[#FAFAFA]/12"
                }`}
              />
              <span className="text-[#FAFAFA]/65 truncate flex-1">
                {t.title}
              </span>
              {t.assignee && (
                <span
                  className={`text-xs px-1 py-0.5 rounded ${
                    ROLE_COLORS[t.assignee] ?? ""
                  }`}
                >
                  {ROLE_LABELS[t.assignee] ?? t.assignee}
                </span>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ─── Task Detail Panel ───

function TaskDetailPanel({
  task,
  onClose,
}: {
  task: Task | null;
  onClose: () => void;
}) {
  if (!task) return null;

  const statusColor =
    task.status === "done" ? "bg-emerald-500/15 text-emerald-300" :
    task.status === "in_progress" ? "bg-blue-500/15 text-blue-300" :
    task.status === "blocked" ? "bg-red-500/15 text-red-300" :
    task.status === "review" ? "bg-violet-500/15 text-violet-300" :
    "bg-[#FAFAFA]/8 text-[#FAFAFA]/55";

  const priorityColor =
    task.priority === "critical" ? "text-red-400" :
    task.priority === "high" ? "text-orange-400" :
    task.priority === "medium" ? "text-amber-400" :
    "text-[#FAFAFA]/40";

  return (
    <div className="w-[350px] shrink-0 border-l border-[#1F1F23] bg-[#0C0C0E] h-full overflow-y-auto">
      <div className="px-4 pt-4 pb-3 border-b border-[#1F1F23]">
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-2">
            <span
              className="w-2.5 h-2.5 rounded-full"
              style={{ backgroundColor: TYPE_COLORS.task }}
            />
            <span className="text-xs text-[#FAFAFA]/55 uppercase tracking-wider">
              Task
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-[#FAFAFA]/65 hover:text-[#FAFAFA]/90 text-xs cursor-pointer"
          >
            ✕
          </button>
        </div>
        <h3 className="text-base font-bold text-[#FAFAFA]/85 leading-snug">
          {task.title}
        </h3>
        <div className="flex items-center gap-2 mt-2">
          <span className={`text-xs px-2 py-0.5 rounded ${statusColor}`}>
            {task.status.replace("_", " ")}
          </span>
          {task.priority && (
            <span className={`text-xs ${priorityColor}`}>
              {task.priority}
            </span>
          )}
        </div>
      </div>

      {task.description && (
        <div className="px-4 py-3 border-b border-[#1F1F23]">
          <div className="text-xs text-[#FAFAFA]/65 uppercase tracking-widest mb-1.5">
            Description
          </div>
          <p className="text-xs text-[#FAFAFA]/65 leading-relaxed">
            {task.description}
          </p>
        </div>
      )}

      {task.assignee && (
        <div className="px-4 py-3 border-b border-[#1F1F23]">
          <div className="text-xs text-[#FAFAFA]/65 uppercase tracking-widest mb-1.5">
            Assignee
          </div>
          <span
            className={`text-xs px-2 py-0.5 rounded ${
              ROLE_COLORS[task.assignee] ?? "bg-[#FAFAFA]/8 text-[#FAFAFA]/55"
            }`}
          >
            {ROLE_LABELS[task.assignee] ?? task.assignee}
          </span>
        </div>
      )}

      {task.acceptanceCriteria && task.acceptanceCriteria.length > 0 && (
        <div className="px-4 py-3">
          <div className="text-xs text-[#FAFAFA]/65 uppercase tracking-widest mb-1.5">
            Acceptance Criteria
          </div>
          <ul className="space-y-1">
            {task.acceptanceCriteria.map((ac, i) => (
              <li key={i} className="flex items-start gap-1.5 text-xs text-[#FAFAFA]/60">
                <span className="text-[#FAFAFA]/30 shrink-0 mt-0.5">·</span>
                <span className="leading-snug">{ac}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ─── Main Page ───

function KnowledgeMapPage() {
  const { partner } = useAuth();
  const [entities, setEntities] = useState<Entity[]>([]);
  const [blindspots, setBlindspots] = useState<Blindspot[]>([]);
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focusProduct, setFocusProduct] = useState<string | null>(null);

  // Layered expand state: moduleId -> expanded L3 types
  const [expandedModules, setExpandedModules] = useState<ExpandedModules>({});

  const handleToggleModuleType = useCallback((moduleId: string, type: ExpandableType) => {
    setExpandedModules((prev) => {
      const current = prev[moduleId] ?? [];
      const next = current.includes(type)
        ? current.filter((t) => t !== type)
        : [...current, type];
      if (next.length === 0) {
        const { [moduleId]: _, ...rest } = prev;
        return rest;
      }
      return { ...prev, [moduleId]: next };
    });
  }, []);

  const handleExpandModule = useCallback((moduleId: string) => {
    setExpandedModules((prev) => ({
      ...prev,
      [moduleId]: DEFAULT_EXPAND_TYPES,
    }));
  }, []);

  const handleCollapseModule = useCallback((moduleId: string) => {
    setExpandedModules((prev) => {
      const { [moduleId]: _, ...rest } = prev;
      return rest;
    });
  }, []);

  useEffect(() => {
    if (!partner) return;

    async function load() {
      try {
        const [fetchedEntities, fetchedBlindspots, fetchedRelationships, fetchedTasks] =
          await Promise.all([
            getAllEntities(),
            getAllBlindspots(),
            getAllRelationships(),
            getTasks(),
          ]);

        setEntities(fetchedEntities);
        setBlindspots(fetchedBlindspots);
        setRelationships(fetchedRelationships);
        setTasks(fetchedTasks);
      } catch (err) {
        console.error("Failed to load data:", err);
      }
      setLoading(false);
    }

    load();
  }, [partner]);

  const entityMap = useMemo(
    () => new Map(entities.map((e) => [e.id, e])),
    [entities]
  );

  const isTaskSelected = selectedId?.startsWith("task:") ?? false;
  const selectedEntity = selectedId && !isTaskSelected ? entityMap.get(selectedId) ?? null : null;

  return (
    <div className="h-screen flex flex-col bg-[#09090B]">
      <AppNav />

      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <span className="text-[#FAFAFA]/40 text-sm">
            Loading knowledge map...
          </span>
        </div>
      ) : (
        <div
          className="flex-1 flex overflow-hidden"
          style={{ height: "calc(100vh - 48px)" }}
        >
          <Sidebar
            entities={entities}
            blindspots={blindspots}
            tasks={tasks}
            relationships={relationships}
            focusProduct={focusProduct}
            setFocusProduct={(id) => {
              setFocusProduct(id);
            }}
            expandedModules={expandedModules}
            onToggleModuleType={handleToggleModuleType}
          />
          <GraphCanvas
            entities={entities}
            relationships={relationships}
            blindspots={blindspots}
            tasks={tasks}
            selectedId={selectedId}
            onSelect={setSelectedId}
            focusProduct={focusProduct}
            expandedModules={expandedModules}
            onToggleModuleType={handleToggleModuleType}
            onExpandModule={handleExpandModule}
            onCollapseModule={handleCollapseModule}
          />
          {selectedId && isTaskSelected ? (
            <TaskDetailPanel
              task={tasks.find((t) => `task:${t.id}` === selectedId) ?? null}
              onClose={() => setSelectedId(null)}
            />
          ) : selectedEntity ? (
            <DetailSheet
              entity={selectedEntity}
              entities={entities}
              blindspots={blindspots}
              tasks={tasks}
              relationships={relationships}
              onClose={() => setSelectedId(null)}
              onSelect={(e) => setSelectedId(e.id)}
            />
          ) : null}
        </div>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <AuthGuard>
      <KnowledgeMapPage />
    </AuthGuard>
  );
}
