"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useMemo, useState } from "react";
import { APP_COPY } from "@/lib/i18n";
import { resolveActiveWorkspace } from "@/lib/partner";

/** Shared workspace surface: shown when isHomeWorkspace=false and workspaceRole is member or guest */
const SHARED_WORKSPACE_NAV_ITEMS = [
  { href: "/knowledge-map", label: "知識地圖" },
  { href: "/projects", label: "Products" },
  { href: "/tasks", label: "Tasks" },
];

/** Full home workspace nav for members */
const MEMBER_NAV_ITEMS = [
  { href: "/knowledge-map", label: "知識地圖" },
  { href: "/projects", label: "專案" },
  { href: "/tasks", label: "任務" },
  { href: "/clients", label: "客戶" },
];

/** Full home workspace nav for owners */
const OWNER_NAV_ITEMS = [
  ...MEMBER_NAV_ITEMS,
  { href: "/team", label: APP_COPY.team },
  { href: "/setup", label: APP_COPY.setup },
];

// ─── Workspace Entry ──────────────────────────────────────────────────────────

interface WorkspaceInfo {
  id: string;
  name: string;
  hasUpdate?: boolean;
}

interface WorkspaceEntryProps {
  availableWorkspaces: WorkspaceInfo[];
  activeWorkspaceId?: string;
  onSwitch?: (workspaceId: string) => void;
}

