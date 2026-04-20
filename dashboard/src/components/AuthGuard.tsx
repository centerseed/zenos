"use client";

import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { activatePartner } from "@/lib/api";
import { useInk } from "@/lib/zen-ink/tokens";
import { InkMark } from "@/components/zen/InkMark";

function ZenScreen({ children }: { children: React.ReactNode }) {
  const t = useInk("light");
  return (
    <div
      style={{
        minHeight: "100vh",
        background: t.c.paper,
        color: t.c.ink,
        fontFamily: t.fontBody,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      {children}
    </div>
  );
}

function ZenSpinner() {
  const t = useInk("light");
  return (
    <div
      aria-hidden
      style={{
        width: 28,
        height: 28,
        borderRadius: "50%",
        border: `2px solid ${t.c.inkHair}`,
        borderTopColor: t.c.vermillion,
        animation: "zen-spin 0.9s linear infinite",
      }}
    />
  );
}

function ZenCard({ children }: { children: React.ReactNode }) {
  const t = useInk("light");
  return (
    <div
      style={{
        maxWidth: 480,
        width: "100%",
        background: t.c.surface,
        border: `1px solid ${t.c.inkHair}`,
        borderRadius: t.radius,
        padding: "40px 36px",
        textAlign: "center",
      }}
    >
      {children}
    </div>
  );
}

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
    const authUser = user;
    if (!authUser || !partner || partner.status !== "invited" || activating) return;
    const invitedUser: NonNullable<typeof authUser> = authUser;

    async function activate() {
      setActivating(true);
      try {
        const token = await invitedUser.getIdToken();
        await activatePartner(token);
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
    const t = useInk("light");
    return (
      <ZenScreen>
        <style>{`@keyframes zen-spin { to { transform: rotate(360deg); } }`}</style>
        <div style={{ textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
          <InkMark size={56} ink={t.c.ink} seal={t.c.seal} sealInk={t.c.sealInk} />
          <div style={{ fontFamily: t.fontHead, fontSize: 22, letterSpacing: "0.04em", color: t.c.ink }}>
            ZenOS
          </div>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 10, color: t.c.inkMuted, fontSize: 14 }}>
            <ZenSpinner />
            <span>正在載入帳號…</span>
          </div>
          <div style={{ fontSize: 11, color: t.c.inkFaint, letterSpacing: "0.05em" }}>
            auth: {user ? "有用戶" : "無用戶"} · partner: {partner ? "已載入" : "未載入"} · error: {error || "無"}
          </div>
        </div>
      </ZenScreen>
    );
  }

  if (error === "FIREBASE_CONFIG_MISSING" || error === "FIREBASE_CONFIG_INVALID") {
    const isMissing = error === "FIREBASE_CONFIG_MISSING";
    const t = useInk("light");
    return (
      <ZenScreen>
        <ZenCard>
          <div style={{ fontFamily: t.fontHead, fontSize: 22, color: t.c.vermillion, marginBottom: 12 }}>部署設定錯誤</div>
          <p style={{ color: t.c.inkSoft, marginBottom: 10, fontSize: 14 }}>
            Firebase 公開設定在 build 階段沒有正確注入，登入模組無法啟動。
          </p>
          <p style={{ fontSize: 12, color: t.c.inkMuted }}>
            錯誤類型：{isMissing ? "缺少 NEXT_PUBLIC_FIREBASE_* 設定" : "NEXT_PUBLIC_FIREBASE_API_KEY 無效"}
          </p>
        </ZenCard>
      </ZenScreen>
    );
  }

  if (!user) return null;

  // Show activating state for invited partners
  if (partner?.status === "invited" || activating) {
    const t = useInk("light");
    return (
      <ZenScreen>
        <style>{`@keyframes zen-spin { to { transform: rotate(360deg); } }`}</style>
        <ZenCard>
          {activationError ? (
            <>
              <div style={{ fontFamily: t.fontHead, fontSize: 22, color: t.c.vermillion, marginBottom: 12 }}>啟用失敗</div>
              <p style={{ color: t.c.inkSoft, marginBottom: 20, fontSize: 14 }}>{activationError}</p>
              <button
                onClick={() => signOut()}
                aria-label="Sign out and use another account"
                style={{
                  fontSize: 13,
                  color: t.c.vermillion,
                  background: "transparent",
                  border: "none",
                  borderBottom: `1px solid ${t.c.vermLine}`,
                  paddingBottom: 2,
                  cursor: "pointer",
                  fontFamily: t.fontBody,
                }}
              >
                使用其他帳號登入
              </button>
            </>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14 }}>
              <InkMark size={48} ink={t.c.ink} seal={t.c.seal} sealInk={t.c.sealInk} />
              <div style={{ display: "inline-flex", alignItems: "center", gap: 10, color: t.c.inkMuted, fontSize: 14 }}>
                <ZenSpinner />
                <span>正在啟用帳號…</span>
              </div>
            </div>
          )}
        </ZenCard>
      </ZenScreen>
    );
  }

  // Suspended partner
  if (partner?.status === "suspended") {
    const t = useInk("light");
    return (
      <ZenScreen>
        <ZenCard>
          <div style={{ fontFamily: t.fontHead, fontSize: 24, color: t.c.ink, marginBottom: 12 }}>帳號已停用</div>
          <p style={{ color: t.c.inkSoft, marginBottom: 18, fontSize: 14 }}>
            你的帳號已被管理員停用。如需恢復存取，請聯繫管理員。
          </p>
          <p style={{ fontSize: 12, color: t.c.inkMuted, marginBottom: 20 }}>{user.email}</p>
          <button
            onClick={() => signOut()}
            aria-label="Sign out and use another account"
            style={{
              fontSize: 13,
              color: t.c.vermillion,
              background: "transparent",
              border: "none",
              borderBottom: `1px solid ${t.c.vermLine}`,
              paddingBottom: 2,
              cursor: "pointer",
              fontFamily: t.fontBody,
            }}
          >
            使用其他帳號登入
          </button>
        </ZenCard>
      </ZenScreen>
    );
  }

  if (error === "NO_PARTNER" || (!partner && !loading)) {
    const t = useInk("light");
    return (
      <ZenScreen>
        <ZenCard>
          <div style={{ fontFamily: t.fontHead, fontSize: 24, color: t.c.ink, marginBottom: 12 }}>尚未開通權限</div>
          <p style={{ color: t.c.inkSoft, marginBottom: 18, fontSize: 14 }}>
            你的帳號尚未被授權使用 ZenOS Dashboard。請聯繫管理員開通權限。
          </p>
          <p style={{ fontSize: 12, color: t.c.inkMuted, marginBottom: 20 }}>{user.email}</p>
          <button
            onClick={() => signOut()}
            aria-label="Sign out and use another account"
            style={{
              fontSize: 13,
              color: t.c.vermillion,
              background: "transparent",
              border: "none",
              borderBottom: `1px solid ${t.c.vermLine}`,
              paddingBottom: 2,
              cursor: "pointer",
              fontFamily: t.fontBody,
            }}
          >
            使用其他帳號登入
          </button>
        </ZenCard>
      </ZenScreen>
    );
  }

  if (error === "FETCH_FAILED") {
    const t = useInk("light");
    return (
      <ZenScreen>
        <ZenCard>
          <div style={{ fontFamily: t.fontHead, fontSize: 22, color: t.c.vermillion, marginBottom: 12 }}>載入失敗</div>
          <p style={{ color: t.c.inkSoft, fontSize: 14 }}>無法連線到 ZenOS，請稍後再試。</p>
        </ZenCard>
      </ZenScreen>
    );
  }

  return <>{children}</>;
}
