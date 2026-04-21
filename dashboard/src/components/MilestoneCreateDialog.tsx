"use client";

import { useState } from "react";
import { useInk } from "@/lib/zen-ink/tokens";
import { Dialog } from "@/components/zen/Dialog";
import { Input } from "@/components/zen/Input";
import { Textarea } from "@/components/zen/Textarea";
import { Select } from "@/components/zen/Select";
import { Btn } from "@/components/zen/Btn";
import { FormField } from "@/components/zen/_formField";

interface MilestoneCreateDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onCreateMilestone: (data: {
    name: string;
    summary?: string;
    status?: "planned" | "active";
  }) => Promise<void>;
}

const STATUS_OPTIONS = [
  { value: "planned", label: "Planned" },
  { value: "active", label: "Active" },
];

export function MilestoneCreateDialog({
  isOpen,
  onClose,
  onCreateMilestone,
}: MilestoneCreateDialogProps) {
  const t = useInk("light");
  const [name, setName] = useState("");
  const [summary, setSummary] = useState("");
  const [status, setStatus] = useState<"planned" | "active">("planned");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setName("");
    setSummary("");
    setStatus("planned");
    setSubmitting(false);
    setError(null);
  }

  function handleClose() {
    reset();
    onClose();
  }

  async function handleSubmit() {
    if (!name.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await onCreateMilestone({
        name: name.trim(),
        summary: summary.trim() || undefined,
        status,
      });
      reset();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "建立 milestone 失敗");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      t={t}
      open={isOpen}
      onOpenChange={(open) => !open && handleClose()}
      title="新增 Milestone"
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
            style={!name.trim() || submitting ? { opacity: 0.5, cursor: "not-allowed", pointerEvents: "none" } : undefined}
          >
            {submitting ? "建立中..." : "建立 Milestone"}
          </Btn>
        </>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <FormField t={t} label="Milestone 名稱" required htmlFor="milestone-name">
          <Input
            t={t}
            id="milestone-name"
            value={name}
            onChange={setName}
            placeholder="例如：P0 上線"
            autoFocus
          />
        </FormField>

        <FormField t={t} label="狀態" htmlFor="milestone-status">
          <Select
            t={t}
            id="milestone-status"
            value={status}
            onChange={(value) => setStatus((value as "planned" | "active") || "planned")}
            options={STATUS_OPTIONS}
          />
        </FormField>

        <FormField t={t} label="摘要" htmlFor="milestone-summary">
          <Textarea
            t={t}
            id="milestone-summary"
            value={summary}
            onChange={setSummary}
            placeholder="這個 milestone 代表什麼成果"
            rows={4}
          />
        </FormField>

        {error ? (
          <div style={{ fontSize: 12, color: t.c.vermillion }}>{error}</div>
        ) : null}
      </div>
    </Dialog>
  );
}
