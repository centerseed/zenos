"use client";

import type { Task } from "@/types";
import { AlertTriangle, ArrowRight, Clock3, Inbox } from "lucide-react";
import {
  getIdleTodoHours,
  getOverdueDays,
  getUpcomingDueDays,
  isCreatedByMe,
  isMine,
} from "@/lib/task-risk";

interface MorningReportProps {
  tasks: Task[];
  partnerId: string;
  onSelectTask: (task: Task) => void;
}

interface MorningBucket {
  key: string;
  title: string;
  empty: string;
  icon: React.ReactNode;
  tasks: Task[];
  describe: (task: Task) => string;
}

export function MorningReport({ tasks, partnerId, onSelectTask }: MorningReportProps) {
  const now = new Date();

  const buckets: MorningBucket[] = [
    {
      key: "upcoming",
      title: "即將到期",
      empty: "未來 3 天內沒有你的到期任務",
      icon: <Clock3 className="w-4 h-4 text-orange-300" />,
      tasks: tasks
        .filter((task) => isMine(task, partnerId) && getUpcomingDueDays(task, now) !== null)
        .sort((a, b) => (a.dueDate?.getTime() ?? 0) - (b.dueDate?.getTime() ?? 0)),
      describe: (task) => `${getUpcomingDueDays(task, now)} 天後到期`,
    },
    {
      key: "overdue",
      title: "已逾期",
      empty: "沒有逾期中的指派任務",
      icon: <AlertTriangle className="w-4 h-4 text-red-300" />,
      tasks: tasks
        .filter((task) => isMine(task, partnerId) && getOverdueDays(task, now) !== null)
        .sort((a, b) => (b.dueDate?.getTime() ?? 0) - (a.dueDate?.getTime() ?? 0)),
      describe: (task) => `逾期 ${getOverdueDays(task, now)} 天`,
    },
    {
      key: "idle",
      title: "建的任務 - 無人動",
      empty: "你建立的任務目前沒有停滯項目",
      icon: <Inbox className="w-4 h-4 text-zinc-300" />,
      tasks: tasks
        .filter((task) =>
          isCreatedByMe(task, partnerId) &&
          task.assignee !== null &&
          getIdleTodoHours(task, now) !== null
        )
        .sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime()),
      describe: (task) => `未開始 ${getIdleTodoHours(task, now)}h`,
    },
  ];

  const hasRisk = buckets.some((bucket) => bucket.tasks.length > 0);

  return (
    <section className="mb-6 rounded-2xl border border-white/10 bg-[linear-gradient(135deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))] p-4 sm:p-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-black uppercase tracking-[0.24em] text-blue-300/80">Morning Report</p>
          <h2 className="mt-1 text-lg font-bold text-white">今天先處理這些風險任務</h2>
        </div>
        <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-bold text-gray-300">
          {buckets.reduce((sum, bucket) => sum + bucket.tasks.length, 0)} items
        </div>
      </div>

      {!hasRisk ? (
        <div className="rounded-xl border border-dashed border-white/10 bg-black/20 px-4 py-8 text-center text-sm text-gray-300">
          今日無待處理風險
        </div>
      ) : (
        <div className="grid gap-3 lg:grid-cols-3">
          {buckets.map((bucket) => (
            <div key={bucket.key} className="rounded-xl border border-white/8 bg-black/20 p-3">
              <div className="mb-3 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  {bucket.icon}
                  <h3 className="text-sm font-bold text-white">{bucket.title}</h3>
                </div>
                <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[11px] font-bold text-gray-300">
                  {bucket.tasks.length}
                </span>
              </div>

              {bucket.tasks.length === 0 ? (
                <p className="min-h-16 text-xs leading-6 text-gray-400">{bucket.empty}</p>
              ) : (
                <div className="space-y-2">
                  {bucket.tasks.map((task) => (
                    <button
                      key={`${bucket.key}-${task.id}`}
                      type="button"
                      onClick={() => onSelectTask(task)}
                      className="w-full rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2 text-left transition-colors hover:border-blue-500/30 hover:bg-blue-500/[0.06]"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-white">{task.title}</p>
                          <p className="mt-1 text-[11px] font-medium text-gray-400">{bucket.describe(task)}</p>
                        </div>
                        <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-gray-500" />
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
