"use client";

import { useState } from "react";
import type { Entity, Relationship } from "@/types";
import { getRelationships } from "@/lib/firestore";

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
  completed: "bg-[#1F1F23] text-[#71717A]",
};

function EntityCard({ entity, allEntities }: { entity: Entity; allEntities: Entity[] }) {
  const [expanded, setExpanded] = useState(false);
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [loadingRels, setLoadingRels] = useState(false);

  const handleToggle = async () => {
    if (!expanded && relationships.length === 0) {
      setLoadingRels(true);
      const rels = await getRelationships(entity.id);
      setRelationships(rels);
      setLoadingRels(false);
    }
    setExpanded(!expanded);
  };

  const getEntityName = (id: string) =>
    allEntities.find((e) => e.id === id)?.name ?? id;

  return (
    <div className="border border-[#1F1F23] rounded-lg bg-[#111113]">
      <button
        onClick={handleToggle}
        className="w-full text-left p-4 hover:bg-[#1F1F23] transition-colors cursor-pointer"
      >
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-2">
            <span>{typeIcons[entity.type] ?? "📄"}</span>
            <div>
              <h4 className="font-medium text-white">{entity.name}</h4>
              <p className="text-sm text-[#71717A] mt-1">{entity.summary}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`text-xs px-2 py-0.5 rounded-full ${statusColors[entity.status] ?? ""}`}
            >
              {entity.status}
            </span>
            <span className="text-[#71717A] text-sm">
              {expanded ? "▲" : "▼"}
            </span>
          </div>
        </div>
      </button>

      {expanded && (
        <div className="border-t border-[#1F1F23] p-4 bg-[#0A0A0B]">
          {loadingRels ? (
            <p className="text-sm text-[#71717A]">Loading relationships...</p>
          ) : relationships.length === 0 ? (
            <p className="text-sm text-[#71717A]">No relationships</p>
          ) : (
            <ul className="space-y-2">
              {relationships.map((rel) => (
                <li key={rel.id} className="text-sm text-[#FAFAFA] flex items-center gap-2">
                  <span className="text-[#71717A]">{rel.type.replace(/_/g, " ")}</span>
                  <span className="font-medium">{getEntityName(rel.targetId)}</span>
                  {rel.description && (
                    <span className="text-[#71717A]">— {rel.description}</span>
                  )}
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
            <h3 className="text-sm font-medium text-[#71717A] uppercase tracking-wide mb-3">
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
