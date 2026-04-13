"use client";

import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LoadingState } from "@/components/LoadingState";

const API_URL = process.env.NEXT_PUBLIC_MCP_API_URL || "https://zenos-mcp-165893875709.asia-east1.run.app";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, partner, loading, error, signOut, refetchPartner } = useAuth();
  const router = useRouter();
  const [activating, setActivating] = useState(false);
  const [activationError, setActivationError] = useState<string | null>(null);

  useEffect(() => {
    if (error === "FIREBASE_CONFIG_MISSING" || error === "FIREBASE_CONFIG_INVALID") {
      return;
    }
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [error, loading, user, router]);

  // Auto-activate invited partners
  useEffect(() => {
    if (!user || !partner || partner.status !== "invited" || activating) return;

    async function activate() {
      setActivating(true);
      try {
        const token = await user!.getIdToken();
        const res = await fetch(`${API_URL}/api/partners/activate`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) {
          const body = await res.text();
          throw new Error(`Activation failed: ${res.status} ${body}`);
        }
        await refetchPartner();
      } catch (err) {
        console.error("Failed to activate partner:", err);
        setActivationError("帳號啟用失敗，請稍後再試或聯繫管理員。");
      } finally {
        setActivating(false);
      }
    }

    activate();
  }, [user, partner, activating, refetchPartner]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <LoadingState label="Loading account..." />
          <div className="text-muted-foreground/60 text-xs mt-2">
            auth: {user ? "有用戶" : "無用戶"} | partner: {partner ? "已載入" : "未載入"} | error: {error || "無"}
          </div>
        </div>
      </div>
    );
  }

  if (error === "FIREBASE_CONFIG_MISSING" || error === "FIREBASE_CONFIG_INVALID") {
    const isMissing = error === "FIREBASE_CONFIG_MISSING";
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="max-w-lg rounded-2xl border border-border bg-card p-8 text-center shadow-sm">
          <div className="text-4xl mb-4">&#x26A0;&#xFE0F;</div>
          <h2 className="text-xl font-semibold text-foreground mb-2">Dashboard 部署設定錯誤</h2>
          <p className="text-muted-foreground mb-3">
            Firebase 公開設定在 build 階段沒有正確注入，所以登入模組無法啟動。
          </p>
          <p className="text-sm text-muted-foreground/80">
            錯誤類型：{isMissing ? "缺少 NEXT_PUBLIC_FIREBASE_* 設定" : "NEXT_PUBLIC_FIREBASE_API_KEY 無效"}
          </p>
        </div>
      </div>
    );
  }

  if (!user) return null;

  // Show activating state for invited partners
  if (partner?.status === "invited" || activating) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center max-w-md p-8">
          {activationError ? (
            <>
              <div className="text-4xl mb-4">&#x26A0;&#xFE0F;</div>
              <h2 className="text-xl font-semibold text-foreground mb-2">啟用失敗</h2>
              <p className="text-muted-foreground mb-4">{activationError}</p>
              <button
                onClick={() => signOut()}
                aria-label="Sign out and use another account"
                className="text-sm text-blue-400 hover:underline cursor-pointer"
              >
                使用其他帳號登入
              </button>
            </>
          ) : (
            <>
              <LoadingState label="正在啟用帳號..." />
            </>
          )}
        </div>
      </div>
    );
  }

  // Suspended partner
  if (partner?.status === "suspended") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center max-w-md p-8">
          <div className="text-4xl mb-4">&#x1F6AB;</div>
          <h2 className="text-xl font-semibold text-foreground mb-2">
            帳號已停用
          </h2>
          <p className="text-muted-foreground mb-6">
            你的帳號已被管理員停用。如需恢復存取，請聯繫管理員。
          </p>
          <p className="text-sm text-muted-foreground mb-4">{user.email}</p>
          <button
            onClick={() => signOut()}
            aria-label="Sign out and use another account"
            className="text-sm text-blue-400 hover:underline cursor-pointer"
          >
            使用其他帳號登入
          </button>
        </div>
      </div>
    );
  }

  if (error === "NO_PARTNER" || (!partner && !loading)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center max-w-md p-8">
          <div className="text-4xl mb-4">&#x1F512;</div>
          <h2 className="text-xl font-semibold text-foreground mb-2">
            尚未開通權限
          </h2>
          <p className="text-muted-foreground mb-6">
            你的帳號尚未被授權使用 ZenOS Dashboard。請聯繫管理員開通權限。
          </p>
          <p className="text-sm text-muted-foreground mb-4">{user.email}</p>
          <button
            onClick={() => signOut()}
            aria-label="Sign out and use another account"
            className="text-sm text-blue-400 hover:underline cursor-pointer"
          >
            使用其他帳號登入
          </button>
        </div>
      </div>
    );
  }

  if (error === "FETCH_FAILED") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center max-w-md p-8">
          <div className="text-4xl mb-4">&#x26A0;&#xFE0F;</div>
          <h2 className="text-xl font-semibold text-foreground mb-2">
            載入失敗
          </h2>
          <p className="text-muted-foreground">無法連線到 ZenOS，請稍後再試。</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
