// ZenOS · Zen Ink — Primitive Demo Page
// Route: /_design/primitives
// Shows all 11 primitives + overlay helper in all states (default/hover/focus/disabled/error/active)
// Light mode only. No Tailwind classes used.
"use client";

import React, { useState } from "react";
import { useInk } from "@/lib/zen-ink/tokens";
import { Input } from "@/components/zen/Input";
import { Textarea } from "@/components/zen/Textarea";
import { Select } from "@/components/zen/Select";
import { Dropdown } from "@/components/zen/Dropdown";
import { Checkbox } from "@/components/zen/Checkbox";
import { Radio } from "@/components/zen/Radio";
import { Dialog } from "@/components/zen/Dialog";
import { Drawer } from "@/components/zen/Drawer";
import { Tabs } from "@/components/zen/Tabs";
import { Panel } from "@/components/zen/Panel";
import { Tooltip } from "@/components/zen/Tooltip";
import { ToastProvider, useToast } from "@/components/zen/Toast";
import { Btn } from "@/components/zen/Btn";
import { Chip } from "@/components/zen/Chip";

const PRIORITY_OPTIONS = [
  { value: "critical", label: "Critical", tone: "accent" as const },
  { value: "high", label: "High", tone: "accent" as const },
  { value: "medium", label: "Medium", tone: "ocher" as const },
  { value: "low", label: "Low", tone: "muted" as const },
];

const STATUS_ITEMS = [
  { value: "todo", label: "Todo" },
  { value: "in_progress", label: "In Progress" },
  { value: "review", label: "Review" },
  { value: "done", label: "Done" },
];

function DemoSection({
  title,
  children,
  t,
}: {
  title: string;
  children: React.ReactNode;
  t: ReturnType<typeof useInk>;
}) {
  const { c, fontHead, fontMono } = t;
  return (
    <section style={{ marginBottom: 64 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          marginBottom: 24,
          paddingBottom: 10,
          borderBottom: `1px solid ${c.inkHair}`,
        }}
      >
        <span
          style={{
            fontFamily: fontMono,
            fontSize: 10,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: c.inkFaint,
          }}
        >
          Component
        </span>
        <h2
          style={{
            margin: 0,
            fontFamily: fontHead,
            fontSize: 20,
            fontWeight: 500,
            letterSpacing: "0.02em",
            color: c.ink,
          }}
        >
          {title}
        </h2>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "flex-start" }}>
        {children}
      </div>
    </section>
  );
}

function StateLabel({ t, label }: { t: ReturnType<typeof useInk>; label: string }) {
  const { c, fontMono } = t;
  return (
    <div
      style={{
        fontFamily: fontMono,
        fontSize: 9,
        letterSpacing: "0.14em",
        textTransform: "uppercase",
        color: c.inkFaint,
        marginBottom: 6,
      }}
    >
      {label}
    </div>
  );
}

function StateBox({
  t,
  label,
  children,
}: {
  t: ReturnType<typeof useInk>;
  label: string;
  children: React.ReactNode;
}) {
  const { c } = t;
  return (
    <div style={{ minWidth: 180 }}>
      <StateLabel t={t} label={label} />
      {children}
    </div>
  );
}

export default function PrimitivesDemo() {
  const t = useInk("light");
  return (
    <ToastProvider t={t}>
      <PrimitivesDemoInner />
    </ToastProvider>
  );
}

