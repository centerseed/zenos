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
import {
  getEntity,
  getChildEntities,
  getBlindspots,
  countDocuments,
  getProjectEntities,
} from "@/lib/firestore";
import type { Entity, Blindspot } from "@/types";

// ─── Project List (no ?id=) ───

function ProjectList() {
  const { partner } = useAuth();
  const [products, setProducts] = useState<Entity[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!partner) return;
    getProjectEntities().then((entities) => {
      setProducts(entities);
      setLoading(false);
    });
  }, [partner]);

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col">
        <AppNav />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-[#71717A]">Loading...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      <AppNav />
      <main className="max-w-5xl mx-auto px-6 py-8 w-full">
        <h1 className="text-2xl font-bold text-white mb-6">Projects</h1>
        {products.length === 0 ? (
          <p className="text-[#71717A] text-sm">No projects yet.</p>
        ) : (
          <div className="grid gap-3">
            {products.map((p) => (
              <Link
                key={p.id}
                href={`/projects?id=${p.id}`}
                className="block border border-[#1F1F23] rounded-lg px-5 py-4 hover:bg-[#1F1F23]/50 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-base font-semibold text-white">
                      {p.name}
                    </h2>
                    <p className="text-sm text-[#71717A] mt-0.5 line-clamp-1">
                      {p.summary}
                    </p>
                  </div>
                  <span className="text-xs text-[#71717A] shrink-0 ml-4">
                    {p.status}
                  </span>
                </div>
              </Link>
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
  const { partner } = useAuth();
  const router = useRouter();

  const [data, setData] = useState<ProjectData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!partner) return;

    async function load() {
      const [project, children, blindspots, documentCount] = await Promise.all([
        getEntity(projectId),
        getChildEntities(projectId),
        getBlindspots(projectId),
        countDocuments(projectId),
      ]);

      if (!project) {
        router.replace("/projects");
        return;
      }

      setData({ project, children, blindspots, documentCount });
      setLoading(false);
    }

    load();
  }, [partner, projectId, router]);

  if (loading || !data) {
    return (
      <div className="min-h-screen flex flex-col">
        <AppNav />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-[#71717A]">Loading...</div>
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
      <main className="max-w-5xl mx-auto px-6 py-8 space-y-8 w-full">
        {criticalBlindspots.length > 0 && (
          <div className="bg-red-900/30 border border-red-800 rounded-lg p-4">
            <p className="text-sm font-medium text-red-400">
              {criticalBlindspots.length} critical issue{criticalBlindspots.length > 1 ? "s" : ""} detected
            </p>
          </div>
        )}

        <div>
          <h2 className="text-2xl font-bold text-white mb-1">
            {project.name}
          </h2>
          <p className="text-[#71717A] mb-4">{project.summary}</p>
          <div className="flex gap-6 text-sm text-[#71717A]">
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
      <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><div className="text-[#71717A]">Loading...</div></div>}>
        <ProjectPageInner />
      </Suspense>
    </AuthGuard>
  );
}
