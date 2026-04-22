"use client";

import { useMemo, useState } from "react";
import type { Blindspot, Entity } from "@/types";
import { useInk } from "@/lib/zen-ink/tokens";
import { Dialog } from "@/components/zen/Dialog";
import { Input } from "@/components/zen/Input";
import { Textarea } from "@/components/zen/Textarea";
import { Select } from "@/components/zen/Select";
import { Btn } from "@/components/zen/Btn";
import { Dropdown } from "@/components/zen/Dropdown";
import { FormField } from "@/components/zen/_formField";

interface TaskCreateData {
  title: string;
  product_id: string;
  description?: string;
  priority?: string;
  assignee?: string;
  due_date?: string;
  project?: string;
  linked_entities?: string[];
  acceptance_criteria?: string[];
  assignee_role_id?: string | null;
  linked_protocol?: string | null;
  linked_blindspot?: string | null;
  blocked_by?: string[];
  blocked_reason?: string | null;
  plan_id?: string | null;
  plan_order?: number | null;
  depends_on_task_ids?: string[];
  parent_task_id?: string | null;
  dispatcher?: string | null;
  source_metadata?: Record<string, unknown>;
}

interface TaskCreateDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onCreateTask: (data: TaskCreateData) => Promise<void>;
  entities: Entity[];
  blindspots: Blindspot[];
}

