"use client";

import { useMemo, useState, useCallback, useEffect } from "react";
import type {
  Entity,
  EntityVisibility,
  Source,
  SourceStatus,
  Relationship,
  Blindspot,
  Task,
  QualitySignals,
  Partner,
  ImpactChainHop,
} from "@/types";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";
import {
  NODE_TYPE_COLORS,
  NODE_TYPE_LABELS,
} from "@/lib/constants";
import { useAuth } from "@/lib/auth";
import { getDepartments, getPartners, updateEntityVisibility } from "@/lib/api";

interface NodeDetailSheetProps {
  entity: Entity | null;
  relationships: Relationship[];
  selectedPathEntities?: Entity[];
  selectedPathRelationships?: Relationship[];
  impactChain?: ImpactChainHop[];
  reverseImpactChain?: ImpactChainHop[];
  blindspots: Blindspot[];
  entities: Entity[];
  tasks: Task[];
  qualitySignals?: QualitySignals;
  onClose: () => void;
  onHoverNode?: (nodeId: string | null) => void;
  onFocusNode?: (nodeId: string) => void;
}

const STATUS_BADGE_COLORS: Record<string, string> = {
  active: "bg-green-500/20 text-green-400",
  paused: "bg-yellow-500/20 text-yellow-400",
  completed: "bg-gray-500/20 text-gray-400",
  planned: "bg-cyan-500/20 text-cyan-400",
};

const TASK_STATUS_LABELS: Record<string, string> = {
  in_progress: "In Progress",
  review: "Review",
  todo: "Todo",
};

const VISIBILITY_LABELS: Record<EntityVisibility, string> = {
  public: "Public — 所有人可見",
  restricted: "Restricted — 僅授權的工作區成員可見",
  confidential: "Confidential — 僅 owner 可見",
};

const VISIBILITY_COLORS: Record<EntityVisibility, string> = {
  public: "bg-green-500/15 text-green-400 border-green-500/30",
  restricted: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  confidential: "bg-red-500/15 text-red-400 border-red-500/30",
};

const VISIBILITY_OPTIONS: EntityVisibility[] = ["public", "restricted", "confidential"];

const DEFAULT_ROLE_OPTIONS = [
  "engineering",
  "marketing",
  "product",
  "sales",
  "finance",
  "hr",
  "ops",
];

function normalizeOption(value: string) {
  return value.trim().toLowerCase();
}

// --- ADR-022: Platform icon + source status helpers ---

const PLATFORM_ICONS: Record<string, { icon: string; label: string }> = {
  github: { icon: "GH", label: "GitHub" },
  google_drive: { icon: "GD", label: "Google Drive" },
  notion: { icon: "N", label: "Notion" },
  confluence: { icon: "CF", label: "Confluence" },
  dropbox: { icon: "DB", label: "Dropbox" },
  local: { icon: "LC", label: "Local" },
};

function getPlatformInfo(sourceType: string): { icon: string; label: string } {
  const key = sourceType.toLowerCase().replace(/[- ]/g, "_");
  return PLATFORM_ICONS[key] ?? { icon: sourceType.slice(0, 2).toUpperCase(), label: sourceType };
}

