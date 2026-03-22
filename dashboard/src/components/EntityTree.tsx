"use client";

import { useState, useEffect } from "react";
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
  active: "bg-green-100 text-green-700",
  paused: "bg-yellow-100 text-yellow-700",
  planned: "bg-blue-100 text-blue-700",
  completed: "bg-gray-100 text-gray-500",
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
    <div className="border border-gray-200 rounded-lg bg-white">
      <button
        onClick={handleToggle}
        className="w-full text-left p-4 hover:bg-gray-50 transition-colors cursor-pointer"
      >
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-2">
            <span>{typeIcons[entity.type] ?? "📄"}</span>
            <div>
              <h4 className="font-medium text-gray-900">{entity.name}</h4>
              <p className="text-sm text-gray-500 mt-1">{entity.summary}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`text-xs px-2 py-0.5 rounded-full ${statusColors[entity.status] ?? ""}`}
            >
              {entity.status}
            </span>
            <span className="text-gray-400 text-sm">
              {expanded ? "▲" : "▼"}
            </span>
          </div>
        </div>
      </button>

      {expanded && (
        <div className="border-t border-gray-100 p-4 bg-gray-50">
          {loadingRels ? (
            <p className="text-sm text-gray-400">Loading relationships...</p>
          ) : relationships.length === 0 ? (
            <p className="text-sm text-gray-400">No relationships</p>
          ) : (
            <ul className="space-y-2">
              {relationships.map((rel) => (
                <li key={rel.id} className="text-sm text-gray-600 flex items-center gap-2">
                  <span className="text-gray-400">{rel.type.replace(/_/g, " ")}</span>
                  <span className="font-medium">{getEntityName(rel.targetId)}</span>
                  {rel.description && (
                    <span className="text-gray-400">— {rel.description}</span>
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
            <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-3">
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
