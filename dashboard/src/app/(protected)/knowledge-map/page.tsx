"use client";

// ZenOS · Knowledge Map — Zen Ink frame + react-force-graph canvas (ink variant)

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useInk } from "@/lib/zen-ink/tokens";
import { Section } from "@/components/zen/Section";
import { Chip } from "@/components/zen/Chip";
import { Btn } from "@/components/zen/Btn";
import { Icon, ICONS } from "@/components/zen/Icons";
import { useAuth } from "@/lib/auth";
import { getAllBlindspots, getAllEntities, getAllRelationships } from "@/lib/api";
import { useToast } from "@/components/zen/Toast";
import type { Blindspot, Entity, Relationship } from "@/types";

const KnowledgeGraph = dynamic(() => import("@/components/KnowledgeGraph"), {
  ssr: false,
  loading: () => null,
});

const TYPE_LABEL: Partial<Record<Entity["type"], string>> = {
  product: "PRODUCT",
  project: "PROJECT",
  module: "MODULE",
  goal: "GOAL",
  role: "ROLE",
  document: "DOCUMENT",
  company: "COMPANY",
  deal: "DEAL",
  person: "PERSON",
};

export default function KnowledgeMapPage() {
  const t = useInk("light");
  const { c, fontHead, fontMono, fontBody } = t;

  // Zen Ink palette for node types
  const inkNodeColors: Record<string, string> = {
    product: c.vermillion,
    project: c.vermillion,
    module: c.ocher,
    goal: c.ocher,
    role: c.ink,
    company: c.jade,
    deal: c.jade,
    person: c.seal,
    document: c.inkMuted,
  };

  const { user } = useAuth();
  const { pushToast } = useToast();

  const [entities, setEntities] = useState<Entity[]>([]);
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [blindspots, setBlindspots] = useState<Blindspot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // focusedId drives graph dim/highlight — only set after user interacts.
  // selectedId drives the Inspector and can auto-init without dimming.
  const [focusedId, setFocusedId] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const token = await user.getIdToken();
      const [e, r, b] = await Promise.all([
        getAllEntities(token),
        getAllRelationships(token),
        getAllBlindspots(token).catch(() => [] as Blindspot[]),
      ]);
      setEntities(e);
      setRelationships(r);
      setBlindspots(b);
    } catch (err) {
      console.error("[KnowledgeMap] fetch failed:", err);
      setError(err instanceof Error ? err.message : "載入失敗");
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  const entityMap = useMemo(() => new Map(entities.map((e) => [e.id, e])), [entities]);

  const blindspotsByEntity = useMemo(() => {
    const map = new Map<string, Blindspot[]>();
    for (const b of blindspots) {
      for (const entityId of b.relatedEntityIds ?? []) {
        const arr = map.get(entityId) ?? [];
        arr.push(b);
        map.set(entityId, arr);
      }
    }
    return map;
  }, [blindspots]);

  const selectedEntity = selectedId ? entityMap.get(selectedId) ?? null : null;
  const selectedRelations = useMemo(
    () =>
      selectedId
        ? relationships.filter(
            (r) => r.sourceEntityId === selectedId || r.targetId === selectedId,
          )
        : [],
    [selectedId, relationships],
  );

  // Visible counts (KnowledgeGraph hides document + project internally)
  const visibleCount = useMemo(
    () => entities.filter((e) => e.type !== "document" && e.type !== "project").length,
    [entities],
  );

  const handleNodeClick = useCallback((entity: Entity) => {
    setSelectedId(entity.id);
    setFocusedId(entity.id);
  }, []);

  const handleBackgroundClick = useCallback(() => {
    setFocusedId(null);
    setSelectedId(null);
  }, []);

  const handleCopyLink = useCallback(() => {
    if (!selectedId) return;
    const url = `${window.location.origin}/knowledge-map?entity=${selectedId}`;
    navigator.clipboard.writeText(url).then(
      () => pushToast({ title: "連結已複製", tone: "success" }),
      () => pushToast({ title: "複製失敗", tone: "error" }),
    );
  }, [selectedId, pushToast]);

  // ── Loading ─────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div
        style={{
          padding: "40px 48px 48px",
          maxWidth: 1600,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          minHeight: 400,
          gap: 16,
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: "50%",
            border: `2px solid ${c.inkHair}`,
            borderTopColor: c.vermillion,
            animation: "spin 0.8s linear infinite",
          }}
        />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        <span
          style={{
            fontFamily: fontMono,
            fontSize: 12,
            color: c.inkMuted,
            letterSpacing: "0.1em",
          }}
        >
          載入知識地圖…
        </span>
      </div>
    );
  }

  // ── Error ───────────────────────────────────────────────────────────────
  if (error) {
    return (
      <div style={{ padding: "40px 48px 48px", maxWidth: 1600 }}>
        <div
          style={{
            background: c.surface,
            border: `1px solid ${c.vermLine}`,
            borderRadius: 2,
            padding: 24,
            display: "flex",
            flexDirection: "column",
            gap: 12,
            maxWidth: 480,
          }}
        >
          <span
            style={{
              fontFamily: fontMono,
              fontSize: 10,
              color: c.vermillion,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
            }}
          >
            載入失敗
          </span>
          <p style={{ fontSize: 13, color: c.ink, margin: 0, lineHeight: 1.6 }}>
            {error}
          </p>
          <Btn t={t} variant="outline" onClick={fetchData}>
            重試
          </Btn>
        </div>
      </div>
    );
  }

  // ── Empty ───────────────────────────────────────────────────────────────
  if (visibleCount === 0) {
    return (
      <div style={{ padding: "40px 48px 48px", maxWidth: 1600 }}>
        <Section
          t={t}
          eyebrow="CONTEXT · 知識"
          title="知識地圖"
          en="Knowledge Map"
          subtitle="所有專案、客戶、文件之間的關係。點擊節點展開 context。"
          right={
            <Chip t={t} tone="muted">
              0 節點
            </Chip>
          }
        />
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            minHeight: 320,
            gap: 10,
            color: c.inkFaint,
            fontFamily: fontMono,
            fontSize: 13,
            letterSpacing: "0.08em",
          }}
        >
          目前沒有節點
        </div>
      </div>
    );
  }

  // ── Main ────────────────────────────────────────────────────────────────
  return (
    <div style={{ padding: "40px 48px 48px", maxWidth: 1600 }}>
      <Section
        t={t}
        eyebrow="CONTEXT · 知識"
        title="知識地圖"
        en="Knowledge Map"
        subtitle="所有專案、客戶、文件之間的關係。點擊節點展開 context。"
        right={
          <div style={{ display: "flex", gap: 10 }}>
            <Chip t={t} tone="muted">
              {visibleCount} 節點 · {relationships.length} 關聯
            </Chip>
            <Btn t={t} variant="outline" icon={ICONS.spark}>
              Agent 詢問此圖
            </Btn>
          </div>
        }
      />

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 340px",
          gap: 16,
          height: "calc(100vh - 260px)",
          minHeight: 560,
        }}
      >
        {/* Canvas — reuse force-graph with Zen Ink variant */}
        <div
          style={{
            position: "relative",
            background: c.paper,
            border: `1px solid ${c.inkHair}`,
            borderRadius: 2,
            overflow: "hidden",
          }}
        >
          <KnowledgeGraph
            entities={entities}
            relationships={relationships}
            blindspotsByEntity={blindspotsByEntity}
            onNodeClick={handleNodeClick}
            onBackgroundClick={handleBackgroundClick}
            focusedNodeId={focusedId}
            variant="ink"
            showLegend
            nodeColorsOverride={inkNodeColors}
            labelFontFamily={fontBody}
            blindspotColor={c.vermillion}
          />
        </div>

        {/* Inspector */}
        <div
          style={{
            background: c.surface,
            border: `1px solid ${c.inkHair}`,
            borderRadius: 2,
            padding: 18,
            overflow: "auto",
            display: "flex",
            flexDirection: "column",
            gap: 14,
          }}
        >
          {selectedEntity ? (
            <>
              {/* Header */}
              <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: "50%",
                    background: c.vermSoft,
                    border: `1px solid ${c.vermLine}`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: c.vermillion,
                    fontSize: 14,
                    fontFamily: fontHead,
                    fontWeight: 500,
                    flexShrink: 0,
                  }}
                >
                  ●
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontFamily: fontMono,
                      fontSize: 10,
                      color: c.inkFaint,
                      letterSpacing: "0.1em",
                      textTransform: "uppercase",
                    }}
                  >
                    {TYPE_LABEL[selectedEntity.type] ?? selectedEntity.type.toUpperCase()}
                  </div>
                  <div
                    style={{
                      fontFamily: fontHead,
                      fontSize: 17,
                      fontWeight: 500,
                      color: c.ink,
                      letterSpacing: "0.02em",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {selectedEntity.name || "—"}
                  </div>
                  <div style={{ fontSize: 12, color: c.inkMuted, marginTop: 2 }}>
                    {selectedEntity.owner ?? "—"}
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div style={{ display: "flex", gap: 6 }}>
                <Btn t={t} variant="ghost" size="sm" icon={ICONS.arrow}>
                  開啟
                </Btn>
                <Btn
                  t={t}
                  variant="ghost"
                  size="sm"
                  icon={ICONS.link}
                  onClick={handleCopyLink}
                >
                  複製連結
                </Btn>
              </div>

              {/* Agent Summary */}
              <div
                style={{
                  background: c.paperWarm,
                  border: `1px solid ${c.inkHair}`,
                  borderRadius: 2,
                  padding: 12,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    marginBottom: 8,
                  }}
                >
                  <Icon d={ICONS.spark} size={12} style={{ color: c.vermillion }} />
                  <span
                    style={{
                      fontFamily: fontMono,
                      fontSize: 10,
                      color: c.inkFaint,
                      letterSpacing: "0.12em",
                      textTransform: "uppercase",
                    }}
                  >
                    Agent Summary
                  </span>
                </div>
                <p
                  style={{
                    fontSize: 12,
                    lineHeight: 1.6,
                    color: c.ink,
                    margin: 0,
                  }}
                >
                  {selectedEntity.summary || "—"}
                </p>
              </div>

              {/* Relations */}
              <div>
                <div
                  style={{
                    fontFamily: fontMono,
                    fontSize: 10,
                    color: c.inkFaint,
                    letterSpacing: "0.12em",
                    textTransform: "uppercase",
                    marginBottom: 8,
                  }}
                >
                  相關 · Relations
                </div>
                {selectedRelations.length === 0 ? (
                  <div
                    style={{
                      fontSize: 12,
                      color: c.inkFaint,
                      fontFamily: fontMono,
                    }}
                  >
                    —
                  </div>
                ) : (
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 4,
                    }}
                  >
                    {selectedRelations.map((rel) => {
                      const otherId =
                        rel.sourceEntityId === selectedId
                          ? rel.targetId
                          : rel.sourceEntityId;
                      const otherEntity = entityMap.get(otherId);
                      const label = otherEntity?.name ?? otherId;
                      const otherType = otherEntity?.type;
                      return (
                        <button
                          key={rel.id}
                          onClick={() => {
                            if (!otherEntity) return;
                            setSelectedId(otherId);
                            setFocusedId(otherId);
                          }}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 10,
                            padding: "6px 8px",
                            borderRadius: 2,
                            background: "transparent",
                            border: "none",
                            color: c.ink,
                            cursor: otherEntity ? "pointer" : "default",
                            fontSize: 12,
                            textAlign: "left",
                            fontFamily: fontBody,
                            width: "100%",
                          }}
                          onMouseEnter={(e) => {
                            if (otherEntity)
                              e.currentTarget.style.background = c.surfaceHi;
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = "transparent";
                          }}
                        >
                          <span
                            style={{
                              width: 6,
                              height: 6,
                              borderRadius: "50%",
                              background: c.ink,
                              flexShrink: 0,
                            }}
                          />
                          <span
                            style={{
                              flex: 1,
                              whiteSpace: "nowrap",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                            }}
                          >
                            {label}
                          </span>
                          <span
                            style={{
                              fontFamily: fontMono,
                              fontSize: 10,
                              color: c.inkFaint,
                              letterSpacing: "0.08em",
                              flexShrink: 0,
                            }}
                          >
                            {otherType
                              ? TYPE_LABEL[otherType] ?? otherType.toUpperCase()
                              : "—"}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Recent activity — P1 */}
              <div>
                <div
                  style={{
                    fontFamily: fontMono,
                    fontSize: 10,
                    color: c.inkFaint,
                    letterSpacing: "0.12em",
                    textTransform: "uppercase",
                    marginBottom: 8,
                  }}
                >
                  近期活動
                </div>
                <div
                  style={{
                    fontSize: 12,
                    color: c.inkFaint,
                    fontFamily: fontMono,
                  }}
                >
                  —
                </div>
              </div>
            </>
          ) : (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flex: 1,
                color: c.inkFaint,
                fontFamily: fontMono,
                fontSize: 12,
                letterSpacing: "0.08em",
              }}
            >
              點擊節點查看詳情
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