function getSourceLabel(src: { uri: string; label?: string; type?: string }): string {
  if (src.label && src.label !== src.type) return src.label;
  try {
    const parts = src.uri.replace(/[#?].*/, "").split("/").filter(Boolean);
    return parts[parts.length - 1] || src.uri;
  } catch {
    return src.uri || src.label || src.type || "Unknown";
  }
}

function getSourceUrl(src: { uri: string; type?: string }): string | null {
  if (src.uri.startsWith("http://") || src.uri.startsWith("https://")) return src.uri;
  // github: scheme -> attempt to construct a URL
  if (src.type === "github" && !src.uri.startsWith("http")) return null;
  return null;
}

const SOURCE_STATUS_STYLES: Record<string, { className: string; label: string }> = {
  valid: { className: "bg-green-500/15 text-green-400 border-green-500/30", label: "valid" },
  stale: { className: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30", label: "stale" },
  unresolvable: { className: "bg-red-500/15 text-red-400 border-red-500/30", label: "broken" },
};

const DOC_TYPE_LABELS: Record<string, string> = {
  SPEC: "Specs",
  DECISION: "Decisions",
  DESIGN: "Design Docs",
  PLAN: "Plans",
  REPORT: "Reports",
  CONTRACT: "Contracts",
  GUIDE: "Guides",
  MEETING: "Meeting Notes",
  REFERENCE: "References",
  TEST: "Test Docs",
  OTHER: "Other",
};

function normalizeVisibility(visibility: string | undefined | null): EntityVisibility {
  if (visibility === "public" || visibility === "restricted" || visibility === "confidential") {
    return visibility;
  }
  if (visibility === "role-restricted") {
    return "restricted";
  }
  return "public";
}

function parseCommaSeparated(value: string) {
  return Array.from(new Set(value.split(",").map(normalizeOption).filter(Boolean)));
}

function formatMemberLabel(partner: Partner) {
  return partner.displayName?.trim() || partner.email || partner.id;
}

function MultiSelectField({
  label,
  hint,
  options,
  value,
  onToggle,
  manualValue,
  manualLabel,
  manualPlaceholder,
  onManualChange,
}: {
  label: string;
  hint?: string;
  options: Array<{ value: string; label: string; description?: string }>;
  value: string[];
  onToggle: (item: string) => void;
  manualValue?: string;
  manualLabel?: string;
  manualPlaceholder?: string;
  onManualChange?: (value: string) => void;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between gap-3">
        <label className="text-[10px] text-foreground/40 block">{label}</label>
        {hint && <span className="text-[10px] text-foreground/25">{hint}</span>}
      </div>

      {value.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {value.map((item) => {
            const match = options.find((option) => option.value === item);
            return (
              <button
                key={item}
                type="button"
                onClick={() => onToggle(item)}
                className="inline-flex items-center gap-1 rounded-full border border-cyan-400/30 bg-cyan-400/10 px-2 py-1 text-[10px] text-cyan-100 transition-colors hover:border-cyan-300/50 hover:bg-cyan-400/15"
              >
                <span>{match?.label ?? item}</span>
                <span className="text-cyan-200/60">×</span>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="rounded-md border border-dashed border-border/70 px-3 py-2 text-[10px] text-foreground/30">
          No selection
        </div>
      )}

      {options.length > 0 && (
        <div className="grid gap-2 sm:grid-cols-2">
          {options.map((option) => {
            const checked = value.includes(option.value);
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => onToggle(option.value)}
                aria-pressed={checked}
                className={`rounded-lg border px-3 py-2 text-left transition-colors ${
                  checked
                    ? "border-cyan-400/40 bg-cyan-400/10 text-foreground"
                    : "border-border bg-card/60 text-foreground/65 hover:border-foreground/25 hover:text-foreground"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="text-xs font-medium">{option.label}</span>
                  <span
                    className={`inline-flex h-4 w-4 items-center justify-center rounded border text-[10px] ${
                      checked
                        ? "border-cyan-300/60 bg-cyan-300/20 text-cyan-100"
                        : "border-border/80 text-transparent"
                    }`}
                  >
                    ✓
                  </span>
                </div>
                {option.description && (
                  <p className="mt-1 text-[10px] text-foreground/35">{option.description}</p>
                )}
              </button>
            );
          })}
        </div>
      )}

      {onManualChange && (
        <div className="space-y-1">
          <label className="text-[10px] text-foreground/35 block">{manualLabel ?? "Additional values"}</label>
          <input
            value={manualValue ?? ""}
            onChange={(e) => onManualChange(e.target.value)}
            placeholder={manualPlaceholder}
            className="w-full bg-card border border-border rounded px-2 py-1.5 text-xs text-foreground placeholder:text-foreground/20"
          />
        </div>
      )}
    </div>
  );
}

export default function NodeDetailSheet({
  entity,
  relationships,
  selectedPathEntities = [],
  selectedPathRelationships = [],
  impactChain = [],
  reverseImpactChain = [],
  blindspots,
  entities,
  tasks,
  qualitySignals,
  onClose,
  onHoverNode,
  onFocusNode,
}: NodeDetailSheetProps) {
  const { user, partner } = useAuth();
  const isAdmin = partner?.isAdmin ?? false;

  const entityMap = useMemo(() => new Map(entities.map((e) => [e.id, e])), [entities]);

  // --- Visibility editing state ---
  const [editingVisibility, setEditingVisibility] = useState(false);
  const [visForm, setVisForm] = useState({
    visibility: "public" as Entity["visibility"],
    visibleToRoles: "",
    visibleToMembers: "",
    visibleToDepartments: "",
  });
  const [savingVis, setSavingVis] = useState(false);
  const [visError, setVisError] = useState<string | null>(null);
  const [partnerOptions, setPartnerOptions] = useState<Partner[]>([]);
  const [departmentOptions, setDepartmentOptions] = useState<string[]>([]);

  // Reset form when entity changes
  useEffect(() => {
    if (entity) {
      setEditingVisibility(false);
      setVisForm({
        visibility: normalizeVisibility(entity.visibility as string | undefined),
        visibleToRoles: (entity.visibleToRoles ?? []).join(", "),
        visibleToMembers: (entity.visibleToMembers ?? []).join(", "),
        visibleToDepartments: (entity.visibleToDepartments ?? []).join(", "),
      });
      setVisError(null);
    }
  }, [entity?.id]);

  useEffect(() => {
    if (!user || !isAdmin) return;

    let cancelled = false;

    const loadPermissionOptions = async () => {
      try {
        const token = await user.getIdToken();
        const [partnersRes, departmentsRes] = await Promise.allSettled([
          getPartners(token),
          getDepartments(token),
        ]);

        if (cancelled) return;

        if (partnersRes.status === "fulfilled") {
          setPartnerOptions(partnersRes.value);
        }

        if (departmentsRes.status === "fulfilled") {
          setDepartmentOptions(departmentsRes.value);
        }
      } catch (error) {
        console.error("Failed to load permission options:", error);
      }
    };

    void loadPermissionOptions();

    return () => {
      cancelled = true;
    };
  }, [user, isAdmin]);

  const handleSaveVisibility = useCallback(async () => {
    if (!entity || !user) return;
    setSavingVis(true);
    setVisError(null);
    try {
      const token = await user.getIdToken();
      await updateEntityVisibility(token, entity.id, {
        visibility: visForm.visibility,
        visible_to_roles: parseCommaSeparated(visForm.visibleToRoles),
        visible_to_members: parseCommaSeparated(visForm.visibleToMembers),
        visible_to_departments: parseCommaSeparated(visForm.visibleToDepartments),
      });
      setEditingVisibility(false);
    } catch (err) {
      setVisError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSavingVis(false);
    }
  }, [entity, user, visForm]);

  const roleOptions = useMemo(() => {
    const collected = new Set(DEFAULT_ROLE_OPTIONS);
    for (const partnerOption of partnerOptions) {
      for (const role of partnerOption.roles ?? []) {
        const normalized = normalizeOption(role);
        if (normalized) collected.add(normalized);
      }
    }
    for (const role of parseCommaSeparated(visForm.visibleToRoles)) {
      collected.add(role);
    }
    return Array.from(collected)
      .sort()
      .map((role) => ({ value: role, label: role }));
  }, [partnerOptions, visForm.visibleToRoles]);

  const availableDepartmentOptions = useMemo(() => {
    const collected = new Set<string>();
    for (const department of departmentOptions) {
      const normalized = normalizeOption(department);
      if (normalized && normalized !== "all") collected.add(normalized);
    }
    for (const partnerOption of partnerOptions) {
      const normalized = normalizeOption(partnerOption.department ?? "");
      if (normalized && normalized !== "all") collected.add(normalized);
    }
    for (const department of parseCommaSeparated(visForm.visibleToDepartments)) {
      if (department !== "all") collected.add(department);
    }
    return Array.from(collected)
      .sort()
      .map((department) => ({ value: department, label: department }));
  }, [departmentOptions, partnerOptions, visForm.visibleToDepartments]);

  const memberOptions = useMemo(() => {
    const map = new Map<string, { value: string; label: string; description?: string }>();
    for (const partnerOption of partnerOptions) {
      map.set(partnerOption.id, {
        value: partnerOption.id,
        label: formatMemberLabel(partnerOption),
        description: partnerOption.department ? `${partnerOption.department} · ${partnerOption.email}` : partnerOption.email,
      });
    }
    for (const memberId of parseCommaSeparated(visForm.visibleToMembers)) {
      if (!map.has(memberId)) {
        map.set(memberId, { value: memberId, label: memberId });
      }
    }
    return Array.from(map.values()).sort((a, b) => a.label.localeCompare(b.label));
  }, [partnerOptions, visForm.visibleToMembers]);

  const toggleCsvItem = useCallback((field: "visibleToRoles" | "visibleToDepartments" | "visibleToMembers", item: string) => {
    setVisForm((current) => {
      const next = new Set(parseCommaSeparated(current[field]));
      if (next.has(item)) {
        next.delete(item);
      } else {
        next.add(item);
      }
      return {
        ...current,
        [field]: Array.from(next).join(", "),
      };
    });
  }, []);

  const isSearchUnused = useMemo(
    () => entity != null && (qualitySignals?.search_unused ?? []).some((s) => s.entity_id === entity.id),
    [entity, qualitySignals]
  );

  const isSummaryPoor = useMemo(
    () => entity != null && (qualitySignals?.summary_poor ?? []).some((s) => s.entity_id === entity.id),
    [entity, qualitySignals]
  );

  // Filter relationships relevant to this entity
  const relevantRels = useMemo(() => {
    if (!entity) return [];
    return relationships.filter(
      (r) => r.sourceEntityId === entity.id || r.targetId === entity.id
    );
  }, [entity, relationships]);

  const reversePropagationChain = useMemo(() => {
    if (!entity) return [];

    const visited = new Set<string>([entity.id]);
    const queue: Array<{ nodeId: string; depth: number }> = [{ nodeId: entity.id, depth: 0 }];
    const hops: Relationship[] = [];

    while (queue.length > 0) {
      const current = queue.shift();
      if (!current) break;
      if (current.depth >= 5) continue;

      for (const rel of relationships) {
        if (rel.targetId !== current.nodeId) continue;
        if (visited.has(rel.sourceEntityId)) continue;
        visited.add(rel.sourceEntityId);
        hops.push(rel);
        queue.push({ nodeId: rel.sourceEntityId, depth: current.depth + 1 });
      }
    }

    return hops;
  }, [entity, relationships]);

  // Action Layer: Tasks
  const categorizedTasks = useMemo(() => {
    if (!entity) return { inProgress: [], review: [], backlog: [] };
    const related = tasks.filter((t) => t.linkedEntities.includes(entity.id));
    return {
      inProgress: related.filter((t) => t.status === "in_progress"),
      review: related.filter((t) => t.status === "review"),
      backlog: related.filter((t) => t.status === "todo"),
    };
  }, [entity, tasks]);

  // Reference Layer: Documents + Sources (ADR-022 Document Bundle)
  const categorizedDocs = useMemo(() => {
    if (!entity) return { specs: [], adrs: [], sources: [] as Source[], isIndex: false, sourcesByDocType: {} as Record<string, Source[]> };
    const childDocs = entities.filter((e) => e.parentId === entity.id && e.type === "document");
    const specs = childDocs.filter((d) => d.name.startsWith("SPEC-"));
    const adrs = childDocs.filter((d) => d.name.startsWith("ADR-"));
    const otherDocs = childDocs.filter((d) => !d.name.startsWith("SPEC-") && !d.name.startsWith("ADR-"));

    const allSources = [...(entity.sources || []), ...otherDocs.flatMap(d => d.sources || [])];
    const isIndex = entity.docRole === "index";

    // For index-type documents, group sources by doc_type
    const sourcesByDocType: Record<string, typeof allSources> = {};
    if (isIndex) {
      for (const src of allSources) {
        const key = src.doc_type || "OTHER";
        if (!sourcesByDocType[key]) sourcesByDocType[key] = [];
        sourcesByDocType[key].push(src);
      }
    }

    return { specs, adrs, sources: allSources, isIndex, sourcesByDocType };
  }, [entity, entities]);

  const hasTasks = categorizedTasks.inProgress.length > 0 || categorizedTasks.review.length > 0 || categorizedTasks.backlog.length > 0;
  const hasDocs = categorizedDocs.specs.length > 0 || categorizedDocs.adrs.length > 0 || categorizedDocs.sources.length > 0;

  return (
    <Sheet open={!!entity} onOpenChange={(open) => !open && onClose()} modal={false}>
      <SheetContent
        side="right"
        showOverlay={false}
        className="bg-card border-border text-foreground overflow-y-auto sm:max-w-md p-0"
      >
        {entity && (
          <div className="flex flex-col h-full">
            <div className="p-6 border-b border-border bg-card sticky top-0 z-10">
              <SheetHeader className="space-y-1">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge
                      className="text-foreground/80 font-medium"
                      style={{ backgroundColor: `${NODE_TYPE_COLORS[entity.type] ?? "#6366F1"}33` }}
                    >
                      {NODE_TYPE_LABELS[entity.type] ?? entity.type}
                    </Badge>
                    {entity.level != null && (
                      <Badge variant="outline" className="border-foreground/20 text-foreground/50 font-mono text-xs">
                        L{entity.level}
                      </Badge>
                    )}
                    {entity.type === "document" && entity.docRole === "index" && (
                      <Badge variant="outline" className="border-cyan-500/40 text-cyan-400 bg-cyan-500/10 font-mono text-xs">
                        index
                      </Badge>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {!entity.confirmedByUser && (
                      <Badge variant="outline" className="border-orange-500/50 text-orange-400 bg-orange-500/5">draft</Badge>
                    )}
                    <Badge
                      className={STATUS_BADGE_COLORS[entity.status] ?? "bg-gray-500/20 text-gray-400"}
                    >
                      {entity.status}
                    </Badge>
                    {isSearchUnused && (
                      <Badge className="bg-yellow-500/15 text-yellow-400 border border-yellow-500/30">少被引用</Badge>
                    )}
                    {isSummaryPoor && (
                      <Badge className="bg-orange-500/15 text-orange-400 border border-orange-500/30">摘要待改善</Badge>
                    )}
                  </div>
                </div>
                <SheetTitle className="text-2xl font-bold text-foreground pt-2">
                  {entity.name}
                </SheetTitle>
              </SheetHeader>
              <p className="text-sm text-foreground/70 leading-relaxed mt-3">
                {entity.summary}
              </p>
              {entity.type === "document" && entity.changeSummary && (
                <div className="mt-3 rounded-md border border-cyan-500/20 bg-cyan-500/5 p-2.5">
                  <div className="text-[10px] font-semibold text-cyan-400/70 uppercase mb-1">Recent Changes</div>
                  <p className="text-xs text-foreground/60 leading-relaxed">{entity.changeSummary}</p>
                  {entity.summaryUpdatedAt && (
                    <div className="text-[10px] text-foreground/30 mt-1">
                      Updated {entity.summaryUpdatedAt.toLocaleDateString()}
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="flex flex-col gap-8 p-6">
              {(selectedPathEntities.length > 1 || impactChain.length > 0 || reverseImpactChain.length > 0) && (
                <section>
                  <h3 className="text-xs font-bold uppercase tracking-widest text-foreground/40 mb-3 flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-fuchsia-400" />
                    Path Explorer
                  </h3>

                  {selectedPathEntities.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-[10px] font-medium text-fuchsia-300/70 uppercase">Selected Path</div>
                      <div className="flex flex-wrap items-center gap-1.5">
                        {selectedPathEntities.map((pathEntity, index) => (
                          <div key={pathEntity.id} className="contents">
                            <button
                              onClick={() => onFocusNode?.(pathEntity.id)}
                              onMouseEnter={() => onHoverNode?.(pathEntity.id)}
                              onMouseLeave={() => onHoverNode?.(null)}
                              className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-foreground/5 border border-border/40 hover:bg-foreground/10 text-xs text-foreground/75"
                            >
                              <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: NODE_TYPE_COLORS[pathEntity.type] }} />
                              {pathEntity.name}
                            </button>
                            {index < selectedPathEntities.length - 1 && (
                              <span className="text-[10px] text-fuchsia-300/50">
                                {selectedPathRelationships[index]?.verb ?? "→"}
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="space-y-2 mt-4">
                    <div className="text-[10px] font-medium text-emerald-300/70 uppercase">Forward Propagation</div>
                    {impactChain.length === 0 ? (
                      <p className="text-xs text-foreground/30 italic">No downstream propagation chain</p>
                    ) : (
                      <div className="space-y-2">
                        {impactChain.map((hop, index) => {
                          const target = entityMap.get(hop.to_id);
                          return (
                            <div key={`${hop.from_id}-${hop.to_id}-${index}`} className="rounded-md border border-emerald-500/20 bg-emerald-500/5 p-2">
                              <div className="flex flex-wrap items-center gap-1.5 text-xs text-foreground/75">
                                <span className="text-foreground/45">{hop.from_name}</span>
                                <span className="text-[10px] text-emerald-300/60">{hop.verb ?? hop.type}</span>
                                {target ? (
                                  <button
                                    onClick={() => onFocusNode?.(target.id)}
                                    onMouseEnter={() => onHoverNode?.(target.id)}
                                    onMouseLeave={() => onHoverNode?.(null)}
                                    className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-foreground/5 border border-border/40 hover:bg-foreground/10"
                                  >
                                    <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: NODE_TYPE_COLORS[target.type] }} />
                                    {target.name}
                                  </button>
                                ) : (
                                  <span className="italic text-foreground/40">{hop.to_name}</span>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  <div className="space-y-2 mt-4">
                    <div className="text-[10px] font-medium text-blue-300/70 uppercase">Reverse Propagation</div>
                    {reverseImpactChain.length === 0 ? (
                      <p className="text-xs text-foreground/30 italic">No upstream propagation chain</p>
                    ) : (
                      <div className="space-y-2">
                        {reverseImpactChain.map((hop, index) => {
                          const source = entityMap.get(hop.from_id);
                          const target = entityMap.get(hop.to_id);
                          return (
                            <div key={`${hop.from_id}-${hop.to_id}-${index}-reverse`} className="rounded-md border border-blue-500/20 bg-blue-500/5 p-2">
                              <div className="flex flex-wrap items-center gap-1.5 text-xs text-foreground/75">
                                {source ? (
                                  <button
                                    onClick={() => onFocusNode?.(source.id)}
                                    onMouseEnter={() => onHoverNode?.(source.id)}
                                    onMouseLeave={() => onHoverNode?.(null)}
                                    className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-foreground/5 border border-border/40 hover:bg-foreground/10"
                                  >
                                    <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: NODE_TYPE_COLORS[source.type] }} />
                                    {source.name}
                                  </button>
                                ) : (
                                  <span className="italic text-foreground/40">{hop.from_name}</span>
                                )}
                                <span className="text-[10px] text-blue-300/60">{hop.verb ?? hop.type}</span>
                                {target ? (
                                  <button
                                    onClick={() => onFocusNode?.(target.id)}
                                    onMouseEnter={() => onHoverNode?.(target.id)}
                                    onMouseLeave={() => onHoverNode?.(null)}
                                    className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-foreground/5 border border-border/40 hover:bg-foreground/10"
                                  >
                                    <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: NODE_TYPE_COLORS[target.type] }} />
                                    {target.name}
                                  </button>
                                ) : (
                                  <span className="italic text-foreground/40">{hop.to_name}</span>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </section>
              )}

              {/* v2-impacts-debug */}
              {/* Action Layer (Tasks) */}
              <section>
                <h3 className="text-xs font-bold uppercase tracking-widest text-foreground/40 mb-4 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
                  Action Layer (Tasks)
                </h3>
                {!hasTasks ? (
                  <p className="text-xs text-foreground/30 italic">No active tasks</p>
                ) : (
                  <div className="space-y-4">
                    {[
                      { label: "Review", items: categorizedTasks.review, color: "text-amber-400" },
                      { label: "In Progress", items: categorizedTasks.inProgress, color: "text-blue-400" },
                      { label: "Todo", items: categorizedTasks.backlog, color: "text-foreground/40" },
                    ].map((group) => group.items.length > 0 && (
                      <div key={group.label}>
                        <div className={`text-[10px] font-semibold uppercase mb-2 ${group.color}`}>
                          {group.label}
                        </div>
                        <div className="space-y-1.5">
                          {group.items.map((task) => (
                            <div
                              key={task.id}
                              onMouseEnter={() => onHoverNode?.(entity.id)}
                              onMouseLeave={() => onHoverNode?.(null)}
                              className="group flex items-start gap-2 p-2 rounded-md bg-foreground/5 hover:bg-foreground/10 transition-colors border border-transparent hover:border-border/50"
                            >
                              <div className="w-1 h-4 rounded-full mt-0.5 shrink-0 bg-orange-500/40" />
                              <div className="flex-1 min-w-0">
                                <div className="text-xs font-medium text-foreground/80 truncate group-hover:text-foreground transition-colors">
                                  {task.title}
                                </div>
                                {task.assignee && (
                                  <div className="text-[10px] text-foreground/40 mt-0.5">
                                    @{task.assignee}
                                  </div>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Reference Layer (Docs) — ADR-022 Document Bundle */}
              <section>
                <h3 className="text-xs font-bold uppercase tracking-widest text-foreground/40 mb-4 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-500" />
                  Reference Layer (Docs)
                </h3>
                {!hasDocs ? (
                  <p className="text-xs text-foreground/30 italic">No reference documents</p>
                ) : (
                  <div className="space-y-4">
                    {/* Child document entities (Specs, Decisions) */}
                    {[
                      { label: "Core Specs", items: categorizedDocs.specs },
                      { label: "Decisions", items: categorizedDocs.adrs },
                    ].map((group) => group.items.length > 0 && (
                      <div key={group.label}>
                        <div className="text-[10px] font-semibold uppercase mb-2 text-cyan-400/70">
                          {group.label}
                        </div>
                        <div className="space-y-1">
                          {group.items.map((item) => (
                            <div
                              key={item.id}
                              className="flex items-center gap-2 py-1.5 group cursor-pointer"
                            >
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-foreground/30 group-hover:text-cyan-400 transition-colors">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" />
                              </svg>
                              <span className="text-xs text-foreground/70 group-hover:text-foreground truncate transition-colors">
                                {item.name}
                              </span>
                              {item.docRole === "index" && (
                                <Badge variant="outline" className="border-cyan-500/30 text-cyan-400/60 text-[9px] py-0 px-1 h-4">index</Badge>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}

                    {/* Sources — grouped by doc_type for index entities, flat list otherwise */}
                    {categorizedDocs.sources.length > 0 && (
                      categorizedDocs.isIndex ? (
                        // Index mode: group by doc_type
                        <div className="space-y-3">
                          {Object.entries(categorizedDocs.sourcesByDocType)
                            .sort(([a], [b]) => a.localeCompare(b))
                            .map(([docType, sources]) => (
                            <div key={docType}>
                              <div className="text-[10px] font-semibold uppercase mb-2 text-cyan-400/70">
                                {DOC_TYPE_LABELS[docType] ?? docType}
                              </div>
                              <div className="space-y-1">
                                {sources.map((src, idx) => {
                                  const platform = getPlatformInfo(src.type || "");
                                  const url = getSourceUrl(src);
                                  const statusStyle = SOURCE_STATUS_STYLES[src.source_status ?? "valid"];
                                  const isUnresolvable = src.source_status === "unresolvable";
                                  return (
                                    <div
                                      key={src.source_id || `src-${idx}`}
                                      className={`flex items-center gap-2 py-1.5 group ${isUnresolvable ? "opacity-50" : "cursor-pointer"}`}
                                      onClick={() => { if (url && !isUnresolvable) window.open(url, "_blank"); }}
                                    >
                                      <span className="inline-flex items-center justify-center w-5 h-5 rounded text-[8px] font-bold bg-foreground/10 text-foreground/50 shrink-0" title={platform.label}>
                                        {platform.icon}
                                      </span>
                                      <span className={`text-xs truncate transition-colors flex-1 min-w-0 ${isUnresolvable ? "text-foreground/40 line-through" : "text-foreground/70 group-hover:text-foreground"}`}>
                                        {getSourceLabel(src)}
                                      </span>
                                      {src.source_status && src.source_status !== "valid" && statusStyle && (
                                        <Badge variant="outline" className={`text-[9px] py-0 px-1 h-4 border ${statusStyle.className}`}>
                                          {statusStyle.label}
                                        </Badge>
                                      )}
                                      {url && !isUnresolvable && (
                                        <span className="text-[9px] text-foreground/30 group-hover:text-cyan-400 transition-colors whitespace-nowrap" title={`Open in ${platform.label}`}>
                                          Open
                                        </span>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        // Single / flat mode
                        <div>
                          <div className="text-[10px] font-semibold uppercase mb-2 text-cyan-400/70">
                            Sources
                          </div>
                          <div className="space-y-1">
                            {categorizedDocs.sources.map((src, idx) => {
                              const platform = getPlatformInfo(src.type || "");
                              const url = getSourceUrl(src);
                              const statusStyle = SOURCE_STATUS_STYLES[src.source_status ?? "valid"];
                              const isUnresolvable = src.source_status === "unresolvable";
                              return (
                                <div
                                  key={src.source_id || `src-${idx}`}
                                  className={`flex items-center gap-2 py-1.5 group ${isUnresolvable ? "opacity-50" : "cursor-pointer"}`}
                                  onClick={() => { if (url && !isUnresolvable) window.open(url, "_blank"); }}
                                >
                                  <span className="inline-flex items-center justify-center w-5 h-5 rounded text-[8px] font-bold bg-foreground/10 text-foreground/50 shrink-0" title={platform.label}>
                                    {platform.icon}
                                  </span>
                                  <span className={`text-xs truncate transition-colors flex-1 min-w-0 ${isUnresolvable ? "text-foreground/40 line-through" : "text-foreground/70 group-hover:text-foreground"}`}>
                                    {getSourceLabel(src)}
                                  </span>
                                  {src.source_status && src.source_status !== "valid" && statusStyle && (
                                    <Badge variant="outline" className={`text-[9px] py-0 px-1 h-4 border ${statusStyle.className}`}>
                                      {statusStyle.label}
                                    </Badge>
                                  )}
                                  {url && !isUnresolvable && (
                                    <span className="text-[9px] text-foreground/30 group-hover:text-cyan-400 transition-colors whitespace-nowrap" title={`Open in ${platform.label}`}>
                                      Open
                                    </span>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )
                    )}
                  </div>
                )}
              </section>

              {/* Impacts Layer */}
              {(() => {
                const impactsOut = relevantRels.filter(r => r.type === "impacts" && r.sourceEntityId === entity.id);
                const impactsIn = relevantRels.filter(r => r.type === "impacts" && r.targetId === entity.id);
                const impactsDraft = (entity.details as Record<string, unknown> | null)?.layer_decision as Record<string, unknown> | undefined;
                const impactsDraftText = impactsDraft?.impacts_draft as string | undefined;
                if (impactsOut.length === 0 && impactsIn.length === 0 && !impactsDraftText) return null;
                return (
                  <section>
                    <h3 className="text-xs font-bold uppercase tracking-widest text-foreground/40 mb-3 flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                      Impacts
                    </h3>
                    <div className="space-y-3">
                      {impactsOut.map(rel => {
                        const target = entityMap.get(rel.targetId);
                        return (
                          <div key={rel.id} className="rounded-md border border-amber-500/20 bg-amber-500/5 p-2.5 space-y-1.5">
                            <div className="flex items-center gap-1.5">
                              <span className="text-[10px] text-amber-400/60 font-medium">{rel.verb ?? "影響"}</span>
                              {target ? (
                                <button
                                  onClick={() => onFocusNode?.(target.id)}
                                  onMouseEnter={() => onHoverNode?.(target.id)}
                                  onMouseLeave={() => onHoverNode?.(null)}
                                  className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-foreground/5 border border-border/40 hover:border-foreground/20 hover:bg-foreground/10 transition-all text-xs text-foreground/70"
                                >
                                  <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: NODE_TYPE_COLORS[target.type] }} />
                                  {target.name}
                                </button>
                              ) : (
                                <span className="text-xs text-foreground/40 italic">未知節點</span>
                              )}
                            </div>
                            {rel.description && (
                              <p className="text-[11px] text-foreground/60 leading-relaxed">{rel.description}</p>
                            )}
                          </div>
                        );
                      })}
                      {impactsIn.map(rel => {
                        const source = entityMap.get(rel.sourceEntityId);
                        return (
                          <div key={rel.id} className="rounded-md border border-blue-500/20 bg-blue-500/5 p-2.5 space-y-1.5">
                            <div className="flex items-center gap-1.5">
                              {source ? (
                                <button
                                  onClick={() => onFocusNode?.(source.id)}
                                  onMouseEnter={() => onHoverNode?.(source.id)}
                                  onMouseLeave={() => onHoverNode?.(null)}
                                  className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-foreground/5 border border-border/40 hover:border-foreground/20 hover:bg-foreground/10 transition-all text-xs text-foreground/70"
                                >
                                  <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: NODE_TYPE_COLORS[source.type] }} />
                                  {source.name}
                                </button>
                              ) : (
                                <span className="text-xs text-foreground/40 italic">未知節點</span>
                              )}
                              <span className="text-[10px] text-blue-400/60 font-medium">{rel.verb ? `${rel.verb}此節點` : "影響此節點"}</span>
                            </div>
                            {rel.description && (
                              <p className="text-[11px] text-foreground/60 leading-relaxed">{rel.description}</p>
                            )}
                          </div>
                        );
                      })}
                      {impactsDraftText && impactsOut.length === 0 && (
                        <div className="rounded-md border border-foreground/10 bg-foreground/5 p-2.5">
                          <div className="text-[10px] text-foreground/40 font-medium mb-1">草稿 Impacts（尚未建立關聯）</div>
                          <p className="text-[11px] text-foreground/50 leading-relaxed">{impactsDraftText}</p>
                        </div>
                      )}
                    </div>
                  </section>
                );
              })()}

              {/* Dependency Layer */}
              <section>
                <h3 className="text-xs font-bold uppercase tracking-widest text-foreground/40 mb-3">
                  Dependency Layer
                </h3>
                <div className="space-y-3">
                  {[
                    { label: "Depends on", direction: "out", color: "text-blue-400/60" },
                    { label: "Serves", direction: "in", color: "text-emerald-400/60" },
                  ].map((dir) => {
                    const filtered = relevantRels.filter(r =>
                      r.type !== "impacts" &&
                      (dir.direction === "out" ? r.sourceEntityId === entity.id : r.targetId === entity.id)
                    );
                    if (filtered.length === 0) return null;
                    return (
                      <div key={dir.label}>
                        <div className={`text-[10px] font-medium mb-1.5 ${dir.color}`}>{dir.label}</div>
                        <div className="flex flex-wrap gap-1.5">
                          {filtered.map(rel => {
                            const targetId = dir.direction === "out" ? rel.targetId : rel.sourceEntityId;
                            const target = entityMap.get(targetId);
                            if (!target) return null;
                            return (
                              <button
                                key={rel.id}
                                onClick={() => onFocusNode?.(target.id)}
                                onMouseEnter={() => onHoverNode?.(target.id)}
                                onMouseLeave={() => onHoverNode?.(null)}
                                className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-foreground/5 border border-border/40 hover:border-foreground/20 hover:bg-foreground/10 transition-all text-xs text-foreground/70"
                              >
                                <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: NODE_TYPE_COLORS[target.type] }} />
                                {target.name}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>

              {/* Blindspots */}
              {blindspots.length > 0 && (
                <section>
                  <h3 className="text-xs font-bold uppercase tracking-widest text-red-400/60 mb-3">
                    Active Blindspots
                  </h3>
                  <div className="space-y-2">
                    {blindspots.map((bs) => (
                      <div
                        key={bs.id}
                        className={`rounded-lg p-3 text-xs ${
                          bs.severity === "red"
                            ? "bg-red-500/10 border border-red-500/20 text-red-300/80"
                            : "bg-yellow-500/10 border border-yellow-500/20 text-yellow-300/80"
                        }`}
                      >
                        <p className="font-semibold mb-1">{bs.description}</p>
                        {bs.suggestedAction && (
                          <p className="opacity-60 text-[10px] leading-tight">
                            Suggest: {bs.suggestedAction}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* Visibility — Admin Only */}
              {isAdmin && (
                <section>
                  <h3 className="text-xs font-bold uppercase tracking-widest text-foreground/40 mb-3 flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-violet-500" />
                    Visibility
                  </h3>

                  {!editingVisibility ? (
                    /* --- Read-only view --- */
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <Badge className={`text-[10px] border ${VISIBILITY_COLORS[normalizeVisibility(entity.visibility as string | undefined)]}`}>
                          {normalizeVisibility(entity.visibility as string | undefined)}
                        </Badge>
                        <button
                          onClick={() => setEditingVisibility(true)}
                          className="text-[10px] text-foreground/40 hover:text-foreground/70 underline transition-colors"
                        >
                          Edit
                        </button>
                      </div>
                      {(entity.visibleToRoles?.length ?? 0) > 0 && (
                        <div className="text-[10px] text-foreground/50">
                          <span className="text-foreground/30">Roles:</span>{" "}
                          {entity.visibleToRoles?.join(", ")}
                        </div>
                      )}
                      {(entity.visibleToDepartments?.length ?? 0) > 0 && (
                        <div className="text-[10px] text-foreground/50">
                          <span className="text-foreground/30">Groups:</span>{" "}
                          {entity.visibleToDepartments?.join(", ")}
                        </div>
                      )}
                      {(entity.visibleToMembers?.length ?? 0) > 0 && (
                        <div className="text-[10px] text-foreground/50">
                          <span className="text-foreground/30">Partners:</span>{" "}
                          {entity.visibleToMembers?.join(", ")}
                        </div>
                      )}
                    </div>
                  ) : (
                    /* --- Edit form --- */
                    <div className="rounded-lg border border-border p-3 space-y-3 bg-foreground/[0.02]">
                      <div>
                        <label className="text-[10px] text-foreground/40 block mb-1">Visibility level</label>
                        <select
                          value={visForm.visibility}
                          onChange={(e) => setVisForm((f) => ({ ...f, visibility: normalizeVisibility(e.target.value) }))}
                          className="w-full bg-card border border-border rounded px-2 py-1.5 text-xs text-foreground"
                        >
                          {VISIBILITY_OPTIONS.map((v) => (
                            <option key={v} value={v}>{VISIBILITY_LABELS[v]}</option>
                          ))}
                        </select>
                        <p className="mt-1 text-[10px] text-foreground/30">
                          Pick the visibility level first, then scope the workspace audiences below.
                        </p>
                      </div>
                      {visForm.visibility !== "public" && (
                        <>
                          <MultiSelectField
                            label="Workspace roles"
                            hint="Toggle predefined workspace roles"
                            options={roleOptions}
                            value={parseCommaSeparated(visForm.visibleToRoles)}
                            onToggle={(item) => toggleCsvItem("visibleToRoles", item)}
                            manualValue={visForm.visibleToRoles}
                            manualLabel="Additional roles"
                            manualPlaceholder="engineering, finance, hr"
                            onManualChange={(value) => setVisForm((f) => ({ ...f, visibleToRoles: value }))}
                          />
                          <MultiSelectField
                            label="Workspace groups"
                            hint="Pulled from current workspace groups"
                            options={availableDepartmentOptions}
                            value={parseCommaSeparated(visForm.visibleToDepartments)}
                            onToggle={(item) => toggleCsvItem("visibleToDepartments", item)}
                            manualValue={visForm.visibleToDepartments}
                            manualLabel="Additional groups"
                            manualPlaceholder="finance, hr"
                            onManualChange={(value) => setVisForm((f) => ({ ...f, visibleToDepartments: value }))}
                          />
                          <MultiSelectField
                            label="Authorized members"
                            hint="Pick exact workspace partner accounts"
                            options={memberOptions}
                            value={parseCommaSeparated(visForm.visibleToMembers)}
                            onToggle={(item) => toggleCsvItem("visibleToMembers", item)}
                            manualValue={visForm.visibleToMembers}
                            manualLabel="Additional partner IDs"
                            manualPlaceholder="partner-id-1, partner-id-2"
                            onManualChange={(value) => setVisForm((f) => ({ ...f, visibleToMembers: value }))}
                          />
                        </>
                      )}
                      {visError && (
                        <p className="text-[10px] text-red-400">{visError}</p>
                      )}
                      <div className="flex gap-2">
                        <button
                          onClick={handleSaveVisibility}
                          disabled={savingVis}
                          className="text-xs px-3 py-1.5 rounded bg-violet-600 hover:bg-violet-500 text-white disabled:opacity-50 transition-colors"
                        >
                          {savingVis ? "Saving..." : "Save Visibility"}
                        </button>
                        <button
                          onClick={() => {
                            setEditingVisibility(false);
                            setVisError(null);
                          }}
                          className="text-xs px-3 py-1.5 rounded border border-border text-foreground/60 hover:text-foreground hover:border-foreground/30 transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </section>
              )}
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
