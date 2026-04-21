"use client";

// ZenOS · Zen Ink — ZenShell (sidebar navigation)
// Ported 1:1 from design-ref/components.jsx Shell element
// activeNav derived from usePathname(), navigation via useRouter().push()

import React, { useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useInk } from "@/lib/zen-ink/tokens";
import { useAuth } from "@/lib/auth";
import { setActiveWorkspaceId } from "@/lib/api";
import { resolveActiveWorkspace } from "@/lib/partner";
import { InkMark } from "./InkMark";
import { Icon, ICONS } from "./Icons";
import { CmdK } from "./CmdK";
import { Dropdown } from "./Dropdown";

// Nav mapping: key → path
const NAV_PATHS: Record<string, string> = {
  map:       "/knowledge-map",
  home:      "/home",
  tasks:     "/tasks",
  projects:  "/projects",
  clients:   "/clients",
  marketing: "/marketing",
  docs:      "/docs",
  team:      "/team",
  agent:     "/agent",
  settings:  "/settings",
};

// Derive nav key from current pathname
function pathToNavKey(pathname: string): string {
  for (const [key, path] of Object.entries(NAV_PATHS)) {
    if (pathname.startsWith(path)) return key;
  }
  return "map";
}

interface ZenShellProps {
  children: React.ReactNode;
}

