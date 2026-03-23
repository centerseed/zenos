"use client";

import type { Entity, Relationship, Blindspot } from "@/types";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";

interface NodeDetailSheetProps {
  entity: Entity | null;
  relationships: Relationship[];
  blindspots: Blindspot[];
  entities: Entity[];
  onClose: () => void;
}

const TYPE_BADGE_COLORS: Record<string, string> = {
  product: "bg-blue-500/20 text-blue-400",
  module: "bg-purple-500/20 text-purple-400",
  goal: "bg-emerald-500/20 text-emerald-400",
  role: "bg-amber-500/20 text-amber-400",
  project: "bg-indigo-500/20 text-indigo-400",
};

const STATUS_BADGE_COLORS: Record<string, string> = {
  active: "bg-green-500/20 text-green-400",
  paused: "bg-yellow-500/20 text-yellow-400",
  completed: "bg-gray-500/20 text-gray-400",
  planned: "bg-cyan-500/20 text-cyan-400",
};

export default function NodeDetailSheet({
  entity,
  relationships,
  blindspots,
  entities,
  onClose,
}: NodeDetailSheetProps) {
  const entityMap = new Map(entities.map((e) => [e.id, e]));

  // Filter relationships relevant to this entity
  const relevantRels = entity
    ? relationships.filter(
        (r) => r.sourceEntityId === entity.id || r.targetId === entity.id
      )
    : [];

  return (
    <Sheet open={!!entity} onOpenChange={(open) => !open && onClose()}>
      <SheetContent
        side="right"
        className="bg-[#111113] border-[#222] text-[#FAFAFA] overflow-y-auto sm:max-w-md"
      >
        {entity && (
          <>
            <SheetHeader>
              <SheetTitle className="text-2xl font-bold text-[#FAFAFA]">
                {entity.name}
              </SheetTitle>
              <SheetDescription className="flex gap-2 mt-1">
                <Badge
                  className={
                    TYPE_BADGE_COLORS[entity.type] ?? "bg-indigo-500/20 text-indigo-400"
                  }
                >
                  {entity.type}
                </Badge>
                <Badge
                  className={
                    STATUS_BADGE_COLORS[entity.status] ?? "bg-gray-500/20 text-gray-400"
                  }
                >
                  {entity.status}
                </Badge>
                {!entity.confirmedByUser && (
                  <Badge className="bg-orange-500/20 text-orange-400">draft</Badge>
                )}
              </SheetDescription>
            </SheetHeader>

            <div className="flex flex-col gap-5 px-4 pb-6">
              {/* Summary */}
              <section>
                <p className="text-sm text-[#FAFAFA]/70 leading-relaxed">
                  {entity.summary}
                </p>
              </section>

              {/* Four-dimensional tags */}
              <section>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-[#FAFAFA]/40 mb-2">
                  Tags
                </h3>
                <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm">
                  <span className="text-blue-400 font-medium">What</span>
                  <span className="text-[#FAFAFA]/80">{entity.tags.what}</span>
                  <span className="text-emerald-400 font-medium">Why</span>
                  <span className="text-[#FAFAFA]/80">{entity.tags.why}</span>
                  <span className="text-purple-400 font-medium">How</span>
                  <span className="text-[#FAFAFA]/80">{entity.tags.how}</span>
                  <span className="text-amber-400 font-medium">Who</span>
                  <span className="text-[#FAFAFA]/80">{entity.tags.who}</span>
                </div>
              </section>

              {/* Relationships */}
              {relevantRels.length > 0 && (
                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-[#FAFAFA]/40 mb-2">
                    Relationships
                  </h3>
                  <ul className="space-y-1.5">
                    {relevantRels.map((rel) => {
                      const targetId =
                        rel.sourceEntityId === entity.id
                          ? rel.targetId
                          : rel.sourceEntityId;
                      const targetEntity = entityMap.get(targetId);
                      return (
                        <li
                          key={rel.id}
                          className="flex items-center gap-2 text-sm text-[#FAFAFA]/70"
                        >
                          <span className="text-[#FAFAFA]/40 text-xs font-mono">
                            {rel.type}
                          </span>
                          <span className="text-[#FAFAFA]/90">
                            {targetEntity?.name ?? targetId}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              )}

              {/* Blindspots */}
              {blindspots.length > 0 && (
                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-[#FAFAFA]/40 mb-2">
                    Blindspots
                  </h3>
                  <div className="space-y-2">
                    {blindspots.map((bs) => (
                      <div
                        key={bs.id}
                        className={`rounded-lg p-3 text-sm ${
                          bs.severity === "red"
                            ? "bg-red-500/10 border border-red-500/30 text-red-300"
                            : bs.severity === "yellow"
                              ? "bg-yellow-500/10 border border-yellow-500/30 text-yellow-300"
                              : "bg-green-500/10 border border-green-500/30 text-green-300"
                        }`}
                      >
                        <p className="font-medium mb-1">{bs.description}</p>
                        {bs.suggestedAction && (
                          <p className="text-xs opacity-70">
                            Suggested: {bs.suggestedAction}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* Link to project detail for product entities */}
              {entity.type === "product" && (
                <section className="pt-2">
                  <Link
                    href={`/projects?id=${entity.id}`}
                    className="inline-flex items-center gap-1.5 text-sm text-blue-400 hover:text-blue-300 transition-colors"
                  >
                    View project details &rarr;
                  </Link>
                </section>
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