function ToastDemoSection({ t }: { t: ReturnType<typeof useInk> }) {
  const { showToast, dismissAll } = useToast();
  return (
    <DemoSection title="Toast (queue + a11y)" t={t}>
      <StateBox t={t} label="success · polite">
        <Btn
          t={t}
          variant="outline"
          onClick={() =>
            showToast({
              title: "儲存成功",
              description: "變更已寫入",
              tone: "success",
            })
          }
        >
          Success toast
        </Btn>
      </StateBox>
      <StateBox t={t} label="error · assertive">
        <Btn
          t={t}
          variant="outline"
          onClick={() =>
            showToast({
              title: "儲存失敗",
              description: "連線中斷，請重試",
              tone: "error",
            })
          }
        >
          Error toast
        </Btn>
      </StateBox>
      <StateBox t={t} label="info · polite">
        <Btn
          t={t}
          variant="outline"
          onClick={() =>
            showToast({
              title: "系統通知",
              description: "新版本已就緒",
              tone: "info",
            })
          }
        >
          Info toast
        </Btn>
      </StateBox>
      <StateBox t={t} label="warn · assertive">
        <Btn
          t={t}
          variant="outline"
          onClick={() =>
            showToast({
              title: "即將逾期",
              description: "任務剩 1 小時",
              tone: "warn",
            })
          }
        >
          Warn toast
        </Btn>
      </StateBox>
      <StateBox t={t} label="queue 5 toasts">
        <Btn
          t={t}
          variant="outline"
          onClick={() => {
            const tones = ["success", "error", "info", "warn", "success"] as const;
            tones.forEach((tone, i) =>
              showToast({
                title: `Toast #${i + 1}`,
                description: `Queue 測試 tone=${tone}`,
                tone,
              })
            );
          }}
        >
          Queue 5
        </Btn>
      </StateBox>
      <StateBox t={t} label="dismiss all">
        <Btn t={t} variant="ghost" onClick={dismissAll}>
          Dismiss all
        </Btn>
      </StateBox>
      <StateBox t={t} label="sticky (duration=null)">
        <Btn
          t={t}
          variant="outline"
          onClick={() =>
            showToast({
              title: "不自動關閉",
              description: "按 × 或 Esc 才會消失",
              tone: "info",
              duration: null,
            })
          }
        >
          Sticky toast
        </Btn>
      </StateBox>
    </DemoSection>
  );
}

