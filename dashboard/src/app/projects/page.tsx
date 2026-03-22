"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { AuthGuard } from "@/components/AuthGuard";
import { EntityTree } from "@/components/EntityTree";
import { BlindspotAlert } from "@/components/BlindspotAlert";
import { PromptSuggestions } from "@/components/PromptSuggestions";
import {
  getEntity,
  getChildEntities,
  getBlindspots,
  countDocuments,
} from "@/lib/firestore";
import type { Entity, Blindspot } from "@/types";

interface ProjectData {
  project: Entity;
  children: Entity[];
  blindspots: Blindspot[];
  documentCount: number;
}

function ProjectPageInner() {
  const { partner, signOut } = useAuth();
  const searchParams = useSearchParams();
  const router = useRouter();
  const projectId = searchParams.get("id");

  const [data, setData] = useState<ProjectData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!partner || !projectId) return;

    async function load() {
      const [project, children, blindspots, documentCount] = await Promise.all([
        getEntity(projectId!),
        getChildEntities(projectId!),
        getBlindspots(projectId!),
        countDocuments(projectId!),
      ]);

      if (!project) {
        router.replace("/");
        return;
      }

      setData({ project, children, blindspots, documentCount });
      setLoading(false);
    }

    load();
  }, [partner, projectId, router]);

  if (!projectId) {
    router.replace("/");
    return null;
  }

  if (loading || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  const { project, children, blindspots, documentCount } = data;
  const criticalBlindspots = blindspots.filter((b) => b.severity === "red");
  const allEntities = [project, ...children];

  return (
    <div className="min-h-screen">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link href="/" className="text-xl font-bold text-gray-900 hover:text-gray-600">
              ZenOS
            </Link>
            <nav className="flex items-center gap-4 text-sm">
              <Link href="/" className="text-gray-500 hover:text-gray-900">
                Projects
              </Link>
              <Link href="/tasks" className="text-gray-500 hover:text-gray-900">
                Tasks
              </Link>
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500">
              {partner?.displayName}
            </span>
            <button
              onClick={signOut}
              className="text-sm text-gray-400 hover:text-gray-600 cursor-pointer"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-8">
        {criticalBlindspots.length > 0 && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-sm font-medium text-red-800">
              {criticalBlindspots.length} critical issue{criticalBlindspots.length > 1 ? "s" : ""} detected
            </p>
          </div>
        )}

        <div>
          <h2 className="text-2xl font-bold text-gray-900 mb-1">
            {project.name}
          </h2>
          <p className="text-gray-500 mb-4">{project.summary}</p>
          <div className="flex gap-6 text-sm text-gray-400">
            <span>{children.filter((c) => c.type === "module").length} modules</span>
            <span>{documentCount} documents</span>
            <span>{blindspots.length} blindspots</span>
          </div>
        </div>

        <div>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Modules
          </h3>
          <EntityTree entities={children} allEntities={allEntities} />
        </div>

        {blindspots.length > 0 && (
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Blindspots
            </h3>
            <BlindspotAlert blindspots={blindspots} />
          </div>
        )}

        <PromptSuggestions projectName={project.name} />

        <div className="pt-4">
          <Link href="/" className="text-sm text-blue-600 hover:underline">
            Back to projects
          </Link>
        </div>
      </main>
    </div>
  );
}

export default function Page() {
  return (
    <AuthGuard>
      <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><div className="text-gray-400">Loading...</div></div>}>
        <ProjectPageInner />
      </Suspense>
    </AuthGuard>
  );
}
