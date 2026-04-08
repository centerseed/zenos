"use client";

import { useState } from "react";
import type { Entity, EntityVisibility, Relationship } from "@/types";
import { getRelationships, updateEntityVisibility } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { LoadingState } from "@/components/LoadingState";

interface EntityTreeProps {
  entities: Entity[];
  allEntities: Entity[];
}

const typeIcons: Record<string, string> = {
  product: "📦",
  module: "🧩",
  goal: "🎯",
  role: "👤",
  project: "📋",
};

const statusColors: Record<string, string> = {
  active: "bg-green-900/50 text-green-400",
  paused: "bg-yellow-900/50 text-yellow-400",
  planned: "bg-blue-900/50 text-blue-400",
  completed: "bg-secondary text-muted-foreground",
};

const VISIBILITY_OPTIONS: EntityVisibility[] = ["public", "restricted", "confidential"];

function normalizeVisibility(visibility: string): EntityVisibility {
  if (visibility === "public" || visibility === "restricted" || visibility === "confidential") {
    return visibility;
  }
  if (visibility === "role-restricted") {
    return "restricted";
  }
  return "public";
}

function EntityCard({ entity, allEntities }: { entity: Entity; allEntities: Entity[] }) {
  const { user, partner } = useAuth();
  const [expanded, setExpanded] = useState(false);
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [loadingRels, setLoadingRels] = useState(false);
  const [savingVisibility, setSavingVisibility] = useState(false);
  const [visibility, setVisibility] = useState<EntityVisibility>(normalizeVisibility(entity.visibility as string));
  const [visibleToRoles, setVisibleToRoles] = useState((entity.visibleToRoles || []).join(", "));
  const [visibleToDepartments, setVisibleToDepartments] = useState(
    (entity.visibleToDepartments || []).join(", ")
  );
  const [visibleToMembers, setVisibleToMembers] = useState((entity.visibleToMembers || []).join(", "));

  const handleToggle = async () => {
    if (!expanded && relationships.length === 0 && user) {
      setLoadingRels(true);
      const token = await user.getIdToken();
      const rels = await getRelationships(token, entity.id);
      setRelationships(rels);
      setLoadingRels(false);
    }
    setExpanded(!expanded);
  };

  const getEntityName = (id: string) =>
    allEntities.find((e) => e.id === id)?.name ?? id;

  const handleSaveVisibility = async () => {
    if (!user || !partner?.isAdmin) return;
    setSavingVisibility(true);
    try {
      const token = await user.getIdToken();
      await updateEntityVisibility(token, entity.id, {
        visibility,
        visible_to_roles: visibleToRoles.split(",").map((v) => v.trim()).filter(Boolean),
        visible_to_departments: visibleToDepartments.split(",").map((v) => v.trim()).filter(Boolean),
        visible_to_members: visibleToMembers.split(",").map((v) => v.trim()).filter(Boolean),
      });
    } catch (err) {
      console.error("Failed to save visibility:", err);
    } finally {
      setSavingVisibility(false);
    }
  };

  return (
    <div className="border border-border rounded-lg bg-card">
      <button
        onClick={handleToggle}
        aria-label={`${expanded ? "Collapse" : "Expand"} ${entity.name}`}
        className="w-full text-left p-4 hover:bg-secondary transition-colors cursor-pointer"
      >
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-2">
            <span>{typeIcons[entity.type] ?? "📄"}</span>
            <div>
              <h4 className="font-medium text-foreground">{entity.name}</h4>
              <p className="text-sm text-muted-foreground mt-1">{entity.summary}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`text-xs px-2 py-0.5 rounded-full ${statusColors[entity.status] ?? ""}`}
            >
              {entity.status}
            </span>
            <span className="text-muted-foreground text-sm">
              {expanded ? "▲" : "▼"}
            </span>
          </div>
        </div>
      </button>

      {expanded && (
        <div className="border-t border-border p-4 bg-background">
          {partner?.isAdmin && (
            <div className="mb-4 rounded-md border border-border p-3">
              <div className="text-xs text-muted-foreground mb-2">Visibility</div>
              <div className="grid gap-2">
                <select
                  aria-label={`Visibility for ${entity.name}`}
                  value={visibility}
                  onChange={(e) => setVisibility(normalizeVisibility(e.target.value))}
                  className="bg-card border border-border rounded px-2 py-1 text-xs text-foreground"
                >
                  {VISIBILITY_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
                <input
                  aria-label={`Workspace roles for ${entity.name}`}
                  value={visibleToRoles}
                  onChange={(e) => setVisibleToRoles(e.target.value)}
                  placeholder="workspace roles (comma-separated)"
                  className="bg-card border border-border rounded px-2 py-1 text-xs text-foreground"
                />
                <input
                  aria-label={`Workspace groups for ${entity.name}`}
                  value={visibleToDepartments}
                  onChange={(e) => setVisibleToDepartments(e.target.value)}
                  placeholder="workspace groups (comma-separated)"
                  className="bg-card border border-border rounded px-2 py-1 text-xs text-foreground"
                />
                <input
                  aria-label={`Authorized members for ${entity.name}`}
                  value={visibleToMembers}
                  onChange={(e) => setVisibleToMembers(e.target.value)}
                  placeholder="authorized members (partner ids, comma-separated)"
                  className="bg-card border border-border rounded px-2 py-1 text-xs text-foreground"
                />
                <button
                  onClick={handleSaveVisibility}
                  disabled={savingVisibility}
                  className="justify-self-start text-xs px-2 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50"
                >
                  {savingVisibility ? "Saving..." : "Save Visibility"}
                </button>
              </div>
            </div>
          )}
          {loadingRels ? (
            <LoadingState label="Loading relationships..." />
          ) : relationships.length === 0 ? (
            <p className="text-sm text-muted-foreground">No relationships</p>
          ) : (
            <ul className="space-y-2">
              {relationships.map((rel, idx) => (
                <li key={rel.id} className="text-sm text-foreground flex items-center gap-2">
                  <span className="text-muted-foreground">{rel.type.replace(/_/g, " ")}</span>
                  <span className="font-medium">{getEntityName(rel.targetId)}</span>
                  {rel.description && (
                    <span className="text-muted-foreground">— {rel.description}</span>
                  )}
                  <span className="sr-only">Relationship {idx + 1}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

export function EntityTree({ entities, allEntities }: EntityTreeProps) {
  const grouped = entities.reduce(
    (acc, e) => {
      const group = acc[e.type] ?? [];
      group.push(e);
      acc[e.type] = group;
      return acc;
    },
    {} as Record<string, Entity[]>
  );

  const typeOrder = ["module", "goal", "role", "project"];

  return (
    <div className="space-y-6">
      {typeOrder.map((type) => {
        const items = grouped[type];
        if (!items || items.length === 0) return null;
        return (
          <div key={type}>
            <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wide mb-3">
              {typeIcons[type]} {type}s ({items.length})
            </h3>
            <div className="space-y-2">
              {items.map((entity) => (
                <EntityCard key={entity.id} entity={entity} allEntities={allEntities} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