export function ZenShell({ children }: ZenShellProps) {
  const t = useInk("light");
  const { c, fontHead, fontBody, fontMono, mode } = t;
  const pathname = usePathname();
  const router = useRouter();
  const { partner, refetchPartner } = useAuth();
  const [cmdKOpen, setCmdKOpen] = useState(false);

  const activeNav = pathToNavKey(pathname);

  const { isHomeWorkspace } = resolveActiveWorkspace(partner);
  // Shared workspace → 只看到知識地圖 / 產品 / 任務
  const SHARED_NAV_KEYS = ["map", "projects", "tasks"] as const;

  const displayName = partner?.displayName?.trim() || partner?.email?.split("@")[0] || "—";
  const initial = displayName[0]?.toUpperCase() ?? "—";
  const availableWorkspaces = useMemo(
    () => partner?.availableWorkspaces ?? [],
    [partner?.availableWorkspaces]
  );
  const activeWorkspace =
    availableWorkspaces.find((w) => w.id === (partner?.activeWorkspaceId ?? partner?.homeWorkspaceId)) ??
    availableWorkspaces[0];
  const activeWorkspaceName = activeWorkspace?.name ?? "—";
  const hasWorkspaceToRender = availableWorkspaces.length >= 1;

  const handleSwitchWorkspace = async (nextIds: string[]) => {
    const id = nextIds[0];
    if (!id || id === activeWorkspace?.id) return;
    setActiveWorkspaceId(id);
    await refetchPartner();
    // 切換後強制重整頁面，確保知識地圖等 data view 走新 workspace scope 重新載入
    if (typeof window !== "undefined") {
      window.location.reload();
    }
  };

  const allNav = [
    { k: "map",       zh: "知識地圖",  en: "Knowledge",  icon: ICONS.map },
    { k: "home",      zh: "今日",      en: "Today",      icon: ICONS.zen },
    { k: "tasks",     zh: "任務",      en: "Tasks",      icon: ICONS.task },
    { k: "projects",  zh: "產品",      en: "Products",   icon: ICONS.folder },
    { k: "projects",  zh: "產品",      en: "Products",   icon: ICONS.folder },
    { k: "clients",   zh: "客戶",      en: "Clients",    icon: ICONS.users },
    { k: "marketing", zh: "行銷",      en: "Growth",     icon: ICONS.trend },
    { k: "docs",      zh: "文件",      en: "Docs",       icon: ICONS.doc },
  ];
  const nav = isHomeWorkspace
    ? allNav
    : allNav.filter((n) => (SHARED_NAV_KEYS as readonly string[]).includes(n.k));

  const secondaryNav = isHomeWorkspace
    ? [
        { k: "team", zh: "團隊", en: "Team", icon: ICONS.users },
        { k: "agent", zh: "Agent·MCP", en: "Agents", icon: ICONS.spark },
        { k: "settings", zh: "設定", en: "Settings", icon: ICONS.settings },
      ]
    : [];

  return (
    <>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "240px 1fr",
          height: "100vh",
          background: c.paper,
          color: c.ink,
          fontFamily: fontBody,
          letterSpacing: "0.005em",
        }}
      >
        <aside
          style={{
            borderRight: `1px solid ${c.inkHair}`,
            padding: "24px 18px 18px",
            display: "flex",
            flexDirection: "column",
            background: c.paperWarm,
          }}
        >
          {/* Brand */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              marginBottom: 22,
            }}
          >
            <InkMark size={30} ink={c.ink} seal={c.seal} sealInk={c.sealInk} />
            <div
              style={{
                fontFamily: fontHead,
                fontSize: 18,
                fontWeight: 500,
                letterSpacing: "0.05em",
                color: c.ink,
              }}
            >
              ZenOS
            </div>
          </div>

          {/* Workspace switcher — prominent button */}
          {hasWorkspaceToRender && (
            <Dropdown
              t={t}
              selected={activeWorkspace ? [activeWorkspace.id] : []}
              onSelect={handleSwitchWorkspace}
              maxWidth={220}
              align="left"
              aria-label="切換工作區"
              items={availableWorkspaces.map((w) => ({
                value: w.id,
                label: w.name,
              }))}
              trigger={
                <button
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    width: "100%",
                    padding: "8px 12px",
                    marginBottom: 14,
                    background: c.surface,
                    border: `1px solid ${c.inkHair}`,
                    borderRadius: 2,
                    cursor: "pointer",
                    fontFamily: fontBody,
                    transition: "border-color .15s, background .15s",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = c.inkHairBold;
                    e.currentTarget.style.background = c.surfaceHi;
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = c.inkHair;
                    e.currentTarget.style.background = c.surface;
                  }}
                >
                  <span
                    style={{
                      fontFamily: fontMono,
                      fontSize: 9,
                      color: c.inkFaint,
                      letterSpacing: "0.2em",
                      textTransform: "uppercase",
                    }}
                  >
                    WS
                  </span>
                  <span
                    style={{
                      flex: 1,
                      textAlign: "left",
                      fontSize: 13,
                      color: c.ink,
                      fontWeight: 500,
                      letterSpacing: "0.02em",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {activeWorkspaceName}
                  </span>
                  <svg
                    width="12"
                    height="12"
                    viewBox="0 0 20 20"
                    fill={c.inkMuted}
                    aria-hidden="true"
                  >
                    <path
                      fillRule="evenodd"
                      d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
                      clipRule="evenodd"
                    />
                  </svg>
                </button>
              }
            />
          )}

          {/* ⌘K */}
          <button
            onClick={() => setCmdKOpen(true)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "9px 12px",
              marginBottom: 22,
              background: c.surface,
              border: `1px solid ${c.inkHair}`,
              borderRadius: 2,
              color: c.inkMuted,
              fontSize: 12,
              fontFamily: fontBody,
              cursor: "pointer",
              width: "100%",
              transition: "all .15s",
            }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.borderColor = c.inkHairBold)
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.borderColor = c.inkHair)
            }
          >
            <Icon d={ICONS.search} size={13} />
            <span
              style={{
                flex: 1,
                textAlign: "left",
                letterSpacing: "0.01em",
              }}
            >
              搜尋 · 指令
            </span>
            <kbd
              style={{
                fontFamily: fontMono,
                fontSize: 10,
                color: c.inkFaint,
              }}
            >
              ⌘K
            </kbd>
          </button>

          {/* Nav label */}
          <div
            style={{
              fontFamily: fontMono,
              fontSize: 9,
              color: c.inkFaint,
              letterSpacing: "0.2em",
              textTransform: "uppercase",
              padding: "0 4px 10px",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <span>Navigation</span>
            <div style={{ flex: 1, height: 1, background: c.inkHair }} />
          </div>

          {/* Nav items */}
          {nav.map((it) => {
            const active = activeNav === it.k;
            return (
              <button
                key={it.k}
                onClick={() => router.push(NAV_PATHS[it.k])}
                style={{
                  display: "grid",
                  gridTemplateColumns: "18px 1fr auto",
                  alignItems: "center",
                  gap: 12,
                  padding: "9px 10px",
                  background: active ? c.surface : "transparent",
                  border: "none",
                  borderLeft: active
                    ? `2px solid ${c.vermillion}`
                    : "2px solid transparent",
                  color: active ? c.ink : c.inkMuted,
                  cursor: "pointer",
                  textAlign: "left",
                  fontFamily: fontBody,
                  transition: "all .15s",
                }}
                onMouseEnter={(e) => {
                  if (!active) e.currentTarget.style.color = c.ink;
                }}
                onMouseLeave={(e) => {
                  if (!active) e.currentTarget.style.color = c.inkMuted;
                }}
              >
                <Icon d={it.icon} size={14} stroke={active ? 1.8 : 1.4} />
                <span
                  style={{
                    fontSize: 13,
                    fontWeight: active ? 500 : 400,
                    letterSpacing: "0.04em",
                  }}
                >
                  {it.zh}
                </span>
                <span
                  style={{
                    fontFamily: fontMono,
                    fontSize: 10,
                    color: c.inkFaint,
                    letterSpacing: "0.08em",
                  }}
                >
                  {it.en}
                </span>
              </button>
            );
          })}

          {secondaryNav.length > 0 && (
            <div
              style={{
                fontFamily: fontMono,
                fontSize: 9,
                color: c.inkFaint,
                letterSpacing: "0.2em",
                textTransform: "uppercase",
                padding: "18px 4px 10px",
                marginTop: 10,
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <span>Workspace</span>
              <div style={{ flex: 1, height: 1, background: c.inkHair }} />
            </div>
          )}

          {secondaryNav.map((it) => {
            const active = activeNav === it.k;
            return (
              <button
                key={it.k}
                onClick={() => router.push(NAV_PATHS[it.k])}
                style={{
                  display: "grid",
                  gridTemplateColumns: "18px 1fr auto",
                  alignItems: "center",
                  gap: 12,
                  padding: "9px 10px",
                  background: active ? c.surface : "transparent",
                  border: "none",
                  borderLeft: active
                    ? `2px solid ${c.vermillion}`
                    : "2px solid transparent",
                  color: active ? c.ink : c.inkMuted,
                  cursor: "pointer",
                  textAlign: "left",
                  fontFamily: fontBody,
                  transition: "all .15s",
                }}
                onMouseEnter={(e) => {
                  if (!active) e.currentTarget.style.color = c.ink;
                }}
                onMouseLeave={(e) => {
                  if (!active) e.currentTarget.style.color = c.inkMuted;
                }}
              >
                <Icon d={it.icon} size={14} stroke={active ? 1.8 : 1.4} />
                <span
                  style={{
                    fontSize: 13,
                    fontWeight: active ? 500 : 400,
                    letterSpacing: "0.04em",
                  }}
                >
                  {it.zh}
                </span>
                <span
                  style={{
                    fontFamily: fontMono,
                    fontSize: 10,
                    color: c.inkFaint,
                    letterSpacing: "0.08em",
                  }}
                >
                  {it.en}
                </span>
              </button>
            );
          })}

          <div style={{ flex: 1 }} />

          {/* Footer · account + mode toggle */}
          <div
            style={{
              padding: "14px 4px 4px",
              borderTop: `1px solid ${c.inkHair}`,
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: "50%",
                background: c.vermSoft,
                border: `1px solid ${c.vermLine}`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontFamily: fontHead,
                fontSize: 12,
                color: c.vermillion,
                fontWeight: 600,
              }}
            >
              {initial}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontFamily: fontBody,
                  fontSize: 12.5,
                  color: c.ink,
                  fontWeight: 500,
                  letterSpacing: "0.02em",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {displayName}
              </div>
              <div
                style={{
                  fontFamily: fontMono,
                  fontSize: 9,
                  color: c.inkFaint,
                  letterSpacing: "0.14em",
                  textTransform: "uppercase",
                  marginTop: 1,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {isHomeWorkspace ? "OWNER" : "GUEST"}
              </div>
            </div>
            {/* Mode toggle — no-op for now, light mode only */}
            <button
              onClick={() => {
                // Phase 2: no-op. Full dark mode toggle is Phase 3+.
              }}
              style={{
                background: "transparent",
                border: `1px solid ${c.inkHair}`,
                borderRadius: 2,
                padding: 6,
                color: c.inkMuted,
                cursor: "pointer",
              }}
            >
              <Icon
                d={mode === "dark" ? ICONS.sun : ICONS.moon}
                size={14}
              />
            </button>
          </div>
        </aside>

        <main style={{ overflow: "auto", position: "relative" }}>
          {children}
        </main>
      </div>

      {/* CmdK modal */}
      <CmdK t={t} open={cmdKOpen} onClose={() => setCmdKOpen(false)} />
    </>
  );
}
