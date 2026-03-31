"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { Entity, Task } from "@/types";
import { MarkdownRenderer } from "./MarkdownRenderer";
import {
  AlertTriangle,
  ArrowUp,
  Minus,
  ArrowDown,
  X,
  Layers,
  Calendar,
  User,
  ExternalLink,
  Bot,
  Hash,
  Link2,
  FileText,
  Clock,
} from "lucide-react";

interface TaskDetailDrawerProps {
  task: Task | null;
  onClose: () => void;
  entityNames?: Record<string, string>;
  entitiesById?: Record<string, Entity>;
}

const priorityIcons: Record<string, React.ReactNode> = {
  critical: <AlertTriangle className="w-4 h-4 text-red-400" />,
  high: <ArrowUp className="w-4 h-4 text-orange-400" />,
  medium: <Minus className="w-4 h-4 text-yellow-400" />,
  low: <ArrowDown className="w-4 h-4 text-blue-400" />,
};

const statusColors: Record<string, string> = {
  todo: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  in_progress: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  review: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  done: "bg-green-500/10 text-green-400 border-green-500/20",
  blocked: "bg-red-500/10 text-red-400 border-red-500/20",
  backlog: "bg-gray-500/10 text-gray-400 border-gray-500/20",
};

function formatDate(date: Date | null): string {
  if (!date) return "No date set";
  return date.toLocaleDateString("zh-TW", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function ContextCard({ entity }: { entity?: Entity; name: string }) {
  if (!entity) return null;
  
  return (
    <Link href={`/knowledge-map?id=${entity.id}`} className="block group">
      <div className="bg-white/[0.04] border border-white/10 rounded-xl p-4 space-y-3 group-hover:bg-white/[0.08] group-hover:border-blue-500/30 transition-all shadow-sm overflow-hidden relative active:scale-[0.98]">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-blue-500/20 border border-blue-500/30 group-hover:bg-blue-500/30 transition-colors">
              <Link2 className="w-3.5 h-3.5 text-blue-300" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-white group-hover:text-blue-300 transition-colors">
                {entity.name}
              </h4>
              <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-black">
                {entity.type}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className={`px-2 py-0.5 rounded-full text-[9px] font-black border ${
              entity.status === 'active' ? 'bg-green-500/20 text-green-400 border-green-500/30' : 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
            }`}>
              {entity.status.toUpperCase()}
            </div>
            <ExternalLink className="w-3 h-3 text-white/20 group-hover:text-blue-400 transition-colors" />
          </div>
        </div>

        <p className="text-xs text-foreground/90 leading-relaxed line-clamp-3 italic">
          "{entity.summary}"
        </p>

        {entity.tags && (
          <div className="grid grid-cols-2 gap-4 pt-1 border-t border-white/5 mt-2">
            {entity.tags.what && (Array.isArray(entity.tags.what) ? entity.tags.what : []).length > 0 && (
              <div className="space-y-1">
                <span className="text-[9px] font-black text-blue-400/80 uppercase tracking-widest">What</span>
                <div className="flex flex-wrap gap-1">
                  {(Array.isArray(entity.tags.what) ? entity.tags.what : []).slice(0, 2).map((t: string, i: number) => (
                    <span key={i} className="text-[10px] text-foreground font-medium">{t}</span>
                  ))}
                </div>
              </div>
            )}
            {entity.owner && (
              <div className="space-y-1">
                <span className="text-[9px] font-black text-indigo-400/80 uppercase tracking-widest">Owner</span>
                <div className="text-[10px] text-foreground font-medium">{entity.owner}</div>
              </div>
            )}
          </div>
        )}
      </div>
    </Link>
  );
}

export function TaskDetailDrawer({
  task,
  onClose,
  entityNames = {},
  entitiesById = {},
}: TaskDetailDrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    if (task) {
      setIsVisible(true);
      document.body.style.overflow = "hidden";
    } else {
      setIsVisible(false);
      document.body.style.overflow = "unset";
    }
  }, [task]);

  if (!task) return null;

  return (
    <div
      className={`fixed inset-0 z-50 transition-opacity duration-300 ${
        isVisible ? "opacity-100" : "opacity-0 pointer-events-none"
      }`}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/85 backdrop-blur-md"
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        ref={drawerRef}
        className={`absolute right-0 top-0 bottom-0 w-full max-w-2xl bg-gradient-to-b from-[#0d0d0d] to-[#050505] border-l border-white/10 shadow-2xl transition-transform duration-500 ease-out flex flex-col ${
          isVisible ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Header Section */}
        <div className="p-6 border-b border-white/10 bg-white/[0.02]">
          <div className="flex items-start justify-between mb-6">
            <div className="space-y-4 flex-1 pr-8">
              <div className="flex flex-wrap items-center gap-2.5">
                <span className={`px-2.5 py-1 rounded-full text-[10px] font-black uppercase tracking-widest border ${statusColors[task.status]}`}>
                  {task.status}
                </span>
                <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-black uppercase tracking-widest border ${priorityBg[task.priority]}`}>
                  {priorityIcons[task.priority]}
                  {task.priority}
                </span>
                {task.planId && (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-black uppercase tracking-widest border border-purple-500/30 bg-purple-500/10 text-purple-300 shadow-sm">
                    <Layers className="w-3.5 h-3.5" />
                    {entityNames[task.planId] || task.planId}
                    {task.planOrder !== null && (
                      <span className="opacity-70 ml-1">#{task.planOrder}</span>
                    )}
                  </span>
                )}
              </div>
              <h2 className="text-2xl font-bold text-white leading-tight tracking-tight">
                {task.title}
              </h2>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-xl hover:bg-white/10 text-muted-foreground hover:text-white transition-all border border-transparent hover:border-white/20"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 pt-2">
            <div className="space-y-1.5">
              <span className="text-[10px] font-black text-muted-foreground uppercase tracking-[0.15em] flex items-center gap-1.5 opacity-80">
                <User className="w-3 h-3 text-indigo-400" /> Owner
              </span>
              <div className="text-sm font-bold text-white truncate">
                {task.assigneeName || task.assignee || "Unassigned"}
              </div>
            </div>
            <div className="space-y-1.5">
              <span className="text-[10px] font-black text-muted-foreground uppercase tracking-[0.15em] flex items-center gap-1.5 opacity-80">
                <Clock className="w-3 h-3 text-orange-400" /> Due Date
              </span>
              <div className="text-sm font-bold text-white">
                {formatDate(task.dueDate)}
              </div>
            </div>
            <div className="space-y-1.5">
              <span className="text-[10px] font-black text-muted-foreground uppercase tracking-[0.15em] flex items-center gap-1.5 opacity-80">
                <Hash className="w-3 h-3 text-blue-400" /> Project
              </span>
              <div className="text-sm font-black text-blue-400 uppercase tracking-tight">
                {task.project || "N/A"}
              </div>
            </div>
            <div className="space-y-1.5">
              <span className="text-[10px] font-black text-muted-foreground uppercase tracking-[0.15em] flex items-center gap-1.5 opacity-80">
                <Bot className="w-3 h-3 text-purple-400" /> Source
              </span>
              <div className="text-sm font-medium text-foreground/90 truncate">
                {task.creatorName || task.createdBy}
              </div>
            </div>
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto custom-scrollbar bg-black/20">
          <div className="p-8 space-y-10">
            
            {/* Context Cards Section */}
            {task.linkedEntities.length > 0 && (
              <div className="space-y-4">
                <div className="flex items-center gap-2 mb-4">
                  <div className="h-4 w-1.5 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.5)]" />
                  <h3 className="text-[11px] font-black uppercase tracking-[0.2em] text-white/90">Contextual Assets</h3>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {task.linkedEntities.map(id => (
                    <ContextCard key={id} name={id} entity={entitiesById[id]} />
                  ))}
                </div>
              </div>
            )}

            {/* Description Section */}
            <div className="space-y-4">
              <div className="flex items-center gap-2 mb-4">
                <div className="h-4 w-1.5 rounded-full bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,0.5)]" />
                <h3 className="text-[11px] font-black uppercase tracking-[0.2em] text-white/90">Instruction & Logic</h3>
              </div>
              <div className="prose prose-invert prose-sm max-w-none bg-white/[0.03] border border-white/10 rounded-2xl p-6 shadow-inner leading-relaxed text-foreground">
                <MarkdownRenderer content={task.description || "_No description provided._"} />
              </div>
            </div>

            {/* Acceptance Criteria */}
            {task.acceptanceCriteria && task.acceptanceCriteria.length > 0 && (
              <div className="space-y-4">
                <div className="flex items-center gap-2 mb-4">
                  <div className="h-4 w-1.5 rounded-full bg-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.5)]" />
                  <h3 className="text-[11px] font-black uppercase tracking-[0.2em] text-white/90">Success Criteria</h3>
                </div>
                <div className="space-y-3">
                  {task.acceptanceCriteria.map((item, idx) => (
                    <div key={idx} className="flex items-start gap-4 bg-white/[0.03] border border-white/10 p-4 rounded-xl hover:bg-white/[0.05] transition-colors">
                      <div className="mt-0.5 w-5 h-5 rounded-full bg-purple-500/20 border border-purple-500/40 flex items-center justify-center flex-shrink-0 text-[11px] font-black text-purple-300">
                        {idx + 1}
                      </div>
                      <p className="text-sm text-foreground leading-relaxed font-medium">{item}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Result / Deliverables */}
            {task.result && (
              <div className="space-y-4 pt-4 border-t border-white/10">
                <div className="flex items-center gap-2 mb-4">
                  <div className="h-4 w-1.5 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]" />
                  <h3 className="text-[11px] font-black uppercase tracking-[0.2em] text-white/90">Outcome</h3>
                </div>
                <div className="bg-green-500/10 border border-green-500/20 rounded-2xl p-6 text-sm text-green-50 leading-relaxed italic shadow-inner">
                  <MarkdownRenderer content={task.result} />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

const priorityBg: Record<string, string> = {
  critical: "bg-red-500/20 border-red-500/30 text-red-300",
  high: "bg-orange-500/20 border-orange-500/30 text-orange-300",
  medium: "bg-yellow-500/20 border-yellow-500/30 text-yellow-300",
  low: "bg-blue-500/20 border-blue-500/30 text-blue-300",
};
