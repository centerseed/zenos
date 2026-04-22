"use client";

import React from "react";
import type { TaskComment, HandoffEvent } from "@/types";
import { useInk } from "@/lib/zen-ink/tokens";
import { Btn } from "./zen/Btn";
import { Chip } from "./zen/Chip";
import { Textarea } from "./zen/Textarea";
import { CornerUpRight, MessageSquare, Trash2 } from "lucide-react";

interface TaskHistoryPanelProps {
  handoffEvents?: HandoffEvent[];
  dispatcherLabel: (value: string | null | undefined) => string;
  dispatcherChipTone: (value: string | null | undefined) => "muted" | "jade" | "ocher" | "accent" | "plain";
  comments: TaskComment[];
  commentsError: string | null;
  newComment: string;
  onNewCommentChange: (value: string) => void;
  onSubmitComment: () => void;
  commentSubmitting: boolean;
  canDeleteComment: (comment: TaskComment) => boolean;
  onDeleteComment: (commentId: string) => void;
}

export function TaskHistoryPanel({
  handoffEvents = [],
  dispatcherLabel,
  dispatcherChipTone,
  comments,
  commentsError,
  newComment,
  onNewCommentChange,
  onSubmitComment,
  commentSubmitting,
  canDeleteComment,
  onDeleteComment,
}: TaskHistoryPanelProps) {
  const t = useInk("light");
  const { c } = t;

  return (
    <div data-testid="task-history-panel" style={{ display: "flex", flexDirection: "column", gap: 28 }}>
      {handoffEvents.length > 0 && (
        <section>
          <SectionLabel label="Handoff Chain" color={c.ocher} />
          <ol
            style={{
              listStyle: "none",
              margin: 0,
              padding: 0,
              borderLeft: `2px solid ${c.inkHair}`,
              marginLeft: 8,
              display: "flex",
              flexDirection: "column",
              gap: 0,
            }}
          >
            {handoffEvents.map((event, idx) => {
              const at = new Date(event.at);
              const fromLabel = dispatcherLabel(event.fromDispatcher);
              const toLabel = dispatcherLabel(event.toDispatcher);
              return (
                <li key={idx} style={{ position: "relative", paddingLeft: 20, paddingBottom: idx < handoffEvents.length - 1 ? 16 : 0 }}>
                  <span
                    style={{
                      position: "absolute",
                      left: -7,
                      top: 4,
                      width: 12,
                      height: 12,
                      borderRadius: "50%",
                      border: `2px solid ${c.inkHairBold}`,
                      background: c.surface,
                    }}
                  />
                  <div
                    style={{
                      background: c.paperWarm,
                      border: `1px solid ${c.inkHair}`,
                      borderRadius: t.radius,
                      padding: 10,
                      display: "flex",
                      flexDirection: "column",
                      gap: 6,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                      <Chip t={t} tone={dispatcherChipTone(event.fromDispatcher)}>{fromLabel}</Chip>
                      <CornerUpRight style={{ width: 10, height: 10, color: c.inkFaint }} />
                      <Chip t={t} tone={dispatcherChipTone(event.toDispatcher)}>{toLabel}</Chip>
                      <span style={{ marginLeft: "auto", fontFamily: t.fontMono, fontSize: 9, color: c.inkFaint }}>
                        {at.toLocaleString("zh-TW", { hour12: false })}
                      </span>
                    </div>
                    <p style={{ fontFamily: t.fontBody, fontSize: 12, color: c.ink, lineHeight: 1.6, margin: 0 }}>{event.reason}</p>
                    {event.outputRef && (
                      <p style={{ fontFamily: t.fontMono, fontSize: 10, color: c.inkMuted, margin: 0, wordBreak: "break-all" }}>↳ {event.outputRef}</p>
                    )}
                    {event.notes && (
                      <p style={{ fontFamily: t.fontBody, fontSize: 10, color: c.inkFaint, lineHeight: 1.6, whiteSpace: "pre-wrap", margin: 0 }}>{event.notes}</p>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        </section>
      )}

      <section>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <div style={{ width: 3, height: 16, borderRadius: 999, background: c.inkHairBold, flexShrink: 0 }} />
          <span style={{ fontFamily: t.fontMono, fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.16em", color: c.inkMuted }}>
            留言
          </span>
          <MessageSquare style={{ width: 11, height: 11, color: c.inkFaint }} />
        </div>

        {commentsError ? (
          <p style={{ fontFamily: t.fontBody, fontSize: 12, color: c.vermillion }}>{commentsError}</p>
        ) : comments.length === 0 ? (
          <p style={{ fontFamily: t.fontBody, fontSize: 12, color: c.inkFaint }}>尚無留言</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 16 }}>
            {comments.map((comment) => (
              <div key={comment.id} style={{ display: "flex", gap: 10 }}>
                <div
                  style={{
                    flexShrink: 0,
                    width: 26,
                    height: 26,
                    borderRadius: "50%",
                    background: c.paperWarm,
                    border: `1px solid ${c.inkHair}`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontFamily: t.fontMono,
                    fontSize: 10,
                    fontWeight: 700,
                    color: c.inkMuted,
                  }}
                >
                  {comment.authorName.charAt(0).toUpperCase()}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 4 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontFamily: t.fontBody, fontSize: 12, fontWeight: 600, color: c.ink }}>{comment.authorName}</span>
                      <span style={{ fontFamily: t.fontMono, fontSize: 10, color: c.inkFaint }}>
                        {comment.createdAt.toLocaleString("zh-TW")}
                      </span>
                    </div>
                    {canDeleteComment(comment) && (
                      <button
                        onClick={() => onDeleteComment(comment.id)}
                        title="刪除留言"
                        style={{
                          padding: 4,
                          borderRadius: t.radius,
                          border: "none",
                          background: "transparent",
                          color: c.inkFaint,
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                        }}
                      >
                        <Trash2 style={{ width: 11, height: 11 }} />
                      </button>
                    )}
                  </div>
                  <p style={{ fontFamily: t.fontBody, fontSize: 13, color: c.inkMuted, lineHeight: 1.6, margin: 0, whiteSpace: "pre-wrap" }}>
                    {comment.content}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <Textarea
            t={t}
            value={newComment}
            onChange={onNewCommentChange}
            placeholder="新增留言..."
            rows={2}
            resize="none"
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                onSubmitComment();
              }
            }}
          />
          <Btn
            t={t}
            variant="ink"
            size="sm"
            onClick={onSubmitComment}
            style={{ opacity: !newComment.trim() || commentSubmitting ? 0.4 : 1, cursor: !newComment.trim() || commentSubmitting ? "not-allowed" : "pointer" }}
          >
            {commentSubmitting ? "送出中..." : "送出留言"}
          </Btn>
        </div>
      </section>
    </div>
  );
}

function SectionLabel({ label, color }: { label: string; color: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
      <div style={{ width: 3, height: 16, borderRadius: 999, background: color, flexShrink: 0 }} />
      <span
        style={{
          fontFamily: "var(--font-mono, ui-monospace, monospace)",
          fontSize: 10,
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: "0.16em",
        }}
      >
        {label}
      </span>
    </div>
  );
}
