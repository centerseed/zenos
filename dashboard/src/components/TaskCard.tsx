"use client";

import { useState } from "react";
import type { Task } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface TaskCardProps {
  task: Task;
}

const priorityColors: Record<string, string> = {
  critical: "bg-red-900/50 text-red-400",
  high: "bg-orange-900/50 text-orange-400",
  medium: "bg-blue-900/50 text-blue-400",
  low: "bg-secondary text-muted-foreground",
};

function formatDate(date: Date | null): string | null {
  if (!date) return null;
  return date.toLocaleDateString("zh-TW");
}

function isOverdue(date: Date | null): boolean {
  if (!date) return false;
  return date.getTime() < Date.now();
}

export function TaskCard({ task }: TaskCardProps) {
  const [expanded, setExpanded] = useState(false);

  const dueDateStr = formatDate(task.dueDate);
  const overdue = task.status !== "done" && task.status !== "cancelled" && isOverdue(task.dueDate);

  return (
    <Card className="ring-1 ring-border/80 hover:ring-border transition-colors">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm font-medium text-foreground leading-tight">
            {task.title}
          </CardTitle>
          <span
            className={`text-xs px-2 py-0.5 rounded-full whitespace-nowrap ${priorityColors[task.priority] ?? "bg-secondary text-muted-foreground"}`}
          >
            {task.priority}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          {task.assignee && <span>@{task.assignee}</span>}
          {dueDateStr && (
            <span className={overdue ? "text-red-400 font-medium" : ""}>
              Due {dueDateStr}
            </span>
          )}
          {task.linkedEntities.length > 0 && (
            <span>{task.linkedEntities.length} linked</span>
          )}
          <Button
            type="button"
            variant="ghost"
            size="xs"
            className="ml-auto"
            onClick={() => setExpanded((prev) => !prev)}
            aria-label={expanded ? `Collapse task ${task.title}` : `Expand task ${task.title}`}
          >
            {expanded ? "Collapse" : "Expand"}
          </Button>
        </div>
      </CardHeader>

      {expanded && (
        <CardContent className="pt-2 border-t border-border space-y-3 text-sm">
          {task.description && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Description</p>
              <p className="text-foreground">{task.description}</p>
            </div>
          )}

          {task.contextSummary && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Context</p>
              <p className="text-foreground">{task.contextSummary}</p>
            </div>
          )}

          {task.acceptanceCriteria.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Acceptance Criteria</p>
              <ul className="list-disc list-inside text-foreground space-y-0.5">
                {task.acceptanceCriteria.map((ac, i) => (
                  <li key={i}>{ac}</li>
                ))}
              </ul>
            </div>
          )}

          {task.blockedBy.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Blocked By</p>
              <p className="text-foreground">{task.blockedBy.join(", ")}</p>
            </div>
          )}

          {task.blockedReason && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Blocked Reason</p>
              <p className="text-foreground">{task.blockedReason}</p>
            </div>
          )}

          {task.result && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Result</p>
              <p className="text-foreground">{task.result}</p>
            </div>
          )}

          {task.rejectionReason && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Rejection Reason</p>
              <p className="text-red-400">{task.rejectionReason}</p>
            </div>
          )}

          <div className="flex gap-4 text-xs text-muted-foreground pt-1">
            <span>Created by {task.createdBy}</span>
            <span>Updated {formatDate(task.updatedAt)}</span>
          </div>
        </CardContent>
      )}
    </Card>
  );
}
