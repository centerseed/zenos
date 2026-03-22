"use client";

import { useAuth } from "@/lib/auth";
import { AuthGuard } from "@/components/AuthGuard";
import { ProjectCard } from "@/components/ProjectCard";
import { useEffect, useState } from "react";
import { getProjectEntities, countChildEntities } from "@/lib/firestore";
import type { Entity } from "@/types";
import Link from "next/link";

interface ProjectWithCount {
  entity: Entity;
  moduleCount: number;
}

function HomePage() {
  const { partner, signOut } = useAuth();
  const [projects, setProjects] = useState<ProjectWithCount[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!partner) return;

    async function load() {
      const entities = await getProjectEntities();
      const withCounts = await Promise.all(
        entities.map(async (entity) => ({
          entity,
          moduleCount: await countChildEntities(entity.id),
        }))
      );
      setProjects(withCounts);
      setLoading(false);
    }

    load();
  }, [partner]);

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <h1 className="text-xl font-bold text-gray-900">ZenOS</h1>
            <nav className="flex items-center gap-4 text-sm">
              <span className="font-semibold text-gray-900 underline underline-offset-4">
                Projects
              </span>
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

      {/* CTA */}
      <div className="max-w-5xl mx-auto px-6 py-6">
        <Link
          href="/setup"
          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors"
        >
          <span>⚡</span> Set up your AI Agent
        </Link>
      </div>

      {/* Projects */}
      <main className="max-w-5xl mx-auto px-6 pb-12">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          My Projects
        </h2>

        {loading ? (
          <div className="text-gray-400 text-sm">Loading projects...</div>
        ) : projects.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
            <p className="text-gray-500">
              No projects assigned yet. Contact your admin.
            </p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {projects.map(({ entity, moduleCount }) => (
              <ProjectCard
                key={entity.id}
                entity={entity}
                moduleCount={moduleCount}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

export default function Page() {
  return (
    <AuthGuard>
      <HomePage />
    </AuthGuard>
  );
}
