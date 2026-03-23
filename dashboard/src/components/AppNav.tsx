"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useMemo } from "react";

const BASE_NAV_ITEMS = [
  { href: "/knowledge-map", label: "Knowledge Map" },
  { href: "/projects", label: "Projects" },
  { href: "/tasks", label: "Tasks" },
];

const ADMIN_NAV_ITEMS = [{ href: "/team", label: "Team" }];

const TAIL_NAV_ITEMS = [{ href: "/setup", label: "Setup" }];

export function AppNav() {
  const pathname = usePathname();
  const { partner, signOut } = useAuth();

  const navItems = useMemo(() => {
    const items = [...BASE_NAV_ITEMS];
    if (partner?.isAdmin) {
      items.push(...ADMIN_NAV_ITEMS);
    }
    items.push(...TAIL_NAV_ITEMS);
    return items;
  }, [partner?.isAdmin]);

  if (!partner) return null;

  return (
    <header className="border-b border-[#1F1F23] bg-[#0A0A0B]/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 h-12 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <Link href="/" className="text-lg font-bold text-white">
            ZenOS
          </Link>
          <nav className="flex items-center gap-1">
            {navItems.map(({ href, label }) => {
              const isActive = pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={`px-3 py-1.5 rounded text-sm transition-colors ${
                    isActive
                      ? "bg-[#1F1F23] text-white"
                      : "text-[#71717A] hover:text-white hover:bg-[#1F1F23]/50"
                  }`}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-[#71717A]">{partner.displayName}</span>
          <button
            onClick={signOut}
            className="text-sm text-[#71717A] hover:text-white cursor-pointer"
          >
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}