function PrimitivesDemoInner() {
  const t = useInk("light");
  const { c, fontHead, fontBody, fontMono } = t;

  // Input state
  const [inputVal, setInputVal] = useState("Hello");
  const [textareaVal, setTextareaVal] = useState("Multi-line\ncontent here");
  const [selectVal, setSelectVal] = useState<string | null>("medium");
  const [dropdownSelected, setDropdownSelected] = useState<string[]>([]);
  const [checkA, setCheckA] = useState(true);
  const [checkB, setCheckB] = useState(false);
  const [radioVal, setRadioVal] = useState<string>("medium");
  const [activeTab, setActiveTab] = useState<"overview" | "details" | "history">("overview");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerWithExtras, setDrawerWithExtras] = useState(false);

  return (
    <div
      style={{
        minHeight: "100vh",
        background: c.paper,
        padding: "48px 64px",
        fontFamily: fontBody,
        color: c.ink,
      }}
    >
      {/* Page header */}
      <div style={{ marginBottom: 64 }}>
        <div
          style={{
            fontFamily: fontMono,
            fontSize: 10,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: c.inkFaint,
            marginBottom: 12,
          }}
        >
          Design System · Batch 1
        </div>
        <h1
          style={{
            margin: 0,
            fontFamily: fontHead,
            fontSize: 42,
            fontWeight: 500,
            letterSpacing: "0.02em",
            color: c.ink,
            lineHeight: 1.1,
          }}
        >
          Zen Ink Primitives
        </h1>
        <p
          style={{
            margin: "12px 0 0",
            fontFamily: fontBody,
            fontSize: 14,
            color: c.inkMuted,
            lineHeight: 1.65,
          }}
        >
          11 native primitive components + overlay helper. Light mode. No Radix, no Tailwind.
        </p>
      </div>

      {/* 1. Input */}
      <DemoSection title="Input" t={t}>
        <StateBox t={t} label="default">
          <Input t={t} value={inputVal} onChange={setInputVal} placeholder="Type here..." />
        </StateBox>
        <StateBox t={t} label="empty placeholder">
          <Input t={t} value="" onChange={() => {}} placeholder="Enter task title" />
        </StateBox>
        <StateBox t={t} label="sm size">
          <Input t={t} value="Small input" onChange={() => {}} size="sm" />
        </StateBox>
        <StateBox t={t} label="invalid / error">
          <Input t={t} value="bad email" onChange={() => {}} invalid placeholder="Email" type="email" />
        </StateBox>
        <StateBox t={t} label="disabled">
          <Input t={t} value="Cannot edit" onChange={() => {}} disabled />
        </StateBox>
        <StateBox t={t} label="password">
          <Input t={t} value="secret123" onChange={() => {}} type="password" />
        </StateBox>
      </DemoSection>

      {/* 2. Textarea */}
      <DemoSection title="Textarea" t={t}>
        <StateBox t={t} label="default (body font)">
          <Textarea t={t} value={textareaVal} onChange={setTextareaVal} rows={3} />
        </StateBox>
        <StateBox t={t} label="mono font (CRM email)">
          <Textarea
            t={t}
            value={"Dear customer,\nThank you for your inquiry."}
            onChange={() => {}}
            rows={3}
            fontVariant="mono"
          />
        </StateBox>
        <StateBox t={t} label="invalid">
          <Textarea t={t} value="" onChange={() => {}} invalid placeholder="Required field" rows={2} />
        </StateBox>
        <StateBox t={t} label="disabled">
          <Textarea t={t} value="Read-only content" onChange={() => {}} disabled rows={2} />
        </StateBox>
        <StateBox t={t} label="resize: none">
          <Textarea t={t} value="Fixed height" onChange={() => {}} rows={2} resize="none" />
        </StateBox>
      </DemoSection>

      {/* 3. Select */}
      <DemoSection title="Select (native)" t={t}>
        <StateBox t={t} label="with value">
          <Select
            t={t}
            value={selectVal}
            onChange={setSelectVal}
            options={PRIORITY_OPTIONS}
            placeholder="Select priority"
            clearable
          />
        </StateBox>
        <StateBox t={t} label="null / placeholder">
          <Select
            t={t}
            value={null}
            onChange={() => {}}
            options={PRIORITY_OPTIONS}
            placeholder="Select priority"
          />
        </StateBox>
        <StateBox t={t} label="sm size">
          <Select
            t={t}
            value="low"
            onChange={() => {}}
            options={PRIORITY_OPTIONS}
            size="sm"
          />
        </StateBox>
        <StateBox t={t} label="disabled">
          <Select
            t={t}
            value={null}
            onChange={() => {}}
            options={PRIORITY_OPTIONS}
            disabled
            placeholder="Disabled"
          />
        </StateBox>
        <StateBox t={t} label="invalid">
          <Select
            t={t}
            value={null}
            onChange={() => {}}
            options={PRIORITY_OPTIONS}
            invalid
            placeholder="Select required"
          />
        </StateBox>
      </DemoSection>

      {/* 4. Dropdown */}
      <DemoSection title="Dropdown (custom popover)" t={t}>
        <StateBox t={t} label="single select">
          <Dropdown
            t={t}
            trigger={<Btn t={t} variant="outline">Single Select ▾</Btn>}
            items={STATUS_ITEMS}
            selected={dropdownSelected}
            onSelect={setDropdownSelected}
          />
        </StateBox>
        <StateBox t={t} label="multi select">
          <Dropdown
            t={t}
            trigger={
              <Btn t={t} variant="outline">
                Status ({dropdownSelected.length}) ▾
              </Btn>
            }
            items={STATUS_ITEMS}
            selected={dropdownSelected}
            multiple
            onSelect={setDropdownSelected}
          />
        </StateBox>
        <StateBox t={t} label="disabled">
          <Dropdown
            t={t}
            trigger={<Btn t={t} variant="outline" style={{ opacity: 0.5 }}>Disabled ▾</Btn>}
            items={STATUS_ITEMS}
            selected={[]}
            onSelect={() => {}}
            disabled
          />
        </StateBox>
        <div style={{ minWidth: 180 }}>
          <StateLabel t={t} label="selected values" />
          <div style={{ fontSize: 12, color: c.inkMuted }}>
            {dropdownSelected.length > 0
              ? dropdownSelected.join(", ")
              : "(none selected)"}
          </div>
        </div>
      </DemoSection>

      {/* 5. Checkbox */}
      <DemoSection title="Checkbox" t={t}>
        <StateBox t={t} label="checked">
          <Checkbox t={t} checked={checkA} onChange={setCheckA} label="I agree to the terms" />
        </StateBox>
        <StateBox t={t} label="unchecked">
          <Checkbox t={t} checked={checkB} onChange={setCheckB} label="Subscribe to updates" />
        </StateBox>
        <StateBox t={t} label="disabled checked">
          <Checkbox t={t} checked={true} onChange={() => {}} label="Always required" disabled />
        </StateBox>
        <StateBox t={t} label="disabled unchecked">
          <Checkbox t={t} checked={false} onChange={() => {}} label="Unavailable option" disabled />
        </StateBox>
        <StateBox t={t} label="sm size">
          <Checkbox t={t} checked={true} onChange={() => {}} label="Small checkbox" size="sm" />
        </StateBox>
        <StateBox t={t} label="no label">
          <Checkbox t={t} checked={false} onChange={() => {}} aria-label="Toggle item" />
        </StateBox>
      </DemoSection>

      {/* 6. Radio */}
      <DemoSection title="Radio" t={t}>
        <StateBox t={t} label="radio group">
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {["critical", "high", "medium", "low"].map((v) => (
              <Radio
                key={v}
                t={t}
                name="priority-demo"
                value={v}
                selected={radioVal}
                onChange={setRadioVal}
                label={v.charAt(0).toUpperCase() + v.slice(1)}
              />
            ))}
          </div>
        </StateBox>
        <StateBox t={t} label="disabled">
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <Radio t={t} name="disabled-demo" value="a" selected="a" onChange={() => {}} label="Option A" disabled />
            <Radio t={t} name="disabled-demo" value="b" selected="a" onChange={() => {}} label="Option B" disabled />
          </div>
        </StateBox>
        <StateBox t={t} label="sm size">
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <Radio t={t} name="sm-radio" value="x" selected="x" onChange={() => {}} label="Small X" size="sm" />
            <Radio t={t} name="sm-radio" value="y" selected="x" onChange={() => {}} label="Small Y" size="sm" />
          </div>
        </StateBox>
      </DemoSection>

      {/* 7. Tabs */}
      <DemoSection title="Tabs" t={t}>
        <div style={{ width: "100%" }}>
          <StateLabel t={t} label="underline variant (default)" />
          <Tabs
            t={t}
            value={activeTab}
            onChange={(v) => setActiveTab(v as typeof activeTab)}
            items={[
              { value: "overview" as const, label: "Overview" },
              { value: "details" as const, label: "Details" },
              { value: "history" as const, label: "History", disabled: true },
            ]}
            panels={{
              overview: (
                <div style={{ color: c.inkMuted, fontSize: 13 }}>
                  Overview panel content — default active tab
                </div>
              ),
              details: (
                <div style={{ color: c.inkMuted, fontSize: 13 }}>
                  Details panel content
                </div>
              ),
            }}
          />
        </div>
        <div style={{ width: "100%", marginTop: 32 }}>
          <StateLabel t={t} label="segment variant" />
          <Tabs
            t={t}
            value={activeTab}
            onChange={(v) => setActiveTab(v as typeof activeTab)}
            variant="segment"
            items={[
              { value: "overview" as const, label: "Overview" },
              { value: "details" as const, label: "Details" },
              { value: "history" as const, label: "History", disabled: true },
            ]}
          />
        </div>
      </DemoSection>

      {/* 8. Panel */}
      <DemoSection title="Panel" t={t}>
        <StateBox t={t} label="surface (default)">
          <Panel t={t} padding={20} style={{ width: 220 }}>
            <div style={{ fontSize: 13, color: c.inkMuted }}>Surface panel content</div>
          </Panel>
        </StateBox>
        <StateBox t={t} label="surfaceHi">
          <Panel t={t} variant="surfaceHi" padding={20} style={{ width: 220 }}>
            <div style={{ fontSize: 13, color: c.inkMuted }}>SurfaceHi panel</div>
          </Panel>
        </StateBox>
        <StateBox t={t} label="paperWarm">
          <Panel t={t} variant="paperWarm" padding={20} style={{ width: 220 }}>
            <div style={{ fontSize: 13, color: c.inkMuted }}>PaperWarm panel</div>
          </Panel>
        </StateBox>
        <StateBox t={t} label="no border">
          <Panel t={t} outlined={false} padding={20} style={{ width: 220, background: c.paperWarm }}>
            <div style={{ fontSize: 13, color: c.inkMuted }}>No border panel</div>
          </Panel>
        </StateBox>
      </DemoSection>

      {/* 9. Tooltip */}
      <DemoSection title="Tooltip" t={t}>
        <StateBox t={t} label="top (default)">
          <Tooltip t={t} content="This is a helpful tooltip" side="top">
            <Btn t={t} variant="outline">Hover me (top)</Btn>
          </Tooltip>
        </StateBox>
        <StateBox t={t} label="bottom">
          <Tooltip t={t} content="Tooltip below" side="bottom">
            <Btn t={t} variant="outline">Hover (bottom)</Btn>
          </Tooltip>
        </StateBox>
        <StateBox t={t} label="left">
          <Tooltip t={t} content="Left tooltip" side="left">
            <Btn t={t} variant="outline">Hover (left)</Btn>
          </Tooltip>
        </StateBox>
        <StateBox t={t} label="right">
          <Tooltip t={t} content="Right tooltip" side="right">
            <Btn t={t} variant="outline">Hover (right)</Btn>
          </Tooltip>
        </StateBox>
        <StateBox t={t} label="focus trigger">
          <Tooltip t={t} content="Tab to focus me">
            <button
              style={{
                padding: "7px 14px",
                background: c.surfaceHi,
                border: `1px solid ${c.inkHairBold}`,
                borderRadius: 2,
                fontFamily: fontBody,
                fontSize: 12,
                cursor: "pointer",
                color: c.ink,
              }}
            >
              Tab focus
            </button>
          </Tooltip>
        </StateBox>
      </DemoSection>

      {/* 10. Dialog */}
      <DemoSection title="Dialog (modal)" t={t}>
        <StateBox t={t} label="sm size">
          <Btn t={t} variant="outline" onClick={() => setDialogOpen(true)}>
            Open Dialog
          </Btn>
          <Dialog
            t={t}
            open={dialogOpen}
            onOpenChange={setDialogOpen}
            title="確認操作"
            description="你確定要繼續嗎？這個操作無法復原。"
            size="sm"
            footer={
              <div style={{ display: "flex", gap: 8 }}>
                <Btn t={t} variant="ghost" onClick={() => setDialogOpen(false)}>取消</Btn>
                <Btn t={t} variant="ink" onClick={() => setDialogOpen(false)}>確認</Btn>
              </div>
            }
          >
            <div style={{ fontSize: 13, color: c.inkMuted, lineHeight: 1.6 }}>
              此操作將永久刪除這筆記錄，包括所有相關附件與備注。
            </div>
          </Dialog>
        </StateBox>
        <StateBox t={t} label="md size">
          <Btn t={t} variant="outline" onClick={() => setDialogOpen(true)}>
            Open Dialog (md)
          </Btn>
        </StateBox>
        <StateBox t={t} label="focus trap demo">
          <div style={{ fontSize: 12, color: c.inkMuted }}>
            Tab / Shift+Tab循環在 dialog 內<br />Esc 關閉
          </div>
        </StateBox>
      </DemoSection>

      {/* 11. Drawer */}
      <DemoSection title="Drawer (side panel)" t={t}>
        <StateBox t={t} label="right side (default)">
          <Btn t={t} variant="outline" onClick={() => setDrawerOpen(true)}>
            Open Drawer
          </Btn>
          <Drawer
            t={t}
            open={drawerOpen}
            onOpenChange={setDrawerOpen}
            header={
              <div>
                <div
                  style={{
                    fontFamily: fontHead,
                    fontSize: 15,
                    fontWeight: 500,
                    color: c.ink,
                  }}
                >
                  任務詳情
                </div>
                <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, marginTop: 2 }}>
                  task-abc123
                </div>
              </div>
            }
            footer={
              <div style={{ display: "flex", gap: 8, width: "100%" }}>
                <Btn t={t} variant="ghost" onClick={() => setDrawerOpen(false)}>取消</Btn>
                <Btn t={t} variant="ink">儲存</Btn>
              </div>
            }
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              <div>
                <label style={{ fontSize: 11, color: c.inkMuted, fontFamily: fontBody }}>任務標題</label>
                <Input t={t} value="Follow up on Q3 report" onChange={() => {}} style={{ marginTop: 6 }} />
              </div>
              <div>
                <label style={{ fontSize: 11, color: c.inkMuted, fontFamily: fontBody }}>描述</label>
                <Textarea t={t} value="詳細說明..." onChange={() => {}} rows={4} style={{ marginTop: 6 }} />
              </div>
              <div>
                <label style={{ fontSize: 11, color: c.inkMuted, fontFamily: fontBody }}>優先級</label>
                <Select
                  t={t}
                  value="high"
                  onChange={() => {}}
                  options={PRIORITY_OPTIONS}
                  style={{ marginTop: 6 }}
                />
              </div>
            </div>
          </Drawer>
        </StateBox>

        <StateBox t={t} label="with headerExtras slot">
          <Btn t={t} variant="outline" onClick={() => setDrawerWithExtras(true)}>
            Drawer + headerExtras
          </Btn>
          <Drawer
            t={t}
            open={drawerWithExtras}
            onOpenChange={setDrawerWithExtras}
            header={
              <div style={{ fontFamily: fontHead, fontSize: 15, fontWeight: 500, color: c.ink }}>
                任務詳情 (with extras)
              </div>
            }
            headerExtras={
              <div style={{ display: "flex", gap: 8, paddingTop: 8 }}>
                <Chip t={t} tone="accent" dot>agent:developer</Chip>
                <Chip t={t} tone="muted">in_progress</Chip>
              </div>
            }
          >
            <div style={{ fontSize: 13, color: c.inkMuted }}>
              headerExtras slot is populated with dispatcher badge + status chip.
              <br />
              <br />
              This is the reserved extension point for Task L3 UI (dispatcher badge / handoff timeline tabs).
            </div>
          </Drawer>
        </StateBox>
      </DemoSection>

      {/* 12. Toast */}
      <ToastDemoSection t={t} />

      {/* Token reference */}
      <DemoSection title="Color Tokens (light mode)" t={t}>
        {(
          [
            ["paper", c.paper],
            ["paperWarm", c.paperWarm],
            ["surface", c.surface],
            ["surfaceHi", c.surfaceHi],
            ["ink", c.ink],
            ["inkSoft", c.inkSoft],
            ["inkMuted", c.inkMuted],
            ["inkFaint", c.inkFaint],
            ["inkHair", c.inkHair],
            ["inkHairBold", c.inkHairBold],
            ["vermillion", c.vermillion],
            ["vermSoft", c.vermSoft],
            ["vermLine", c.vermLine],
            ["seal", c.seal],
            ["jade", c.jade],
            ["ocher", c.ocher],
          ] as [string, string][]
        ).map(([name, val]) => (
          <div key={name} style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 2,
                background: val,
                border: `1px solid ${c.inkHair}`,
                flexShrink: 0,
              }}
            />
            <div>
              <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkMuted }}>{name}</div>
              <div style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint }}>{val}</div>
            </div>
          </div>
        ))}
      </DemoSection>
    </div>
  );
}
