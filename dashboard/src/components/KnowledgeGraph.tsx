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
  onLinkClick?: (sourceId: string, targetId: string) => void;
  onBackgroundClick?: () => void;
  hoveredSidebarNodeId?: string | null;
  focusedNodeId?: string | null;
  selectedPathIds?: string[];
  detailPanelOpen?: boolean;
  variant?: "dark" | "ink";
  showLegend?: boolean;
  /** Override NODE_TYPE_COLORS (e.g. to swap in Zen Ink palette). */
  nodeColorsOverride?: Record<string, string>;
  /** Override label typography, e.g. `500 12px "Helvetica Neue",...`. */
  labelFontFamily?: string;
  /** Blindspot highlight color (e.g. vermillion for Zen Ink). Default red. */
  blindspotColor?: string;
}

interface Palette {
  bg: string;
  nodeBorderIdle: string;
  nodeBorderPath: string;
  labelBg: string;
  labelFg: string;
  labelFgHover: string;
  linkIdle: string;
  linkDim: string;
  linkActiveNeutral: string;
  linkActiveAccent: string;
  linkPath: string;
  arrowIdle: string;
  arrowActiveNeutral: string;
  arrowActiveAccent: string;
  legendBg: string;
  legendBorder: string;
  legendLabel: string;
  tooltipBg: string;
  tooltipBorder: string;
  tooltipTitle: string;
  tooltipMeta: string;
  tooltipBody: string;
}

const DARK_PALETTE: Palette = {
  bg: "#0A0A0B",
  nodeBorderIdle: "rgba(255,255,255,0.15)",
  nodeBorderPath: "rgba(255,255,255,0.92)",
  labelBg: "rgba(10,10,11,0.7)",
  labelFg: "#FAFAFA",
  labelFgHover: "#FFFFFF",
  linkIdle: "rgba(255,255,255,0.12)",
  linkDim: "rgba(255,255,255,0.04)",
  linkActiveNeutral: "rgba(255,255,255,0.6)",
  linkActiveAccent: "rgba(54,225,202,0.72)",
  linkPath: "rgba(255,255,255,0.9)",
  arrowIdle: "rgba(255,255,255,0.25)",
  arrowActiveNeutral: "rgba(255,255,255,0.45)",
  arrowActiveAccent: "rgba(54,225,202,0.72)",
  legendBg: "rgba(17,17,19,0.9)",
  legendBorder: "rgba(255,255,255,0.1)",
  legendLabel: "#A1A1AA",
  tooltipBg: "#111113",
  tooltipBorder: "#333",
  tooltipTitle: "#FAFAFA",
  tooltipMeta: "#71717A",
  tooltipBody: "#A1A1AA",
};

// Zen Ink palette — light paper with ink accents
const INK_PALETTE: Palette = {
  bg: "#F4EFE4", // paper
  nodeBorderIdle: "rgba(20,18,16,0.22)",
  nodeBorderPath: "rgba(182,58,44,0.85)", // vermillion
  labelBg: "rgba(244,239,228,0.88)",
  labelFg: "#2B2722", // ink
  labelFgHover: "#141210",
  linkIdle: "rgba(20,18,16,0.18)",
  linkDim: "rgba(20,18,16,0.06)",
  linkActiveNeutral: "rgba(20,18,16,0.55)",
  linkActiveAccent: "rgba(182,58,44,0.78)",
  linkPath: "rgba(182,58,44,0.9)",
  arrowIdle: "rgba(20,18,16,0.28)",
  arrowActiveNeutral: "rgba(20,18,16,0.5)",
  arrowActiveAccent: "rgba(182,58,44,0.8)",
  legendBg: "rgba(244,239,228,0.92)",
  legendBorder: "rgba(20,18,16,0.14)",
  legendLabel: "#4B443C",
  tooltipBg: "#FAF5E9",
  tooltipBorder: "rgba(20,18,16,0.18)",
  tooltipTitle: "#141210",
  tooltipMeta: "#6B6359",
  tooltipBody: "#2B2722",
};

function getTypeColor(type: string): string {
  return NODE_TYPE_COLORS[type] ?? DEFAULT_NODE_COLOR;
}

function wrapLabelLines(
  ctx: CanvasRenderingContext2D,
  label: string,
  maxWidth: number
): string[] {
  if (!label) return [""];

  const chars = Array.from(label);
  const lines: string[] = [];
  let currentLine = "";

  for (const char of chars) {
    const nextLine = currentLine + char;
    if (currentLine && ctx.measureText(nextLine).width > maxWidth) {
      lines.push(currentLine);
      currentLine = char;
    } else {
      currentLine = nextLine;
    }
  }

  if (currentLine) lines.push(currentLine);
  return lines;
}

