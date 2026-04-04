"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useMemo, useState } from "react";
import { APP_COPY } from "@/lib/i18n";

const BASE_NAV_ITEMS = [
  { href: "/knowledge-map", label: "知識地圖" },
  { href: "/projects", label: "專案" },
  { href: "/tasks", label: "任務" },
  { href: "/clients", label: "客戶" },
];

const SCOPED_NAV_ITEMS = [
  { href: "/projects", label: "專案" },
  { href: "/tasks", label: "任務" },
];

const ADMIN_NAV_ITEMS = [{ href: "/team", label: APP_COPY.team }];

const TAIL_NAV_ITEMS = [{ href: "/setup", label: APP_COPY.setup }];

export function AppNav() {
  const pathname = usePathname();
  const { partner, signOut } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  const isScoped = !partner?.isAdmin && (partner?.authorizedEntityIds?.length ?? 0) > 0;

  const navItems = useMemo(() => {
    if (isScoped) {
      return SCOPED_NAV_ITEMS;
    }
    const items = [...BASE_NAV_ITEMS];
    if (partner?.isAdmin) {
      items.push(...ADMIN_NAV_ITEMS);
    }
    items.push(...TAIL_NAV_ITEMS);
    return items;
  }, [partner?.isAdmin, isScoped]);

  if (!partner) return null;

  return (
    <header className="border-b border-border bg-background/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-12 flex items-center justify-between">
        <div className="flex items-center gap-3 sm:gap-6">
          <Link href="/" className="text-lg font-bold text-foreground">
            ZenOS
          </Link>
          <nav className="hidden md:flex items-center gap-1">
            {navItems.map(({ href, label }) => {
              const isActive = pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={`px-3 py-1.5 rounded text-sm transition-colors ${
                    isActive
                      ? "bg-secondary text-foreground"
                      : "text-muted-foreground hover:text-foreground hover:bg-secondary/60"
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
            className="hidden sm:inline text-sm text-muted-foreground hover:text-foreground cursor-pointer active:scale-95 transition-transform"
          >
            {APP_COPY.signOut}
          </button>
          <button
            onClick={() => setMobileOpen((prev) => !prev)}
            className="md:hidden inline-flex items-center justify-center h-8 w-8 rounded border border-border text-muted-foreground hover:text-foreground hover:bg-secondary/60 active:scale-95 transition-all"
            aria-label={mobileOpen ? "關閉選單" : "開啟選單"}
            aria-expanded={mobileOpen}
          >
            {mobileOpen ? "✕" : "☰"}
          </button>
        </div>
      </div>
      {mobileOpen && (
        <div className="md:hidden border-t border-border bg-card">
          <nav className="px-4 py-2 flex flex-col">
            {navItems.map(({ href, label }) => {
              const isActive = pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setMobileOpen(false)}
                  className={`px-3 py-2 rounded text-sm transition-colors ${
                    isActive
                      ? "bg-secondary text-foreground"
                      : "text-muted-foreground hover:text-foreground hover:bg-secondary/60"
                  }`}
                >
                  {label}
                </Link>
              );
            })}
            <div className="mt-2 pt-2 border-t border-border flex items-center justify-between">
              <span className="text-sm text-muted-foreground">{partner.displayName}</span>
              <button
                onClick={signOut}
                className="text-sm text-muted-foreground hover:text-foreground cursor-pointer active:scale-95 transition-transform"
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
