"use client";

import { useState } from "react";
import { useInk } from "@/lib/zen-ink/tokens";
import { Dialog } from "@/components/zen/Dialog";
import { Input } from "@/components/zen/Input";
import { Textarea } from "@/components/zen/Textarea";
import { Select } from "@/components/zen/Select";
import { Btn } from "@/components/zen/Btn";
import { FormField } from "@/components/zen/_formField";

interface TaskCreateData {
  title: string;
  description?: string;
  priority?: string;
  assignee?: string;
  due_date?: string;
  project?: string;
}

interface TaskCreateDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onCreateTask: (data: TaskCreateData) => Promise<void>;
}

const PRIORITY_OPTIONS = [
  { value: "critical", label: "Critical" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

export function TaskCreateDialog({
  isOpen,
  onClose,
  onCreateTask,
}: TaskCreateDialogProps) {
  const t = useInk("light");
  const { c, fontBody, fontMono } = t;

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<string | null>(null);
  const [assignee, setAssignee] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [project, setProject] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function resetForm() {
    setTitle("");
    setDescription("");
    setPriority(null);
    setAssignee("");
    setDueDate("");
    setProject("");
    setError(null);
  }

  function handleClose() {
    resetForm();
    onClose();
  }

  async function handleSubmit() {
    if (!title.trim()) return;

    setSubmitting(true);
    setError(null);
    try {
      const data: TaskCreateData = { title: title.trim() };
      if (description.trim()) data.description = description.trim();
      if (priority) data.priority = priority;
      if (assignee.trim()) data.assignee = assignee.trim();
      if (dueDate) data.due_date = dueDate;
      if (project.trim()) data.project = project.trim();

      await onCreateTask(data);
      resetForm();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "建立失敗，請重試");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      t={t}
      open={isOpen}
      onOpenChange={(v) => !v && handleClose()}
      title="新增任務"
      size="md"
      footer={
        <>
          <Btn t={t} variant="ghost" onClick={handleClose} size="md">
            取消
          </Btn>
          <Btn
            t={t}
            variant="ink"
            onClick={handleSubmit}
            size="md"
            style={!title.trim() || submitting ? { opacity: 0.5, cursor: "not-allowed", pointerEvents: "none" } : undefined}
          >
            {submitting ? "建立中..." : "建立任務"}
          </Btn>
        </>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {/* Title (required) */}
        <FormField t={t} label="標題" required htmlFor="task-title">
          <Input
            t={t}
            id="task-title"
            value={title}
            onChange={setTitle}
            placeholder="任務標題"
            autoFocus
          />
        </FormField>

        {/* Description */}
        <FormField t={t} label="描述" htmlFor="task-desc">
          <Textarea
            t={t}
            id="task-desc"
            value={description}
            onChange={setDescription}
            placeholder="任務描述（選填）"
            rows={3}
            resize="none"
          />
        </FormField>

        {/* Priority + Assignee */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <FormField t={t} label="優先級" htmlFor="task-priority">
            <Select
              t={t}
              id="task-priority"
              value={priority}
              onChange={setPriority}
              options={PRIORITY_OPTIONS}
              placeholder="選擇優先級"
              clearable
            />
          </FormField>

          <FormField t={t} label="指派人" htmlFor="task-assignee">
            <Input
              t={t}
              id="task-assignee"
              value={assignee}
              onChange={setAssignee}
              placeholder="UID 或名稱"
            />
          </FormField>
        </div>

        {/* Due Date + Project */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <FormField t={t} label="到期日" htmlFor="task-due">
            <Input
              t={t}
              id="task-due"
              type="date"
              value={dueDate}
              onChange={setDueDate}
            />
          </FormField>

          <FormField t={t} label="專案" htmlFor="task-project">
            <Input
              t={t}
              id="task-project"
              value={project}
              onChange={setProject}
              placeholder="專案名稱"
            />
          </FormField>
        </div>

        {/* Error message */}
        {error && (
          <p
            style={{
              margin: 0,
              fontSize: 13,
              fontFamily: fontMono,
              color: c.vermillion,
              background: c.vermSoft,
              border: `1px solid ${c.vermLine}`,
              borderRadius: t.radius,
              padding: "8px 12px",
            }}
          >
            {error}
          </p>
        )}
      </div>
    </Dialog>
  );
}