const PRIORITY_OPTIONS = [
  { value: "critical", label: "Critical" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

const DISPATCHER_OPTIONS = [
  { value: "", label: "未指定" },
  { value: "agent:pm", label: "PM" },
  { value: "agent:architect", label: "Architect" },
  { value: "agent:developer", label: "Developer" },
  { value: "agent:qa", label: "QA" },
  { value: "agent:designer", label: "Designer" },
  { value: "agent:debugger", label: "Debugger" },
  { value: "human", label: "Human" },
];

function parseCommaSeparatedIds(input: string): string[] {
  return input
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseMultilineItems(input: string): string[] {
  return input
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function TaskCreateDialog({
  isOpen,
  onClose,
  onCreateTask,
  entities,
  blindspots,
}: TaskCreateDialogProps) {
  const t = useInk("light");
  const { c, fontBody, fontMono, radius } = t;

  const roleOptions = useMemo(
    () =>
      entities
        .filter((entity) => entity.type === "role")
        .map((entity) => ({ value: entity.id, label: entity.name })),
    [entities]
  );

  const entityItems = useMemo(
    () =>
      entities.map((entity) => ({
        value: entity.id,
        label: `${entity.name} · ${entity.type}`,
      })),
    [entities]
  );

  const blindspotOptions = useMemo(
    () => [
      { value: "", label: "未指定" },
      ...blindspots.map((blindspot) => ({
        value: blindspot.id,
        label: `${blindspot.severity.toUpperCase()} · ${blindspot.description.slice(0, 32)}`,
      })),
    ],
    [blindspots]
  );

  const productOptions = useMemo(
    () =>
      entities
        .filter((entity) => entity.type === "product" || entity.type === "company")
        .map((entity) => ({ value: entity.id, label: entity.name })),
    [entities],
  );

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<string | null>(null);
  const [assignee, setAssignee] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [productId, setProductId] = useState<string | null>(null);
  const [project, setProject] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [linkedEntities, setLinkedEntities] = useState<string[]>([]);
  const [acceptanceCriteriaText, setAcceptanceCriteriaText] = useState("");
  const [assigneeRoleId, setAssigneeRoleId] = useState<string | null>(null);
  const [linkedProtocol, setLinkedProtocol] = useState("");
  const [linkedBlindspot, setLinkedBlindspot] = useState<string | null>(null);
  const [dispatcher, setDispatcher] = useState<string | null>(null);
  const [planId, setPlanId] = useState("");
  const [planOrder, setPlanOrder] = useState("");
  const [parentTaskId, setParentTaskId] = useState("");
  const [dependsOnTaskIds, setDependsOnTaskIds] = useState("");
  const [blockedBy, setBlockedBy] = useState("");
  const [blockedReason, setBlockedReason] = useState("");
  const [sourceMetadataText, setSourceMetadataText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function resetForm() {
    setTitle("");
    setDescription("");
    setPriority(null);
    setAssignee("");
    setDueDate("");
    setProductId(null);
    setProject("");
    setShowAdvanced(false);
    setLinkedEntities([]);
    setAcceptanceCriteriaText("");
    setAssigneeRoleId(null);
    setLinkedProtocol("");
    setLinkedBlindspot(null);
    setDispatcher(null);
    setPlanId("");
    setPlanOrder("");
    setParentTaskId("");
    setDependsOnTaskIds("");
    setBlockedBy("");
    setBlockedReason("");
    setSourceMetadataText("");
    setError(null);
  }

  function handleClose() {
    resetForm();
    onClose();
  }

  async function handleSubmit() {
    if (!title.trim()) return;
    if (!productId) {
      setError("協作主軸為必填");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      let sourceMetadata: Record<string, unknown> | undefined;
      if (sourceMetadataText.trim()) {
        try {
          sourceMetadata = JSON.parse(sourceMetadataText);
        } catch {
          throw new Error("source metadata 必須是合法 JSON");
        }
      }

      const acceptanceCriteria = parseMultilineItems(acceptanceCriteriaText);
      const dependsOn = parseCommaSeparatedIds(dependsOnTaskIds);
      const blockedByIds = parseCommaSeparatedIds(blockedBy);

      const selectedProduct = entities.find((entity) => entity.id === productId);
      const data: TaskCreateData = { title: title.trim(), product_id: productId };
      if (description.trim()) data.description = description.trim();
      if (priority) data.priority = priority;
      if (assignee.trim()) data.assignee = assignee.trim();
      if (dueDate) data.due_date = dueDate;
      data.project = selectedProduct?.name ?? (project.trim() || "");
      if (linkedEntities.length > 0) data.linked_entities = linkedEntities;
      if (acceptanceCriteria.length > 0) data.acceptance_criteria = acceptanceCriteria;
      if (assigneeRoleId) data.assignee_role_id = assigneeRoleId;
      if (linkedProtocol.trim()) data.linked_protocol = linkedProtocol.trim();
      if (linkedBlindspot) data.linked_blindspot = linkedBlindspot;
      if (dispatcher) data.dispatcher = dispatcher;
      if (planId.trim()) data.plan_id = planId.trim();
      if (planOrder.trim()) data.plan_order = Number(planOrder);
      if (parentTaskId.trim()) data.parent_task_id = parentTaskId.trim();
      if (dependsOn.length > 0) data.depends_on_task_ids = dependsOn;
      if (blockedByIds.length > 0) data.blocked_by = blockedByIds;
      if (blockedReason.trim()) data.blocked_reason = blockedReason.trim();
      if (sourceMetadata) data.source_metadata = sourceMetadata;

      await onCreateTask(data);
      resetForm();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "建立失敗，請重試");
    } finally {
      setSubmitting(false);
    }
  }

  const linkedEntitiesLabel =
    linkedEntities.length > 0 ? `關聯節點 (${linkedEntities.length})` : "選擇關聯節點";

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

        <FormField t={t} label="協作主軸" required htmlFor="task-product">
          <Select
            t={t}
            id="task-product"
            value={productId}
            onChange={setProductId}
            options={productOptions}
            placeholder="選擇產品或客戶"
            aria-label="Task collaboration root"
            invalid={!productId && Boolean(error)}
          />
        </FormField>

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

          <FormField t={t} label="產品" htmlFor="task-product">
            <Input
              t={t}
              id="task-product"
              value={project}
              onChange={setProject}
              placeholder="產品名稱"
            />
          </FormField>
        </div>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <div style={{ fontFamily: fontMono, fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase", color: c.inkFaint }}>
            Rich Task Fields
          </div>
          <Btn
            t={t}
            variant="ghost"
            size="sm"
            onClick={() => setShowAdvanced((prev) => !prev)}
          >
            {showAdvanced ? "收起進階欄位" : "展開進階欄位"}
          </Btn>
        </div>

        {showAdvanced && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 16,
              padding: 16,
              border: `1px solid ${c.inkHair}`,
              borderRadius: radius,
              background: c.paperWarm,
            }}
          >
            <FormField t={t} label="關聯節點">
              <Dropdown<string>
                t={t}
                multiple
                selected={linkedEntities}
                items={entityItems}
                onSelect={setLinkedEntities}
                aria-label="Linked entities"
                trigger={
                  <button
                    type="button"
                    style={{
                      width: "100%",
                      textAlign: "left",
                      padding: "9px 12px",
                      fontFamily: fontBody,
                      fontSize: 13,
                      color: linkedEntities.length > 0 ? c.ink : c.inkFaint,
                      background: c.surfaceHi,
                      border: `1px solid ${c.inkHair}`,
                      borderRadius: radius,
                      cursor: "pointer",
                    }}
                  >
                    {linkedEntitiesLabel}
                  </button>
                }
              />
            </FormField>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <FormField t={t} label="責任角色">
                <Select
                  t={t}
                  value={assigneeRoleId}
                  onChange={setAssigneeRoleId}
                  options={roleOptions}
                  placeholder="選擇 role"
                  clearable
                />
              </FormField>

              <FormField t={t} label="Dispatcher">
                <Select
                  t={t}
                  value={dispatcher}
                  onChange={setDispatcher}
                  options={DISPATCHER_OPTIONS}
                  placeholder="選擇 dispatcher"
                  clearable
                />
              </FormField>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <FormField t={t} label="Plan ID">
                <Input t={t} value={planId} onChange={setPlanId} placeholder="32-char UUID" />
              </FormField>

              <FormField t={t} label="Plan Order">
                <Input t={t} type="number" value={planOrder} onChange={setPlanOrder} placeholder="1" />
              </FormField>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <FormField t={t} label="Parent Task ID">
                <Input t={t} value={parentTaskId} onChange={setParentTaskId} placeholder="subtask 時填入" />
              </FormField>

              <FormField t={t} label="Blindspot">
                <Select
                  t={t}
                  value={linkedBlindspot}
                  onChange={setLinkedBlindspot}
                  options={blindspotOptions}
                  placeholder="選擇 blindspot"
                  clearable
                />
              </FormField>
            </div>

            <FormField t={t} label="Protocol ID">
              <Input t={t} value={linkedProtocol} onChange={setLinkedProtocol} placeholder="目前以穩定 ID 輸入" />
            </FormField>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <FormField t={t} label="Depends On Task IDs">
                <Input t={t} value={dependsOnTaskIds} onChange={setDependsOnTaskIds} placeholder="taskA, taskB" />
              </FormField>

              <FormField t={t} label="Blocked By Task IDs">
                <Input t={t} value={blockedBy} onChange={setBlockedBy} placeholder="taskA, taskB" />
              </FormField>
            </div>

            <FormField t={t} label="Blocked Reason">
              <Input t={t} value={blockedReason} onChange={setBlockedReason} placeholder="有 blocker 時建議填寫" />
            </FormField>

            <FormField t={t} label="Acceptance Criteria（每行一條）">
              <Textarea
                t={t}
                value={acceptanceCriteriaText}
                onChange={setAcceptanceCriteriaText}
                placeholder={"AC-XXX-01 ...\nAC-XXX-02 ..."}
                rows={4}
                resize="vertical"
              />
            </FormField>

            <FormField t={t} label="Source Metadata（JSON）">
              <Textarea
                t={t}
                value={sourceMetadataText}
                onChange={setSourceMetadataText}
                placeholder={'{"created_via_agent": true, "agent_name": "architect"}'}
                rows={4}
                resize="vertical"
              />
            </FormField>
          </div>
        )}

        {error && (
          <p
            style={{
              margin: 0,
              fontSize: 13,
              fontFamily: fontMono,
              color: c.vermillion,
              background: c.vermSoft,
              border: `1px solid ${c.vermLine}`,
              borderRadius: radius,
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
