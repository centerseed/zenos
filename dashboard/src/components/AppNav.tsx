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
    <header className="sticky top-0 z-50 border-b border-border/80 bg-background/72 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-3 sm:gap-6">
          <Link
            href="/"
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
