"use client";

import { useEffect, useLayoutEffect, useRef, useState, useCallback, useMemo } from "react";
import type { Entity, Relationship, Blindspot } from "@/types";
import {
  DEFAULT_NODE_COLOR,
  NODE_TYPE_COLORS,
  NODE_TYPE_LABELS,
} from "@/lib/constants";
import { LoadingState } from "@/components/LoadingState";

interface GraphNode {
  id: string;
  name: string;
  type: Entity["type"];
  status: Entity["status"];
  summary: string;
  hasBlindspot: boolean;
  val: number;
}

interface GraphLink {
  source: string;
  target: string;
  type: Relationship["type"];
}

interface KnowledgeGraphProps {
  entities: Entity[];
  relationships: Relationship[];
  blindspotsByEntity: Map<string, Blindspot[]>;
  onNodeClick: (entity: Entity) => void;
  hoveredSidebarNodeId?: string | null;
  focusedNodeId?: string | null;
}

function getTypeColor(type: string): string {
  return NODE_TYPE_COLORS[type] ?? DEFAULT_NODE_COLOR;
}

export default function KnowledgeGraph({
  entities,
  relationships,
  blindspotsByEntity,
  onNodeClick,
  hoveredSidebarNodeId,
  focusedNodeId,
}: KnowledgeGraphProps) {
  const [mounted, setMounted] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [ForceGraph, setForceGraph] = useState<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fgRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  // Read actual container size before first paint so simulation starts with correct dimensions
  useLayoutEffect(() => {
    if (!containerRef.current) return;
    const { width, height } = containerRef.current.getBoundingClientRect();
    if (width > 0 && height > 0) setDimensions({ width, height });
  }, []);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [, setRenderTrigger] = useState(0);

  // Animation loop for pulse effect
  useEffect(() => {
    if (!hoveredSidebarNodeId) return;
    let animId: number;
    const animate = () => {
      setRenderTrigger((prev) => prev + 1);
      animId = requestAnimationFrame(animate);
    };
    animId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animId);
  }, [hoveredSidebarNodeId]);

  // Dynamic import for SSR safety
  useEffect(() => {
    setMounted(true);
    import("react-force-graph-2d").then((mod) => {
      setForceGraph(() => mod.default);
    });
  }, []);

  // Smooth focus on node
  useEffect(() => {
    if (fgRef.current && focusedNodeId) {
      const node = graphData.nodes.find((n) => n.id === focusedNodeId);
      if (node && (node as any).x !== undefined) {
        fgRef.current.centerAt((node as any).x, (node as any).y, 1000);
        fgRef.current.zoom(2.5, 1000);
      }
    }
  }, [focusedNodeId]);

  // Resize observer — keep canvas in sync when window resizes
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) setDimensions({ width, height });
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Configure force simulation for better spacing
  useEffect(() => {
    if (!fgRef.current) return;
    const fg = fgRef.current;
    // Increase repulsion force for more spacing
    fg.d3Force("charge")?.strength(-400).distanceMax(300);
    // Increase link distance
    fg.d3Force("link")?.distance(80);
    // Center force
    fg.d3Force("center")?.strength(0.03);
  }, [ForceGraph]);

  // Build entity lookup for click handler
  const entityMap = useMemo(() => {
    const map = new Map<string, Entity>();
    for (const e of entities) {
      map.set(e.id, e);
    }
    return map;
  }, [entities]);

  // Build graph data — ONLY SHOW L1/L2
  const graphData = useMemo(() => {
    // Filter out L3 (document/task-like) nodes for structure mode
    const filteredEntities = entities.filter(
      (e) => e.type !== "document" && e.type !== "project"
    );
    const entityIds = new Set(filteredEntities.map((e) => e.id));

    const nodes: GraphNode[] = filteredEntities.map((e) => ({
      id: e.id,
      name: e.name,
      type: e.type,
      status: e.status,
      summary: e.summary,
      hasBlindspot: (blindspotsByEntity.get(e.id)?.length ?? 0) > 0,
      val: e.type === "product" ? 16 : e.type === "goal" ? 10 : 8,
    }));

    const relLinks: GraphLink[] = relationships
      .filter((r) => entityIds.has(r.sourceEntityId) && entityIds.has(r.targetId))
      .map((r) => ({
        source: r.sourceEntityId,
        target: r.targetId,
        type: r.type,
      }));

    // Also draw parent→child edges from parentId hierarchy
    const parentLinks: GraphLink[] = filteredEntities
      .filter((e) => e.parentId && entityIds.has(e.parentId))
      .map((e) => ({
        source: e.parentId!,
        target: e.id,
        type: "contains" as Relationship["type"],
      }));

    // Deduplicate: skip parentId edges that are already covered by a relationship record
    const relPairs = new Set(relLinks.map((l) => `${l.source}::${l.target}`));
    const dedupedParentLinks = parentLinks.filter(
      (l) => !relPairs.has(`${l.source}::${l.target}`) && !relPairs.has(`${l.target}::${l.source}`)
    );

    const links = [...relLinks, ...dedupedParentLinks];

    return { nodes, links };
  }, [entities, relationships, blindspotsByEntity]);

  // Connected node IDs for hover highlighting
  const connectedNodes = useMemo(() => {
    const currentHover = hoveredNode || hoveredSidebarNodeId;
    if (!currentHover) return new Set<string>();
    const connected = new Set<string>();
    connected.add(currentHover);
    for (const link of graphData.links) {
      const src = typeof link.source === "string" ? link.source : (link.source as unknown as GraphNode).id;
      const tgt = typeof link.target === "string" ? link.target : (link.target as unknown as GraphNode).id;
      if (src === currentHover) connected.add(tgt);
      if (tgt === currentHover) connected.add(src);
    }
    return connected;
  }, [hoveredNode, hoveredSidebarNodeId, graphData.links]);

  // Node canvas renderer
  const nodeCanvasObject = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const label = node.name as string;
      const radius = Math.sqrt(node.val as number) * 2.5;
      const x = node.x as number;
      const y = node.y as number;
      const isPaused = node.status === "paused";
      const hasBlindspot = node.hasBlindspot as boolean;
      const color = getTypeColor(node.type as string);
      const nodeId = node.id as string;
      
      const isHoveredOnGraph = hoveredNode === nodeId;
      const isHoveredOnSidebar = hoveredSidebarNodeId === nodeId;
      const isHovered = isHoveredOnGraph || isHoveredOnSidebar;
      
      const activeHoverId = hoveredNode || hoveredSidebarNodeId;
      const isDimmed = activeHoverId !== null && !connectedNodes.has(nodeId);

      ctx.save();

      if (isPaused || isDimmed) {
        ctx.globalAlpha = isDimmed ? 0.15 : 0.4;
      }

      // Pulse Effect for sidebar hover
      if (isHoveredOnSidebar) {
        const t = (Date.now() % 2000) / 2000; // 0..1 loop every 2s
        const pulseR = radius * (1 + t * 2.5);
        ctx.beginPath();
        ctx.arc(x, y, pulseR, 0, 2 * Math.PI);
        ctx.strokeStyle = color;
        ctx.lineWidth = 2 / globalScale;
        ctx.globalAlpha = (1 - t) * 0.6;
        ctx.stroke();
      }

      // Outer glow for hovered node
      if (isHovered) {
        ctx.shadowBlur = 25;
        ctx.shadowColor = color;
      }
      // Blindspot glow
      else if (hasBlindspot) {
        ctx.shadowBlur = 20;
        ctx.shadowColor = "#EF4444";
      }

      // Draw node circle
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();

      // Subtle border ring
      ctx.strokeStyle = "rgba(255,255,255,0.15)";
      ctx.lineWidth = 0.5;
      ctx.stroke();

      // Reset shadow for label
      ctx.shadowBlur = 0;
      ctx.shadowColor = "transparent";

      // Label — larger font, with background for readability
      const fontSize = Math.max(12 / globalScale, 3);
      ctx.font = `500 ${fontSize}px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "top";

      // Truncate long names
      const maxChars = 10;
      const displayLabel = label.length > maxChars ? label.slice(0, maxChars) + "…" : label;

      // Text background for readability
      const textWidth = ctx.measureText(displayLabel).width;
      const textY = y + radius + 3;
      ctx.fillStyle = "rgba(10,10,11,0.7)";
      ctx.fillRect(x - textWidth / 2 - 2, textY - 1, textWidth + 4, fontSize + 2);

      ctx.fillStyle = isHovered ? "#FFFFFF" : "#FAFAFA";
      ctx.fillText(displayLabel, x, textY);

      ctx.restore();
    },
    [hoveredNode, hoveredSidebarNodeId, connectedNodes]
  );

  // Pointer area for click detection
  const nodePointerAreaPaint = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (node: any, paintColor: string, ctx: CanvasRenderingContext2D) => {
      const radius = Math.sqrt(node.val as number) * 2.5;
      ctx.beginPath();
      ctx.arc(node.x as number, node.y as number, radius + 4, 0, 2 * Math.PI);
      ctx.fillStyle = paintColor;
      ctx.fill();
    },
    []
  );

  const handleNodeClick = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (node: any) => {
      const entity = entityMap.get(node.id as string);
      if (entity) {
        onNodeClick(entity);
      }
    },
    [entityMap, onNodeClick]
  );

  const handleNodeHover = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (node: any) => {
      setHoveredNode(node ? (node.id as string) : null);
    },
    []
  );

  // Link color: highlight connected links on hover
  const linkColor = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (link: any) => {
      if (!hoveredNode) return "rgba(255,255,255,0.12)";
      const src = typeof link.source === "string" ? link.source : link.source?.id;
      const tgt = typeof link.target === "string" ? link.target : link.target?.id;
      if (src === hoveredNode || tgt === hoveredNode) {
        return "rgba(255,255,255,0.6)";
      }
      return "rgba(255,255,255,0.04)";
    },
    [hoveredNode]
  );

  const linkWidth = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (link: any) => {
      if (!hoveredNode) return 1;
      const src = typeof link.source === "string" ? link.source : link.source?.id;
      const tgt = typeof link.target === "string" ? link.target : link.target?.id;
      if (src === hoveredNode || tgt === hoveredNode) return 2;
      return 0.5;
    },
    [hoveredNode]
  );

  // Tooltip: show full name + summary on hover
  const nodeLabel = useCallback(
    (node: GraphNode) => {
      const typeLabel = NODE_TYPE_LABELS[node.type] ?? node.type;
      return `<div style="background:#111113;border:1px solid #333;border-radius:8px;padding:8px 12px;max-width:280px;font-family:-apple-system,sans-serif;">
        <div style="font-weight:600;font-size:13px;color:#FAFAFA;margin-bottom:4px;">${node.name}</div>
        <div style="font-size:11px;color:#71717A;margin-bottom:4px;">${typeLabel} · ${node.status}</div>
        <div style="font-size:11px;color:#A1A1AA;line-height:1.4;">${node.summary.slice(0, 100)}${node.summary.length > 100 ? "…" : ""}</div>
      </div>`;
    },
    []
  );

  const graphA11ySummary = useMemo(() => {
    const totalNodes = graphData.nodes.length;
    const totalLinks = graphData.links.length;
    const blindspotCount = graphData.nodes.filter((node) => node.hasBlindspot).length;
    return `Knowledge graph preview with ${totalNodes} nodes, ${totalLinks} links, and ${blindspotCount} nodes that have blindspots.`;
  }, [graphData]);

  const FG = ForceGraph;

  // Legend items
  const legendItems = Object.entries(NODE_TYPE_COLORS).map(([type, color]) => ({
    type,
    color,
    label: NODE_TYPE_LABELS[type] ?? type,
  }));

  return (
    <div
      ref={containerRef}
      className="w-full h-full relative"
      role="img"
      aria-label={graphA11ySummary}
      aria-describedby="knowledge-graph-preview-summary"
    >
      {(!mounted || !FG || dimensions.width === 0) && (
        <LoadingState variant="graph" label="Loading graph..." />
      )}
      {mounted && FG && dimensions.width > 0 && (<>
      <p id="knowledge-graph-preview-summary" className="sr-only">
        {graphA11ySummary}
      </p>
      <FG
        ref={fgRef}
        graphData={graphData}
        width={dimensions.width}
        height={dimensions.height}
        backgroundColor="#0A0A0B"
        nodeRelSize={6}
        nodeCanvasObject={nodeCanvasObject}
        nodeCanvasObjectMode={() => "replace"}
        nodePointerAreaPaint={nodePointerAreaPaint}
        nodeLabel={nodeLabel}
        linkColor={linkColor}
        linkWidth={linkWidth}
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={1}
        linkDirectionalArrowColor={() => "rgba(255,255,255,0.25)"}
        linkLabel={(link: GraphLink) => {
          const labels: Record<string, string> = {
            part_of: "屬於",
            depends_on: "依賴",
            serves: "服務",
            owned_by: "負責人",
            blocks: "阻塞",
            related_to: "相關",
          };
          return labels[link.type] ?? link.type;
        }}
        linkCurvature={0.1}
        cooldownTicks={100}
        onNodeClick={handleNodeClick}
        onNodeHover={handleNodeHover}
        enableZoomInteraction={true}
        enablePanInteraction={true}
        warmupTicks={50}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
      />

      {/* Legend */}
      <div className="absolute top-3 right-3 bg-card/90 border border-border rounded-lg px-3 py-2 flex flex-col gap-1.5">
        {legendItems.map((item) => (
          <div key={item.type} className="flex items-center gap-2">
            <div
              className="w-2.5 h-2.5 rounded-full"
              style={{ backgroundColor: item.color }}
            />
            <span className="text-[10px] text-muted-foreground">{item.label}</span>
          </div>
        ))}
        <div className="flex items-center gap-2 mt-0.5 pt-1 border-t border-border">
          <div className="w-2.5 h-2.5 rounded-full border border-red-500 bg-red-500/30" />
          <span className="text-[10px] text-muted-foreground">Has Blindspot</span>
        </div>
      </div>
      </>)}
    </div>
  );
}
