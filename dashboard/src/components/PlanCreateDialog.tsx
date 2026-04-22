"use client";

import { useState } from "react";
import { useInk } from "@/lib/zen-ink/tokens";
import { Dialog } from "@/components/zen/Dialog";
import { Input } from "@/components/zen/Input";
import { Textarea } from "@/components/zen/Textarea";
import { Select } from "@/components/zen/Select";
import { Btn } from "@/components/zen/Btn";
import { FormField } from "@/components/zen/_formField";

interface PlanCreateDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onCreatePlan: (data: {
    goal: string;
    owner?: string | null;
    entry_criteria?: string | null;
    exit_criteria?: string | null;
    status?: "draft" | "active";
  }) => Promise<void>;
  defaultOwner?: string | null;
}

const STATUS_OPTIONS = [
  { value: "active", label: "Active" },
  { value: "draft", label: "Draft" },
];

export function PlanCreateDialog({
  isOpen,
  onClose,
  onCreatePlan,
  defaultOwner,
}: PlanCreateDialogProps) {
  const t = useInk("light");
  const [goal, setGoal] = useState("");
  const [owner, setOwner] = useState(defaultOwner ?? "");
  const [entryCriteria, setEntryCriteria] = useState("");
  const [exitCriteria, setExitCriteria] = useState("");
  const [status, setStatus] = useState<"draft" | "active">("active");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setGoal("");
    setOwner(defaultOwner ?? "");
    setEntryCriteria("");
    setExitCriteria("");
    setStatus("active");
    setSubmitting(false);
    setError(null);
  }

  function handleClose() {
    reset();
    onClose();
  }

  async function handleSubmit() {
    if (!goal.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await onCreatePlan({
        goal: goal.trim(),
        owner: owner.trim() || null,
        entry_criteria: entryCriteria.trim() || null,
        exit_criteria: exitCriteria.trim() || null,
        status,
      });
      reset();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "建立 plan 失敗");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      t={t}
      open={isOpen}
      onOpenChange={(open) => !open && handleClose()}
      title="新增 Plan"
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
            style={!goal.trim() || submitting ? { opacity: 0.5, cursor: "not-allowed", pointerEvents: "none" } : undefined}
          >
            {submitting ? "建立中..." : "建立 Plan"}
          </Btn>
        </>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <FormField t={t} label="Plan 目標" required htmlFor="plan-goal">
          <Input
            t={t}
            id="plan-goal"
            value={goal}
            onChange={setGoal}
            placeholder="例如：完成工作台進度盤點"
            autoFocus
          />
        </FormField>

        <FormField t={t} label="Owner" htmlFor="plan-owner">
          <Input
            t={t}
            id="plan-owner"
            value={owner}
            onChange={setOwner}
            placeholder="負責人"
          />
        </FormField>

        <FormField t={t} label="狀態" htmlFor="plan-status">
          <Select
            t={t}
            id="plan-status"
            value={status}
            onChange={(value) => setStatus((value as "draft" | "active") || "active")}
            options={STATUS_OPTIONS}
          />
        </FormField>

        <FormField t={t} label="Entry Criteria" htmlFor="plan-entry">
          <Textarea
            t={t}
            id="plan-entry"
            value={entryCriteria}
            onChange={setEntryCriteria}
            placeholder="什麼條件下算正式開始"
            rows={3}
          />
        </FormField>

        <FormField t={t} label="Exit Criteria" htmlFor="plan-exit">
          <Textarea
            t={t}
            id="plan-exit"
            value={exitCriteria}
            onChange={setExitCriteria}
            placeholder="什麼條件下算完成"
            rows={3}
          />
        </FormField>

        {error ? (
          <div style={{ fontSize: 12, color: t.c.vermillion }}>{error}</div>
        ) : null}
      </div>
    </Dialog>
  );
}
