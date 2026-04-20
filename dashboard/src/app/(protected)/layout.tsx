import type { ReactNode } from "react";
import { AuthGuard } from "@/components/AuthGuard";
import { ZenShell } from "@/components/zen/ZenShell";

export default function ProtectedLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard>
      {/* Override globals.css dark background; ZenShell sets its own paper color */}
      <div style={{ background: "#F4EFE4", minHeight: "100vh" }}>
        <ZenShell>{children}</ZenShell>
      </div>
    </AuthGuard>
  );
}