function WorkspaceEntry({ availableWorkspaces, activeWorkspaceId, onSwitch }: WorkspaceEntryProps) {
  const [open, setOpen] = useState(false);

  if (availableWorkspaces.length <= 1) {
    return (
      <span
        data-testid="workspace-entry-single"
        className="hidden sm:inline-flex items-center rounded-md border border-border/60 bg-secondary/30 px-2.5 py-1 text-xs font-medium text-muted-foreground"
      >
        我的工作區
      </span>
    );
  }

  const active = availableWorkspaces.find((w) => w.id === activeWorkspaceId) ?? availableWorkspaces[0];

  return (
    <div className="relative hidden sm:block" data-testid="workspace-entry-picker">
      <button
        onClick={() => setOpen((prev) => !prev)}
        className="inline-flex items-center gap-1.5 rounded-md border border-border/60 bg-secondary/30 px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/30 hover:text-foreground"
        aria-expanded={open}
        aria-haspopup="listbox"
      >
        {active.name}
        <svg className="h-3 w-3 opacity-60" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
        </svg>
      </button>
      {open && (
        <ul
          role="listbox"
          aria-label="切換工作區"
          className="absolute left-0 top-full z-50 mt-1 min-w-[160px] overflow-hidden rounded-md border border-border bg-card shadow-lg"
        >
          {availableWorkspaces.map((ws) => {
            const isActive = ws.id === active.id;
            return (
              <li key={ws.id} role="option" aria-selected={isActive}>
                <button
                  onClick={() => {
                    onSwitch?.(ws.id);
                    setOpen(false);
                  }}
                  className={`flex w-full items-center justify-between px-3 py-2 text-xs transition-colors hover:bg-secondary/60 ${isActive ? "text-primary" : "text-foreground"}`}
                >
                  <span>{ws.name}</span>
                  {ws.hasUpdate && !isActive && (
                    <span
                      data-testid={`workspace-badge-${ws.id}`}
                      className="ml-2 h-1.5 w-1.5 rounded-full bg-primary"
                      aria-label="有更新"
                    />
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export function AppNav() {
  const pathname = usePathname();
  const { partner, signOut } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  const { isHomeWorkspace, workspaceRole } = resolveActiveWorkspace(partner);

  // Two-stage nav decision:
  // Stage 1 — isHomeWorkspace gate: shared workspaces get restricted surface
  // Stage 2 — workspaceRole gate: within home workspace, role determines nav depth
  const navItems = useMemo(() => {
    if (!isHomeWorkspace) {
      // Shared workspace: always show the restricted shared surface regardless of role
      return SHARED_WORKSPACE_NAV_ITEMS;
    }
    // Home workspace: full surface, gated by role.
    // guest within home workspace is an edge case (spec says it shouldn't occur);
    // fallback to OWNER_NAV_ITEMS to avoid blank nav.
    if (workspaceRole === "member") return MEMBER_NAV_ITEMS;
    return OWNER_NAV_ITEMS;
  }, [isHomeWorkspace, workspaceRole]);

  // Workspace entry: derive available workspaces from partner data.
  // Partner.availableWorkspaces is not yet defined in the backend (pending S04/S05).
  // Until then, we derive a single-workspace list from the current partner context,
  // so the entry always renders correctly and won't crash when the field is absent.
  const availableWorkspaces = useMemo<WorkspaceInfo[]>(() => {
    const raw = (partner as unknown as { availableWorkspaces?: WorkspaceInfo[] })?.availableWorkspaces;
    if (Array.isArray(raw) && raw.length > 0) return raw;
    return [{ id: partner?.id ?? "home", name: "我的工作區" }];
  }, [partner]);

  if (!partner) return null;

  return (
    <header className="sticky top-0 z-50 border-b border-border/80 bg-background/72 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-3 sm:gap-6">
          <Link
            href="/tasks"
            className="flex items-center gap-2 rounded-md transition-opacity hover:opacity-95"
            aria-label="ZenOS 首頁"
          >
            <img
              src="/brand/zenos-mark.png"
              alt=""
              width={360}
              height={360}
              className="h-8 w-8 rounded-[0.7rem] object-cover object-left shadow-[0_0_0_1px_rgba(23,49,77,0.65)] sm:h-9 sm:w-9"
            />
            <span className="text-[1.55rem] font-semibold tracking-[-0.045em] leading-none text-foreground">
              Zen
              <span className="bg-[linear-gradient(135deg,#7af3e2_0%,#36e1ca_55%,#21c7b5_100%)] bg-clip-text text-transparent">
                OS
              </span>
            </span>
          </Link>
          <WorkspaceEntry availableWorkspaces={availableWorkspaces} activeWorkspaceId={partner.id} />
          <nav className="hidden md:flex items-center gap-1">
            {navItems.map(({ href, label }) => {
              const isActive = pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={`rounded-md px-3 py-1.5 text-sm transition-all ${
                    isActive
                      ? "bg-primary/18 text-primary shadow-[inset_0_0_0_1px_rgba(54,225,202,0.2)]"
                      : "text-muted-foreground hover:bg-secondary/70 hover:text-foreground"
                  }`}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="flex items-center gap-4">
          <span className="hidden sm:inline text-sm text-muted-foreground">
            {partner.displayName}
          </span>
          <button
            onClick={signOut}
            className="hidden cursor-pointer text-sm text-muted-foreground transition-transform active:scale-95 hover:text-primary sm:inline"
          >
            {APP_COPY.signOut}
          </button>
          <button
            onClick={() => setMobileOpen((prev) => !prev)}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-border bg-card/70 text-muted-foreground transition-all active:scale-95 hover:border-primary/30 hover:text-foreground hover:bg-secondary/60 md:hidden"
            aria-label={mobileOpen ? "關閉選單" : "開啟選單"}
            aria-expanded={mobileOpen}
          >
            {mobileOpen ? "✕" : "☰"}
          </button>
        </div>
      </div>
      {mobileOpen && (
        <div className="border-t border-border bg-card/95 md:hidden">
          <nav className="flex flex-col px-4 py-2">
            {navItems.map(({ href, label }) => {
              const isActive = pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setMobileOpen(false)}
                  className={`rounded-md px-3 py-2 text-sm transition-all ${
                    isActive
                      ? "bg-primary/18 text-primary shadow-[inset_0_0_0_1px_rgba(54,225,202,0.2)]"
                      : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground"
                  }`}
                >
                  {label}
                </Link>
              );
            })}
            <div className="mt-2 flex items-center justify-between border-t border-border pt-2">
              <span className="text-sm text-muted-foreground">{partner.displayName}</span>
              <button
                onClick={signOut}
                className="cursor-pointer text-sm text-muted-foreground transition-transform active:scale-95 hover:text-primary"
              >
                {APP_COPY.signOut}
              </button>
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
