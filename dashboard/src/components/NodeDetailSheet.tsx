"use client";

import { useMemo, useState, useCallback, useEffect } from "react";
import type { Entity, Relationship, Blindspot, Task, QualitySignals } from "@/types";
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
import { updateEntityVisibility } from "@/lib/api";

interface NodeDetailSheetProps {
  entity: Entity | null;
  relationships: Relationship[];
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

const VISIBILITY_LABELS: Record<Entity["visibility"], string> = {
  public: "Public — 所有人可見",
  "role-restricted": "Role-Restricted — 限特定角色",
  restricted: "Restricted — 限特定部門/成員",
  confidential: "Confidential — 僅明確名單",
};

const VISIBILITY_COLORS: Record<Entity["visibility"], string> = {
  public: "bg-green-500/15 text-green-400 border-green-500/30",
  "role-restricted": "bg-blue-500/15 text-blue-400 border-blue-500/30",
  restricted: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  confidential: "bg-red-500/15 text-red-400 border-red-500/30",
};

export default function NodeDetailSheet({
  entity,
  relationships,
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

  // Reset form when entity changes
  useEffect(() => {
    if (entity) {
      setEditingVisibility(false);
      setVisForm({
        visibility: entity.visibility ?? "public",
        visibleToRoles: (entity.visibleToRoles ?? []).join(", "),
        visibleToMembers: (entity.visibleToMembers ?? []).join(", "),
        visibleToDepartments: (entity.visibleToDepartments ?? []).join(", "),
      });
      setVisError(null);
    }
  }, [entity?.id]);

  const handleSaveVisibility = useCallback(async () => {
    if (!entity || !user) return;
    setSavingVis(true);
    setVisError(null);
    try {
      const token = await user.getIdToken();
      const parseList = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);
      await updateEntityVisibility(token, entity.id, {
        visibility: visForm.visibility,
        visible_to_roles: parseList(visForm.visibleToRoles),
        visible_to_members: parseList(visForm.visibleToMembers),
        visible_to_departments: parseList(visForm.visibleToDepartments),
      });
      setEditingVisibility(false);
    } catch (err) {
      setVisError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSavingVis(false);
    }
  }, [entity, user, visForm]);

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

  // Reference Layer: Documents
  const categorizedDocs = useMemo(() => {
    if (!entity) return { specs: [], adrs: [], sources: [] };
    const childDocs = entities.filter((e) => e.parentId === entity.id && e.type === "document");
    const specs = childDocs.filter((d) => d.name.startsWith("SPEC-"));
    const adrs = childDocs.filter((d) => d.name.startsWith("ADR-"));
    const otherDocs = childDocs.filter((d) => !d.name.startsWith("SPEC-") && !d.name.startsWith("ADR-"));
    
    return {
      specs,
      adrs,
      sources: [...(entity.sources || []), ...otherDocs.flatMap(d => d.sources || [])],
    };
  }, [entity, entities]);

  const hasTasks = categorizedTasks.inProgress.length > 0 || categorizedTasks.review.length > 0 || categorizedTasks.backlog.length > 0;
  const hasDocs = categorizedDocs.specs.length > 0 || categorizedDocs.adrs.length > 0 || categorizedDocs.sources.length > 0;

  return (
    <Sheet open={!!entity} onOpenChange={(open) => !open && onClose()}>
      <SheetContent
        side="right"
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
            </div>

            <div className="flex flex-col gap-8 p-6">
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

              {/* Reference Layer (Docs) */}
              <section>
                <h3 className="text-xs font-bold uppercase tracking-widest text-foreground/40 mb-4 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-500" />
                  Reference Layer (Docs)
                </h3>
                {!hasDocs ? (
                  <p className="text-xs text-foreground/30 italic">No reference documents</p>
                ) : (
                  <div className="space-y-4">
                    {[
                      { label: "Core Specs", items: categorizedDocs.specs, type: 'entity' },
                      { label: "Decisions", items: categorizedDocs.adrs, type: 'entity' },
                      { label: "External Sources", items: categorizedDocs.sources, type: 'source' },
                    ].map((group) => group.items.length > 0 && (
                      <div key={group.label}>
                        <div className="text-[10px] font-semibold uppercase mb-2 text-cyan-400/70">
                          {group.label}
                        </div>
                        <div className="space-y-1">
                          {group.items.map((item, idx) => (
                            <div
                              key={group.type === 'entity' ? (item as Entity).id : `src-${idx}`}
                              className="flex items-center gap-2 py-1.5 group cursor-pointer"
                            >
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-foreground/30 group-hover:text-cyan-400 transition-colors">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" />
                              </svg>
                              <span className="text-xs text-foreground/70 group-hover:text-foreground truncate transition-colors">
                                {group.type === 'entity'
                                  ? (item as Entity).name
                                  : (() => {
                                      const src = item as any;
                                      if (src.label && src.label !== src.type) return src.label;
                                      try {
                                        const parts = new URL(src.uri).pathname.split('/').filter(Boolean);
                                        return parts[parts.length - 1] || src.uri;
                                      } catch {
                                        return src.uri || src.label || src.type;
                                      }
                                    })()
                                }
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>

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
                      dir.direction === "out" ? r.sourceEntityId === entity.id : r.targetId === entity.id
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

              {/* Permission — Admin Only */}
              {isAdmin && (
                <section>
                  <h3 className="text-xs font-bold uppercase tracking-widest text-foreground/40 mb-3 flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-violet-500" />
                    Permission
                  </h3>

                  {!editingVisibility ? (
                    /* --- Read-only view --- */
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <Badge className={`text-[10px] border ${VISIBILITY_COLORS[entity.visibility ?? "public"]}`}>
                          {entity.visibility ?? "public"}
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
                          <span className="text-foreground/30">Departments:</span>{" "}
                          {entity.visibleToDepartments?.join(", ")}
                        </div>
                      )}
                      {(entity.visibleToMembers?.length ?? 0) > 0 && (
                        <div className="text-[10px] text-foreground/50">
                          <span className="text-foreground/30">Members:</span>{" "}
                          {entity.visibleToMembers?.join(", ")}
                        </div>
                      )}
                    </div>
                  ) : (
                    /* --- Edit form --- */
                    <div className="rounded-lg border border-border p-3 space-y-3 bg-foreground/[0.02]">
                      <div>
                        <label className="text-[10px] text-foreground/40 block mb-1">Visibility Level</label>
                        <select
                          value={visForm.visibility}
                          onChange={(e) => setVisForm((f) => ({ ...f, visibility: e.target.value as Entity["visibility"] }))}
                          className="w-full bg-card border border-border rounded px-2 py-1.5 text-xs text-foreground"
                        >
                          {(Object.keys(VISIBILITY_LABELS) as Entity["visibility"][]).map((v) => (
                            <option key={v} value={v}>{v} — {VISIBILITY_LABELS[v].split("—")[1]?.trim()}</option>
                          ))}
                        </select>
                      </div>
                      {visForm.visibility !== "public" && (
                        <>
                          <div>
                            <label className="text-[10px] text-foreground/40 block mb-1">Visible to Roles</label>
                            <input
                              value={visForm.visibleToRoles}
                              onChange={(e) => setVisForm((f) => ({ ...f, visibleToRoles: e.target.value }))}
                              placeholder="engineering, finance, hr"
                              className="w-full bg-card border border-border rounded px-2 py-1.5 text-xs text-foreground placeholder:text-foreground/20"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] text-foreground/40 block mb-1">Visible to Departments</label>
                            <input
                              value={visForm.visibleToDepartments}
                              onChange={(e) => setVisForm((f) => ({ ...f, visibleToDepartments: e.target.value }))}
                              placeholder="finance, hr"
                              className="w-full bg-card border border-border rounded px-2 py-1.5 text-xs text-foreground placeholder:text-foreground/20"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] text-foreground/40 block mb-1">Visible to Members (Partner IDs)</label>
                            <input
                              value={visForm.visibleToMembers}
                              onChange={(e) => setVisForm((f) => ({ ...f, visibleToMembers: e.target.value }))}
                              placeholder="partner-id-1, partner-id-2"
                              className="w-full bg-card border border-border rounded px-2 py-1.5 text-xs text-foreground placeholder:text-foreground/20"
                            />
                          </div>
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
                          {savingVis ? "Saving..." : "Save"}
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
