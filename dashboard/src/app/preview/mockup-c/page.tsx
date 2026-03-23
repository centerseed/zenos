"use client";

import { useState, useMemo, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import {
  REAL_ENTITIES,
  REAL_BLINDSPOTS,
  REAL_TASKS,
  REAL_RELATIONSHIPS,
  REAL_DOCUMENTS,
  TOTAL_DOCUMENTS,
  getRealStats,
  getDocumentsForEntity,
} from "../realData";
import type { RealEntity, RealTask, RealBlindspot, RealRelationship } from "../realData";

// ─── Mockup C (v5): Sidebar + Relationship Graph + Detail Sheet ───

// ─── Helpers ───

function daysAgo(iso: string): number {
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
}

function inferTasksForEntity(entity: RealEntity, tasks: RealTask[]): RealTask[] {
  const name = entity.name.toLowerCase();
  const keywords = entity.tags.what.toLowerCase().split(/[,、，\s]+/).filter(k => k.length > 2);
  return tasks.filter(t => {
    const title = t.title.toLowerCase();
    return title.includes(name) || keywords.some(kw => title.includes(kw));
  });
}

const TYPE_COLORS: Record<string, string> = {
  product: "#3B82F6",
  module: "#8B5CF6",
  goal: "#10B981",
  role: "#F59E0B",
};

const TYPE_LABELS: Record<string, string> = {
  product: "產品",
  module: "模組",
  goal: "目標",
  role: "角色",
};

const ROLE_COLORS: Record<string, string> = {
  architect: "bg-violet-500/20 text-violet-300",
  developer: "bg-blue-500/20 text-blue-300",
  qa: "bg-emerald-500/20 text-emerald-300",
  pm: "bg-amber-500/20 text-amber-300",
};
const ROLE_LABELS: Record<string, string> = {
  architect: "Arch", developer: "Dev", qa: "QA", pm: "PM",
};

// ─── Entity Chip ───

function EntityChip({ entity, onClick }: { entity: RealEntity; onClick: (e: RealEntity) => void }) {
  const color = TYPE_COLORS[entity.type] ?? "#6366F1";
  return (
    <button
      onClick={(ev) => { ev.stopPropagation(); onClick(entity); }}
      className="inline-flex items-center gap-1.5 rounded-md border border-[#FAFAFA]/8 bg-[#FAFAFA]/[0.03] hover:bg-[#FAFAFA]/[0.07] transition-colors cursor-pointer px-1.5 py-0.5 text-xs"
    >
      <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: color }} />
      <span className="text-[#FAFAFA]/70 truncate max-w-[140px]">{entity.name}</span>
    </button>
  );
}

// ─── Left Sidebar ───