export default function KnowledgeGraph({
  entities,
  relationships,
  blindspotsByEntity,
  onNodeClick,
  onLinkClick,
  onBackgroundClick,
  hoveredSidebarNodeId,
  focusedNodeId,
  selectedPathIds = [],
  detailPanelOpen = false,
  variant = "ink",
  showLegend = true,
  nodeColorsOverride,
  labelFontFamily,
  blindspotColor,
}: KnowledgeGraphProps) {
  const palette: Palette = variant === "ink" ? INK_PALETTE : DARK_PALETTE;
  const isInk = variant === "ink";
  const resolvedLabelFont =
    labelFontFamily ?? `-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`;
  const resolvedBlindspot = blindspotColor ?? "#EF4444";
  const getNodeColor = useCallback(
    (type: string): string => {
      if (nodeColorsOverride && nodeColorsOverride[type]) return nodeColorsOverride[type];
      return NODE_TYPE_COLORS[type] ?? DEFAULT_NODE_COLOR;
    },
    [nodeColorsOverride],
  );
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

  // Smooth focus on node; when detail panel is open, bias the node into the left visible area.
  useEffect(() => {
    if (fgRef.current && focusedNodeId) {
      const node = graphData.nodes.find((n) => n.id === focusedNodeId);
      if (node && (node as any).x !== undefined) {
        const targetZoom = 2.15;
        const panelWidth = detailPanelOpen ? Math.min(448, dimensions.width * 0.42) : 0;
        const visibleWidth = dimensions.width - panelWidth;
        const desiredScreenX = panelWidth > 0
          ? Math.max(visibleWidth * 0.42, 220)
          : dimensions.width / 2;
        const xOffsetPx = (dimensions.width / 2) - desiredScreenX;
        const targetCenterX = (node as any).x + xOffsetPx / targetZoom;
        fgRef.current.centerAt(targetCenterX, (node as any).y, 700);
        fgRef.current.zoom(targetZoom, 700);
      }
    }
  }, [focusedNodeId, graphData.nodes, detailPanelOpen, dimensions.width]);

  // Connected node IDs for hover highlighting
  const connectedNodes = useMemo(() => {
    const activeNodeId = hoveredNode || hoveredSidebarNodeId || focusedNodeId;
    if (!activeNodeId) return new Set<string>();
    const connected = new Set<string>();
    connected.add(activeNodeId);
    for (const link of graphData.links) {
      const src = typeof link.source === "string" ? link.source : (link.source as unknown as GraphNode).id;
      const tgt = typeof link.target === "string" ? link.target : (link.target as unknown as GraphNode).id;
      if (src === activeNodeId) connected.add(tgt);
      if (tgt === activeNodeId) connected.add(src);
    }
    return connected;
  }, [hoveredNode, hoveredSidebarNodeId, focusedNodeId, graphData.links]);

  const pathNodeIds = useMemo(() => new Set(selectedPathIds), [selectedPathIds]);
  const pathEdgeKeys = useMemo(() => {
    const keys = new Set<string>();
    for (let i = 0; i < selectedPathIds.length - 1; i += 1) {
      const source = selectedPathIds[i];
      const target = selectedPathIds[i + 1];
      keys.add(`${source}->${target}`);
      keys.add(`${target}->${source}`);
    }
    return keys;
  }, [selectedPathIds]);

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
      const color = getNodeColor(node.type as string);
      const nodeId = node.id as string;
      
      const isHoveredOnGraph = hoveredNode === nodeId;
      const isHoveredOnSidebar = hoveredSidebarNodeId === nodeId;
      const isFocused = focusedNodeId === nodeId;
      const isInPath = pathNodeIds.has(nodeId);
      const isHovered = isHoveredOnGraph || isHoveredOnSidebar || isFocused || isInPath;

      const activeNodeId = hoveredNode || hoveredSidebarNodeId || focusedNodeId;
      const isDimmed = activeNodeId !== null && !connectedNodes.has(nodeId) && !isInPath;

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

      // Outer glow for hovered node / blindspot — dark variant only (Zen Ink has no glow)
      if (!isInk) {
        if (isHovered) {
          ctx.shadowBlur = 25;
          ctx.shadowColor = color;
        } else if (hasBlindspot) {
          ctx.shadowBlur = 20;
          ctx.shadowColor = resolvedBlindspot;
        }
      }

      if (isInk) {
        // Zen Ink node: paper fill + colored hairline stroke + small type dot.
        // Hover/selected: tint fill with color at low alpha + thicker stroke.
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, 2 * Math.PI);
        if (isHovered || isInPath) {
          ctx.fillStyle = color;
          ctx.globalAlpha *= 0.18;
          ctx.fill();
          ctx.globalAlpha = isDimmed ? 0.15 : isPaused ? 0.4 : 1;
        } else {
          ctx.fillStyle = palette.bg; // paper
          ctx.fill();
        }
        ctx.lineWidth = isHovered || isInPath ? 1.6 : 1;
        ctx.strokeStyle = color;
        ctx.stroke();
        // Inner type dot (identity)
        ctx.beginPath();
        ctx.arc(x, y, Math.max(2, radius * 0.32), 0, 2 * Math.PI);
        ctx.fillStyle = color;
        ctx.fill();
      } else {
        // Dark variant (original): solid fill
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, 2 * Math.PI);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.strokeStyle = isInPath ? palette.nodeBorderPath : palette.nodeBorderIdle;
        ctx.lineWidth = isInPath ? 1.8 : 0.5;
        ctx.stroke();
      }

      // Blindspot marker — Zen Ink: small vermillion ring outside node (no glow)
      if (isInk && hasBlindspot) {
        ctx.beginPath();
        ctx.arc(x, y, radius + 3, 0, 2 * Math.PI);
        ctx.strokeStyle = resolvedBlindspot;
        ctx.lineWidth = 0.8;
        ctx.globalAlpha = isDimmed ? 0.25 : 0.75;
        ctx.stroke();
        ctx.globalAlpha = isDimmed ? 0.15 : isPaused ? 0.4 : 1;
      }

      // Reset shadow for label
      ctx.shadowBlur = 0;
      ctx.shadowColor = "transparent";

      // Label — full entity name with wrapping for readability
      const fontSize = Math.max(12 / globalScale, 3);
      ctx.font = `${isInk ? 400 : 500} ${fontSize}px ${resolvedLabelFont}`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      const maxLabelWidth = Math.max(radius * 6, 72 / globalScale);
      const lines = wrapLabelLines(ctx, label, maxLabelWidth);
      const lineHeight = fontSize + 2;
      const blockHeight = lines.length * lineHeight;
      const textY = y + radius + 6;
      const textWidths = lines.map((line) => ctx.measureText(line).width);
      const textWidth = Math.max(...textWidths, 0);

      // Zen Ink: only show label bg on hover; otherwise transparent text on paper.
      if (!isInk || isHovered || isInPath) {
        ctx.fillStyle = palette.labelBg;
        ctx.fillRect(x - textWidth / 2 - 4, textY - 2, textWidth + 8, blockHeight + 4);
      }

      ctx.fillStyle = isHovered ? palette.labelFgHover : palette.labelFg;
      lines.forEach((line, index) => {
        ctx.fillText(line, x, textY + (index * lineHeight) + (lineHeight / 2));
      });

      ctx.restore();
    },
    [hoveredNode, hoveredSidebarNodeId, focusedNodeId, connectedNodes, pathNodeIds, palette, isInk, getNodeColor, resolvedLabelFont, resolvedBlindspot]
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

  const handleLinkClick = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (link: any) => {
      const sourceId = typeof link.source === "string" ? link.source : link.source?.id;
      const targetId = typeof link.target === "string" ? link.target : link.target?.id;
      if (sourceId && targetId) {
        onLinkClick?.(sourceId, targetId);
      }
    },
    [onLinkClick]
  );

  // Link color: highlight connected links on hover
  const linkColor = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (link: any) => {
      const activeNodeId = hoveredNode || hoveredSidebarNodeId || focusedNodeId;
      const src = typeof link.source === "string" ? link.source : link.source?.id;
      const tgt = typeof link.target === "string" ? link.target : link.target?.id;
      if (pathEdgeKeys.has(`${src}->${tgt}`)) return palette.linkPath;
      if (!activeNodeId) return palette.linkIdle;
      if (src === activeNodeId || tgt === activeNodeId) {
        return hoveredNode || hoveredSidebarNodeId
          ? palette.linkActiveNeutral
          : palette.linkActiveAccent;
      }
      return palette.linkDim;
    },
    [hoveredNode, hoveredSidebarNodeId, focusedNodeId, pathEdgeKeys, palette]
  );

  const linkWidth = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (link: any) => {
      const activeNodeId = hoveredNode || hoveredSidebarNodeId || focusedNodeId;
      const src = typeof link.source === "string" ? link.source : link.source?.id;
      const tgt = typeof link.target === "string" ? link.target : link.target?.id;
      if (pathEdgeKeys.has(`${src}->${tgt}`)) return 3;
      if (!activeNodeId) return 1;
      if (src === activeNodeId || tgt === activeNodeId) {
        return hoveredNode || hoveredSidebarNodeId ? 2 : 2.4;
      }
      return 0.5;
    },
    [hoveredNode, hoveredSidebarNodeId, focusedNodeId, pathEdgeKeys]
  );

  // Keep links visually clean; relationship semantics stay in the detail sheet.
  const linkCanvasObject = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (_link: any, _ctx: CanvasRenderingContext2D) => {
      return;
    },
    []
  );

  // Tooltip: show full name + summary on hover
  const nodeLabel = useCallback(
    (node: GraphNode) => {
      const typeLabel = NODE_TYPE_LABELS[node.type] ?? node.type;
      return `<div style="background:${palette.tooltipBg};border:1px solid ${palette.tooltipBorder};border-radius:8px;padding:8px 12px;max-width:280px;font-family:-apple-system,sans-serif;">
        <div style="font-weight:600;font-size:13px;color:${palette.tooltipTitle};margin-bottom:4px;">${node.name}</div>
        <div style="font-size:11px;color:${palette.tooltipMeta};margin-bottom:4px;">${typeLabel} · ${node.status}</div>
        <div style="font-size:11px;color:${palette.tooltipBody};line-height:1.4;">${node.summary.slice(0, 100)}${node.summary.length > 100 ? "…" : ""}</div>
      </div>`;
    },
    [palette]
  );

  const graphA11ySummary = useMemo(() => {
    const totalNodes = graphData.nodes.length;
    const totalLinks = graphData.links.length;
    const blindspotCount = graphData.nodes.filter((node) => node.hasBlindspot).length;
    return `Knowledge graph preview with ${totalNodes} nodes, ${totalLinks} links, and ${blindspotCount} nodes that have blindspots.`;
  }, [graphData]);

  const FG = ForceGraph;

  // Legend items — use overridden palette if provided
  const legendSource = nodeColorsOverride ?? NODE_TYPE_COLORS;
  const legendItems = Object.entries(legendSource).map(([type, color]) => ({
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
        backgroundColor={palette.bg}
        nodeRelSize={6}
        nodeCanvasObject={nodeCanvasObject}
        nodeCanvasObjectMode={() => "replace"}
        nodePointerAreaPaint={nodePointerAreaPaint}
        nodeLabel={nodeLabel}
        linkColor={linkColor}
        linkWidth={linkWidth}
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={1}
        linkDirectionalArrowColor={(link: GraphLink) => {
          const activeNodeId = hoveredNode || hoveredSidebarNodeId || focusedNodeId;
          if (!activeNodeId) return palette.arrowIdle;
          const src = typeof link.source === "string" ? link.source : (link.source as unknown as GraphNode)?.id;
          const tgt = typeof link.target === "string" ? link.target : (link.target as unknown as GraphNode)?.id;
          if (src === activeNodeId || tgt === activeNodeId) {
            return hoveredNode || hoveredSidebarNodeId
              ? palette.arrowActiveNeutral
              : palette.arrowActiveAccent;
          }
          return palette.linkIdle;
        }}
        linkLabel={() => ""}
        linkCanvasObject={linkCanvasObject}
        linkCanvasObjectMode={() => "after"}
        linkCurvature={0.1}
        cooldownTicks={100}
          onNodeClick={handleNodeClick}
          onLinkClick={handleLinkClick}
          onNodeHover={handleNodeHover}
          onBackgroundClick={onBackgroundClick}
        enableZoomInteraction={true}
        enablePanInteraction={true}
        warmupTicks={50}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
      />

      {/* Legend */}
      {showLegend && (
        <div
          className="absolute top-3 right-3 rounded-lg px-3 py-2 flex flex-col gap-1.5"
          style={{
            background: palette.legendBg,
            border: `1px solid ${palette.legendBorder}`,
          }}
        >
          {legendItems.map((item) => (
            <div key={item.type} className="flex items-center gap-2">
              <div
                className="w-2.5 h-2.5 rounded-full"
                style={{ backgroundColor: item.color }}
              />
              <span className="text-[10px]" style={{ color: palette.legendLabel }}>
                {item.label}
              </span>
            </div>
          ))}
          <div
            className="flex items-center gap-2 mt-0.5 pt-1"
            style={{ borderTop: `1px solid ${palette.legendBorder}` }}
          >
            <div className="w-2.5 h-2.5 rounded-full border border-red-500 bg-red-500/30" />
            <span className="text-[10px]" style={{ color: palette.legendLabel }}>
              Has Blindspot
            </span>
          </div>
        </div>
      )}
      </>)}
    </div>
  );
}
