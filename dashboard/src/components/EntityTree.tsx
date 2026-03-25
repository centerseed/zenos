"use client";

import { useState } from "react";
import type { Entity, Relationship } from "@/types";
import { getRelationships } from "@/lib/api";
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

function EntityCard({ entity, allEntities }: { entity: Entity; allEntities: Entity[] }) {
  const { user } = useAuth();
  const [expanded, setExpanded] = useState(false);
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [loadingRels, setLoadingRels] = useState(false);

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
