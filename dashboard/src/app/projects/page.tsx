"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { AuthGuard } from "@/components/AuthGuard";
import { AppNav } from "@/components/AppNav";
import { EntityTree } from "@/components/EntityTree";
import { BlindspotAlert } from "@/components/BlindspotAlert";
import { PromptSuggestions } from "@/components/PromptSuggestions";
import { ProjectCard } from "@/components/ProjectCard";
import { LoadingState } from "@/components/LoadingState";
import {
  getEntity,
  getChildEntities,
  getBlindspots,
  getProjectEntities,
} from "@/lib/api";
import type { Entity, Blindspot } from "@/types";

// ─── Project List (no ?id=) ───

function ProjectList() {
  const { user, partner } = useAuth();
  const [products, setProducts] = useState<Entity[]>([]);
  const [moduleCounts, setModuleCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user || !partner) return;

    async function load() {
      const token = await user!.getIdToken();
      const entities = await getProjectEntities(token);
      setProducts(entities);
      const counts = await Promise.all(
        entities.map(async (entity) => {
          const children = await getChildEntities(token, entity.id);
          return [entity.id, children.filter((child) => child.type === "module").length] as const;
        })
      );
      setModuleCounts(Object.fromEntries(counts));
      setLoading(false);
    }

    load();
  }, [user, partner]);

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col">
        <AppNav />
        <div className="flex-1 flex items-center justify-center">
          <LoadingState label="Loading projects..." />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      <AppNav />
      <main id="main-content" className="max-w-5xl mx-auto px-6 py-8 w-full">
        <h1 className="text-2xl font-bold text-foreground mb-6">Projects</h1>
        {products.length === 0 ? (
          <p className="text-muted-foreground text-sm">No projects yet.</p>
        ) : (
          <div className="grid gap-3">
            {products.map((p) => (
              <ProjectCard
                key={p.id}
                entity={p}
                moduleCount={moduleCounts[p.id] ?? 0}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

// ─── Project Detail (?id=XXX) ───

interface ProjectData {
  project: Entity;
  children: Entity[];
  blindspots: Blindspot[];
  documentCount: number;
}

function ProjectDetail({ projectId }: { projectId: string }) {
  const { user, partner } = useAuth();
  const router = useRouter();

  const [data, setData] = useState<ProjectData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user || !partner) return;

    async function load() {
      const token = await user!.getIdToken();
      const [project, children, blindspots] = await Promise.all([
        getEntity(token, projectId),
        getChildEntities(token, projectId),
        getBlindspots(token, projectId),
      ]);

      if (!project) {
        router.replace("/projects");
        return;
      }

      const documentCount = children.filter((c) => c.type === "document").length;
      setData({ project, children, blindspots, documentCount });
      setLoading(false);
    }

    load();
  }, [user, partner, projectId, router]);

  if (loading || !data) {
    return (
      <div className="min-h-screen flex flex-col">
        <AppNav />
        <div className="flex-1 flex items-center justify-center">
          <LoadingState label="Loading project details..." />
        </div>
      </div>
    );
  }

  const { project, children, blindspots, documentCount } = data;
  const criticalBlindspots = blindspots.filter((b) => b.severity === "red");
  const allEntities = [project, ...children];

  return (
    <div className="min-h-screen flex flex-col">
      <AppNav />
      <main id="main-content" className="max-w-5xl mx-auto px-6 py-8 space-y-8 w-full">
        {criticalBlindspots.length > 0 && (
          <div className="bg-red-900/30 border border-red-800 rounded-lg p-4">
            <p className="text-sm font-medium text-red-400">
              {criticalBlindspots.length} critical issue{criticalBlindspots.length > 1 ? "s" : ""} detected
            </p>
          </div>
        )}

        <div>
          <h2 className="text-2xl font-bold text-foreground mb-1">
            {project.name}
          </h2>
          <p className="text-muted-foreground mb-4">{project.summary}</p>
          <div className="flex gap-6 text-sm text-muted-foreground">
            <span>{children.filter((c) => c.type === "module").length} modules</span>
            <span>{documentCount} documents</span>
            <span>{blindspots.length} blindspots</span>
          </div>
        </div>

        <div>
          <h3 className="text-lg font-semibold text-white mb-4">
            Modules
          </h3>
          <EntityTree entities={children} allEntities={allEntities} />
        </div>

        {blindspots.length > 0 && (
          <div>
            <h3 className="text-lg font-semibold text-white mb-4">
              Blindspots
            </h3>
            <BlindspotAlert blindspots={blindspots} />
          </div>
        )}

        <PromptSuggestions projectName={project.name} />

        <div className="pt-4">
          <Link href="/projects" className="text-sm text-blue-400 hover:underline">
            Back to projects
          </Link>
        </div>
      </main>
    </div>
  );
}

// ─── Router ───

function ProjectPageInner() {
  const searchParams = useSearchParams();
  const projectId = searchParams.get("id");

  if (!projectId) {
    return <ProjectList />;
  }

  return <ProjectDetail projectId={projectId} />;
}

export default function Page() {
  return (
    <AuthGuard>
      <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><LoadingState label="Loading projects..." /></div>}>
        <ProjectPageInner />
      </Suspense>
    </AuthGuard>
  );
}