function Sidebar({
  entities, blindspots, tasks, selectedId, filterType, setFilterType,
  focusProduct, setFocusProduct, onSelectEntity,
}: {
  entities: RealEntity[];
  blindspots: RealBlindspot[];
  tasks: RealTask[];
  selectedId: string | null;
  filterType: string | null;
  setFilterType: (t: string | null) => void;
  focusProduct: string | null;
  setFocusProduct: (id: string | null) => void;
  onSelectEntity: (id: string) => void;
}) {
  const stats = getRealStats();
  const products = entities.filter(e => e.type === "product");
  const openBs = blindspots.filter(b => b.status === "open");

  return (
    <div className="w-[230px] shrink-0 border-r border-[#1F1F23] bg-[#0C0C0E] flex flex-col h-full overflow-y-auto">
      {/* Company header */}
      <div className="px-3 pt-4 pb-3 border-b border-[#1F1F23]">
        <h2 className="text-sm font-bold text-[#FAFAFA]">Naruvia</h2>
        <div className="flex items-center gap-2 mt-2">
          <div className="flex-1 h-1 rounded-full bg-[#FAFAFA]/5 overflow-hidden">
            <div className="h-full rounded-full bg-emerald-400/60" style={{ width: `${stats.confirmedRate}%` }} />
          </div>
          <span className="text-xs text-[#FAFAFA]/55">{stats.confirmedRate}%</span>
        </div>
        <div className="text-xs text-[#FAFAFA]/65 mt-1">
          {stats.totalEntities} 節點 · {TOTAL_DOCUMENTS} 文件 · {REAL_RELATIONSHIPS.length} 關係
        </div>
      </div>

      {/* Products — clickable to focus graph */}
      <div className="px-2 py-2 border-b border-[#1F1F23]">
        <div className="text-xs text-[#FAFAFA]/65 uppercase tracking-widest px-1 mb-1.5">產品</div>
        <button
          onClick={() => setFocusProduct(null)}
          className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs transition-colors cursor-pointer mb-0.5 ${
            focusProduct === null ? "bg-[#FAFAFA]/8 text-[#FAFAFA]/70" : "text-[#FAFAFA]/65 hover:bg-[#FAFAFA]/[0.03]"
          }`}
        >
          <span className="w-2 h-2 rounded-full bg-[#FAFAFA]/15" />
          <span className="flex-1 text-left">全公司</span>
        </button>
        {products.map(p => {
          const moduleCount = entities.filter(e => e.parentId === p.id).length;
          const pBs = blindspots.filter(b => b.status === "open" && b.relatedEntityIds.includes(p.id));
          return (
            <button
              key={p.id}
              onClick={() => setFocusProduct(focusProduct === p.id ? null : p.id)}
              className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs transition-colors cursor-pointer ${
                focusProduct === p.id ? "bg-blue-500/15 text-blue-300" : "text-[#FAFAFA]/65 hover:bg-[#FAFAFA]/[0.03]"
              }`}
            >
              <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: TYPE_COLORS.product }} />
              <span className="flex-1 text-left truncate">{p.name}</span>
              <span className="text-xs text-[#FAFAFA]/65">{moduleCount}</span>
              {pBs.length > 0 && <span className="w-1.5 h-1.5 rounded-full bg-red-400 shrink-0" />}
            </button>
          );
        })}
      </div>

      {/* Blindspots */}
      <div className="px-2 py-2 border-b border-[#1F1F23]">
        <div className="text-xs text-[#FAFAFA]/65 uppercase tracking-widest px-1 mb-1">盲點 ({openBs.length})</div>
        <div className="space-y-1 max-h-[140px] overflow-y-auto">
          {openBs.sort((a,b) => (a.severity === "red" ? 0 : 1) - (b.severity === "red" ? 0 : 1)).slice(0, 6).map(bs => (
            <div key={bs.id} className="flex items-start gap-1.5 px-1">
              <span className={`w-1.5 h-1.5 rounded-full shrink-0 mt-1 ${bs.severity === "red" ? "bg-red-400" : "bg-amber-400/40"}`} />
              <span className="text-xs text-[#FAFAFA]/60 leading-snug line-clamp-2">{bs.description}</span>
            </div>
          ))}
          {openBs.length > 6 && <div className="text-xs text-[#FAFAFA]/50 px-1">+{openBs.length - 6} 更多</div>}
        </div>
      </div>

      {/* Tasks */}
      <div className="px-2 py-2 mt-auto">
        <div className="text-xs text-[#FAFAFA]/65 uppercase tracking-widest px-1 mb-1">Tasks ({tasks.length})</div>
        <div className="space-y-0.5 px-1">
          {[
            { l: "完成", c: tasks.filter(t => t.status === "done").length, color: "bg-emerald-400" },
            { l: "進行", c: tasks.filter(t => ["in_progress","review"].includes(t.status)).length, color: "bg-blue-400" },
            { l: "待辦", c: tasks.filter(t => ["backlog","todo"].includes(t.status)).length, color: "bg-[#FAFAFA]/12" },
          ].map(s => (
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
  entities, relationships, blindspots, tasks,
  selectedId, onSelect, filterType, focusProduct,
}: {
  entities: RealEntity[];
  relationships: RealRelationship[];
  blindspots: RealBlindspot[];
  tasks: RealTask[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  filterType: string | null;
  focusProduct: string | null;
}) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [ForceGraph, setForceGraph] = useState<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fgRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ width: 800, height: 600 });
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  useEffect(() => {
    import("react-force-graph-2d").then(mod => setForceGraph(() => mod.default));
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver(entries => {
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
    fgRef.current.d3Force("charge")?.strength(-500).distanceMax(400);
    fgRef.current.d3Force("link")?.distance(100);
    fgRef.current.d3Force("center")?.strength(0.03);
  }, [ForceGraph]);

  const blindspotSet = useMemo(() => {
    const s = new Set<string>();
    for (const b of blindspots) if (b.status === "open") for (const id of b.relatedEntityIds) s.add(id);
    return s;
  }, [blindspots]);

  const entityMap = useMemo(() => new Map(entities.map(e => [e.id, e])), [entities]);

  const graphData = useMemo(() => {
    const entityIds = new Set(entities.map(e => e.id));
    let visibleIds: Set<string>;

    if (focusProduct) {
      // Show only the focused product and its children
      visibleIds = new Set<string>([focusProduct]);
      for (const e of entities) {
        if (e.parentId === focusProduct) visibleIds.add(e.id);
      }
      // Also include entities connected via relationships
      for (const r of relationships) {
        if (visibleIds.has(r.sourceEntityId) && entityIds.has(r.targetId)) visibleIds.add(r.targetId);
        if (visibleIds.has(r.targetId) && entityIds.has(r.sourceEntityId)) visibleIds.add(r.sourceEntityId);
      }
    } else if (filterType) {
      visibleIds = new Set(entities.filter(e => e.type === filterType).map(e => e.id));
      if (filterType === "module") {
        for (const e of entities) {
          if (e.type === "module" && e.parentId && entityIds.has(e.parentId)) visibleIds.add(e.parentId);
        }
      }
    } else {
      visibleIds = new Set(entities.map(e => e.id));
    }

    const nodes = entities
      .filter(e => visibleIds.has(e.id))
      .map(e => ({
        id: e.id,
        name: e.name,
        type: e.type,
        confirmed: e.confirmedByUser,
        hasBlindspot: blindspotSet.has(e.id),
        days: daysAgo(e.updatedAt),
        taskCount: inferTasksForEntity(e, tasks).length,
        val: e.type === "product" ? 20 : e.type === "goal" ? 12 : 8,
      }));

    const nodeIds = new Set(nodes.map(n => n.id));
    // Only non-part_of relationships (part_of is implicit from parentId)
    const links = relationships
      .filter(r => !r.id.startsWith("parent_"))
      .filter(r => nodeIds.has(r.sourceEntityId) && nodeIds.has(r.targetId))
      .map(r => ({ source: r.sourceEntityId, target: r.targetId, type: r.type }));

    // Also add part_of links
    for (const e of entities) {
      if (e.parentId && nodeIds.has(e.id) && nodeIds.has(e.parentId)) {
        links.push({ source: e.id, target: e.parentId, type: "part_of" });
      }
    }

    return { nodes, links };
  }, [entities, relationships, blindspotSet, tasks, filterType, focusProduct]);

  const connectedNodes = useMemo(() => {
    if (!hoveredNode) return new Set<string>();
    const s = new Set<string>([hoveredNode]);
    for (const l of graphData.links) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const src = typeof l.source === "string" ? l.source : (l.source as any).id;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const tgt = typeof l.target === "string" ? l.target : (l.target as any).id;
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
      const color = TYPE_COLORS[node.type as string] ?? "#6366F1";
      const isSelected = selectedId === node.id;
      const isHovered = hoveredNode === node.id;
      const isDimmed = hoveredNode !== null && !connectedNodes.has(node.id as string);
      const days = node.days as number;
      const activity = days <= 1 ? 1 : days <= 3 ? 0.7 : days <= 7 ? 0.45 : 0.2;

      ctx.save();
      if (isDimmed) ctx.globalAlpha = 0.12;

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

      // Confirmation ring
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

      // Task count badge
      if ((node.taskCount as number) > 0 && !isDimmed) {
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

      // Label
      const fontSize = Math.max(14 / globalScale, 4.5);
      ctx.font = `500 ${fontSize}px -apple-system, BlinkMacSystemFont, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "top";

      const label = node.name as string;
      const maxChars = 16;
      const displayLabel = label.length > maxChars ? label.slice(0, maxChars) + "…" : label;
      const textW = ctx.measureText(displayLabel).width;
      const textY = y + r + 4;

      // Text bg
      ctx.fillStyle = "rgba(9,9,11,0.8)";
      ctx.fillRect(x - textW / 2 - 2, textY - 1, textW + 4, fontSize + 3);

      ctx.fillStyle = isSelected || isHovered ? "#FFFFFF" : `rgba(250,250,250,${isDimmed ? 0.12 : 0.9})`;
      ctx.fillText(displayLabel, x, textY);

      ctx.restore();
    },
    [selectedId, hoveredNode, connectedNodes]
  );

  const linkColor = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (link: any) => {
      if (!hoveredNode && !selectedId) return "rgba(255,255,255,0.08)";
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const src = typeof link.source === "string" ? link.source : (link.source as any)?.id;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const tgt = typeof link.target === "string" ? link.target : (link.target as any)?.id;
      const focusId = hoveredNode ?? selectedId;
      if (src === focusId || tgt === focusId) return "rgba(255,255,255,0.45)";
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
      const src = typeof link.source === "string" ? link.source : (link.source as any)?.id;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const tgt = typeof link.target === "string" ? link.target : (link.target as any)?.id;
      if (src === focusId || tgt === focusId) return 1.5;
      return 0.3;
    },
    [hoveredNode, selectedId]
  );

  if (!ForceGraph) {
    return (
      <div ref={containerRef} className="flex-1 flex items-center justify-center bg-[#09090B]">
        <span className="text-[#FAFAFA]/50 text-sm">Loading...</span>
      </div>
    );
  }

  const FG = ForceGraph;
  return (
    <div ref={containerRef} className="flex-1 relative bg-[#09090B] overflow-hidden">
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
          node: any, color: string, ctx: CanvasRenderingContext2D
        ) => {
          const r = Math.sqrt(node.val as number) * 2.8;
          ctx.beginPath();
          ctx.arc(node.x as number, node.y as number, r + 5, 0, 2 * Math.PI);
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
        ) => onSelect(node.id as string)}
        onNodeHover={(
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          node: any
        ) => setHoveredNode(node ? (node.id as string) : null)}
        cooldownTicks={120}
        warmupTicks={60}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
        enableZoomInteraction={true}
        enablePanInteraction={true}
      />
    </div>
  );
}

// ─── Right Detail Sheet ───

function DetailSheet({
  entity, entities, blindspots, tasks, relationships, onClose, onSelect,
}: {
  entity: RealEntity;
  entities: RealEntity[];
  blindspots: RealBlindspot[];
  tasks: RealTask[];
  relationships: RealRelationship[];
  onClose: () => void;
  onSelect: (e: RealEntity) => void;
}) {
  const entityMap = new Map(entities.map(e => [e.id, e]));
  const parent = entity.parentId ? entityMap.get(entity.parentId) : null;
  const children = entities.filter(e => e.parentId === entity.id);
  const relatedBs = blindspots.filter(b => b.status === "open" && b.relatedEntityIds.includes(entity.id));
  const relatedTasks = inferTasksForEntity(entity, tasks);
  const days = daysAgo(entity.updatedAt);

  // Find entities connected via explicit relationships (not part_of)
  const connectedEntities = useMemo(() => {
    const connected: { entity: RealEntity; type: string; direction: "out" | "in" }[] = [];
    for (const r of relationships) {
      if (r.id.startsWith("parent_")) continue;
      if (r.sourceEntityId === entity.id) {
        const target = entityMap.get(r.targetId);
        if (target) connected.push({ entity: target, type: r.type, direction: "out" });
      }
      if (r.targetId === entity.id) {
        const source = entityMap.get(r.sourceEntityId);
        if (source) connected.push({ entity: source, type: r.type, direction: "in" });
      }
    }
    return connected;
  }, [entity.id, relationships, entityMap]);

  return (
    <div className="w-[350px] shrink-0 border-l border-[#1F1F23] bg-[#0C0C0E] h-full overflow-y-auto">
      <div className="px-4 pt-4 pb-3 border-b border-[#1F1F23]">
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: TYPE_COLORS[entity.type] }} />
            <span className="text-xs text-[#FAFAFA]/55 uppercase tracking-wider">{TYPE_LABELS[entity.type]}</span>
          </div>
          <button onClick={onClose} className="text-[#FAFAFA]/65 hover:text-[#FAFAFA]/65 text-xs cursor-pointer">✕</button>
        </div>
        <h3 className="text-base font-bold text-[#FAFAFA]/85">{entity.name}</h3>
        <p className="text-xs text-[#FAFAFA]/65 mt-1 leading-relaxed">{entity.summary}</p>
        <div className="flex items-center gap-2 mt-2 text-xs text-[#FAFAFA]/50">
          {!entity.confirmedByUser && <span className="text-orange-400/50 bg-orange-400/8 px-1 py-0.5 rounded">草稿</span>}
          <span>{days === 0 ? "今天" : `${days}d 前`}更新</span>
        </div>
      </div>

      {/* Tags */}
      <div className="px-4 py-3 border-b border-[#1F1F23]">
        <div className="text-xs text-[#FAFAFA]/65 uppercase tracking-widest mb-1.5">Tags</div>
        <div className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-1 text-xs">
          {(["what","why","how","who"] as const).map(k => (
            <span key={k} className={`font-medium ${k === "what" ? "text-blue-400/60" : k === "why" ? "text-emerald-400/60" : k === "how" ? "text-violet-400/60" : "text-amber-400/60"}`}>
              {k.charAt(0).toUpperCase() + k.slice(1)}
            </span>
          ))}
          {(["what","why","how","who"] as const).map(k => (
            <span key={k+"v"} className="text-[#FAFAFA]/65">{entity.tags[k]}</span>
          ))}
        </div>
      </div>

      {/* Linked entities */}
      <div className="px-4 py-3 border-b border-[#1F1F23]">
        <div className="text-xs text-[#FAFAFA]/65 uppercase tracking-widest mb-1.5">關聯</div>
        {parent && (
          <div className="mb-2">
            <div className="text-xs text-[#FAFAFA]/65 mb-0.5">隸屬</div>
            <EntityChip entity={parent} onClick={onSelect} />
          </div>
        )}
        {children.length > 0 && (
          <div className="mb-2">
            <div className="text-xs text-[#FAFAFA]/65 mb-0.5">子模組 ({children.length})</div>
            <div className="flex flex-wrap gap-1">{children.map(c => <EntityChip key={c.id} entity={c} onClick={onSelect} />)}</div>
          </div>
        )}
        {connectedEntities.length > 0 && (
          <div>
            <div className="text-xs text-[#FAFAFA]/65 mb-0.5">依賴/相關</div>
            <div className="space-y-1">
              {connectedEntities.map((c, i) => (
                <div key={i} className="flex items-center gap-1.5">
                  <span className="text-xs text-[#FAFAFA]/65 w-3">{c.direction === "out" ? "→" : "←"}</span>
                  <EntityChip entity={c.entity} onClick={onSelect} />
                  <span className="text-xs text-[#FAFAFA]/10">{c.type.replace("_", " ")}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        {!parent && children.length === 0 && connectedEntities.length === 0 && (
          <div className="text-xs text-[#FAFAFA]/50">無關聯</div>
        )}
      </div>

      {/* Blindspots */}
      {relatedBs.length > 0 && (
        <div className="px-4 py-3 border-b border-[#1F1F23]">
          <div className="text-xs text-[#FAFAFA]/65 uppercase tracking-widest mb-1.5">盲點 ({relatedBs.length})</div>
          {relatedBs.map(bs => (
            <div key={bs.id} className={`rounded p-2 text-xs mb-1.5 ${bs.severity === "red" ? "bg-red-500/8 text-red-300/60" : "bg-amber-500/8 text-amber-300/60"}`}>
              {bs.description}
              <div className="text-xs opacity-40 mt-0.5">→ {bs.suggestedAction}</div>
            </div>
          ))}
        </div>
      )}

      {/* Known issues */}
      {entity.details?.knownIssues && (
        <div className="px-4 py-3 border-b border-[#1F1F23]">
          <div className="text-xs text-[#FAFAFA]/65 uppercase tracking-widest mb-1.5">已知問題</div>
          {entity.details.knownIssues.map((issue, i) => (
            <div key={i} className="text-xs text-red-300/50 mb-0.5">· {issue}</div>
          ))}
        </div>
      )}

      {/* Documents */}
      {(() => {
        const docs = getDocumentsForEntity(entity.id);
        return (
          <div className="px-4 py-3 border-b border-[#1F1F23]">
            <div className="text-xs text-[#FAFAFA]/65 uppercase tracking-widest mb-1.5">文件 ({docs.length})</div>
            {docs.length === 0 ? (
              <div className="text-xs text-[#FAFAFA]/50">
                無文件連結到此實體
                <div className="text-xs text-amber-400/30 mt-0.5">Firestore 有 {TOTAL_DOCUMENTS} 份文件，但連結的是舊 entity ID</div>
              </div>
            ) : (
              docs.map(d => (
                <div key={d.id} className="flex items-center gap-1.5 py-0.5 text-xs">
                  <span className="text-[#FAFAFA]/65">📄</span>
                  <span className="text-[#FAFAFA]/70 truncate">{d.title}</span>
                </div>
              ))
            )}
          </div>
        );
      })()}

      {/* Tasks */}
      <div className="px-4 py-3">
        <div className="text-xs text-[#FAFAFA]/65 uppercase tracking-widest mb-1.5">任務 ({relatedTasks.length})</div>
        {relatedTasks.length === 0 ? (
          <div className="text-xs text-[#FAFAFA]/50">無任務連結</div>
        ) : (
          relatedTasks.map(t => (
            <div key={t.id} className="flex items-center gap-1.5 py-0.5 text-xs">
              <span className={`w-1.5 h-1.5 rounded-full ${t.status === "done" ? "bg-emerald-400" : t.status === "in_progress" || t.status === "review" ? "bg-blue-400" : "bg-[#FAFAFA]/12"}`} />
              <span className="text-[#FAFAFA]/65 truncate flex-1">{t.title}</span>
              {t.assignee && <span className={`text-xs px-1 py-0.5 rounded ${ROLE_COLORS[t.assignee] ?? ""}`}>{ROLE_LABELS[t.assignee] ?? t.assignee}</span>}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ─── Main ───

export default function MockupC() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string | null>(null);
  const [focusProduct, setFocusProduct] = useState<string | null>(null);
  const selectedEntity = selectedId ? REAL_ENTITIES.find(e => e.id === selectedId) ?? null : null;

  return (
    <div className="h-screen flex flex-col bg-[#09090B]">
      <header className="border-b border-[#1F1F23] shrink-0">
        <div className="px-5 py-2.5 flex items-center justify-between">
          <div className="flex items-center gap-5">
            <h1 className="text-base font-bold text-white tracking-tight">ZenOS</h1>
            <nav className="flex items-center gap-1 text-xs">
              <span className="px-2.5 py-1 rounded bg-white/10 text-white font-medium">全景圖</span>
              <Link href="/tasks" className="px-2.5 py-1 rounded text-[#71717A] hover:text-white hover:bg-white/5">任務</Link>
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/preview" className="text-xs text-[#71717A] hover:text-white">← Preview</Link>
            <span className="text-xs text-[#71717A]">Barry Wu</span>
          </div>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          entities={REAL_ENTITIES}
          blindspots={REAL_BLINDSPOTS}
          tasks={REAL_TASKS}
          selectedId={selectedId}
          filterType={filterType}
          setFilterType={setFilterType}
          focusProduct={focusProduct}
          setFocusProduct={(id) => { setFocusProduct(id); setFilterType(null); }}
          onSelectEntity={setSelectedId}
        />
        <GraphCanvas
          entities={REAL_ENTITIES}
          relationships={REAL_RELATIONSHIPS}
          blindspots={REAL_BLINDSPOTS}
          tasks={REAL_TASKS}
          selectedId={selectedId}
          onSelect={setSelectedId}
          filterType={filterType}
          focusProduct={focusProduct}
        />
        {selectedEntity && (
          <DetailSheet
            entity={selectedEntity}
            entities={REAL_ENTITIES}
            blindspots={REAL_BLINDSPOTS}
            tasks={REAL_TASKS}
            relationships={REAL_RELATIONSHIPS}
            onClose={() => setSelectedId(null)}
            onSelect={e => setSelectedId(e.id)}
          />
        )}
      </div>
    </div>
  );
}
