import type { ReactNode } from "react";
import { AppNav } from "@/components/AppNav";
import { AuthGuard } from "@/components/AuthGuard";

export default function ProtectedLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard>
      <div className="min-h-screen bg-background text-foreground">
        <AppNav />
        {children}
      </div>
    </AuthGuard>
  );
}
