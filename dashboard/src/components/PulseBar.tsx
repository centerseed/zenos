"use client";

import type { Task } from "@/types";

interface PulseBarProps {
  tasks: Task[];
}

export function PulseBar({ tasks }: PulseBarProps) {
  const now = new Date();

  const active = tasks.filter((t) =>
    ["backlog", "todo", "in_progress", "review", "blocked"].includes(t.status)
  ).length;

  const moving = tasks.filter((t) => t.status === "in_progress").length;

  const blocked = tasks.filter((t) => t.status === "blocked").length;

  const overdue = tasks.filter(
    (t) =>
      t.dueDate !== null &&
      t.dueDate.getTime() < now.getTime() &&
      !["done", "cancelled", "archived"].includes(t.status)
  ).length;

  const review = tasks.filter(
    (t) => t.status === "review" && !t.confirmedByCreator
  ).length;

  const metrics = [
    { label: "Active", value: active, color: "text-blue-400", bg: "bg-blue-900/30" },
    { label: "Moving", value: moving, color: "text-green-400", bg: "bg-green-900/30" },
    {
      label: "Blocked",
      value: blocked,
      color: blocked > 0 ? "text-red-400" : "text-[#71717A]",
      bg: blocked > 0 ? "bg-red-900/30" : "bg-[#1F1F23]",
    },
    {
      label: "Overdue",
      value: overdue,
      color: overdue > 0 ? "text-orange-400" : "text-[#71717A]",
      bg: overdue > 0 ? "bg-orange-900/30" : "bg-[#1F1F23]",
    },
    { label: "Review", value: review, color: "text-purple-400", bg: "bg-purple-900/30" },
  ];

  return (
    <div className="bg-[#111113] rounded-lg border border-[#1F1F23] p-4">
      <div className="grid grid-cols-5 gap-4">
        {metrics.map((m) => (
          <div
            key={m.label}
            className={`rounded-lg p-4 text-center ${m.bg}`}
          >
            <div className={`text-2xl font-bold ${m.color}`}>{m.value}</div>
            <div className="text-xs text-[#71717A] mt-1">{m.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
