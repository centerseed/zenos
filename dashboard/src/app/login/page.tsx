"use client";

import { useEffect, useRef, useState } from "react";
import { isSignInWithEmailLink, signInWithEmailLink } from "firebase/auth";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { getAuthInstance } from "@/lib/firebase";

const WORKSPACE_HOME = "/tasks";

export default function LoginPage() {
  const { user, partner, loading, error, signInWithGoogle } = useAuth();
  const router = useRouter();
  const emailLinkHandledRef = useRef(false);
  const [emailLinkLoading, setEmailLinkLoading] = useState(false);
  const [emailLinkError, setEmailLinkError] = useState<string | null>(null);

  useEffect(() => {
    if (error === "FIREBASE_CONFIG_MISSING" || error === "FIREBASE_CONFIG_INVALID") {
      return;
    }
    if (!loading && user && partner) {
      router.replace(WORKSPACE_HOME);
      return;
    }

    if (emailLinkHandledRef.current || emailLinkLoading) return;

    let auth;
    try {
      auth = getAuthInstance();
    } catch (err) {
      console.error("Failed to bootstrap Firebase auth on login page:", err);
      setEmailLinkError("目前登入設定異常，請先修復 dashboard 部署設定。");
      return;
    }
    if (!isSignInWithEmailLink(auth, window.location.href)) return;

    emailLinkHandledRef.current = true;
    setEmailLinkLoading(true);

    const completeEmailLink = async () => {
      let email = window.localStorage.getItem("emailForSignIn");
      if (!email) {
        email = window.prompt("請輸入你的 email 以完成登入");
      }

      if (!email) {
        setEmailLinkLoading(false);
        setEmailLinkError("需要 email 才能完成登入");
        return;
      }

      try {
        await signInWithEmailLink(auth, email, window.location.href);
        window.localStorage.removeItem("emailForSignIn");
        router.replace(WORKSPACE_HOME);
      } catch (err) {
        console.error("Email link sign-in failed:", err);
        setEmailLinkError("登入連結無效或已過期，請重新申請邀請。");
        emailLinkHandledRef.current = false;
      } finally {
        setEmailLinkLoading(false);
      }
    };

    void completeEmailLink();
  }, [emailLinkLoading, error, loading, partner, router, signInWithGoogle, user]);

  if (error === "FIREBASE_CONFIG_MISSING" || error === "FIREBASE_CONFIG_INVALID") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-base">
        <div className="text-center max-w-md w-full p-8">
          <h1 className="text-3xl font-bold text-white mb-2">ZenOS</h1>
          <p className="text-dim mb-6">Dashboard deployment is misconfigured.</p>
          <div className="rounded-zen border bd-hair bg-panel p-5 text-left">
            <div className="text-sm font-medium text-foreground mb-2">Firebase public config 無法啟動</div>
            <div className="text-sm text-dim">
              {error === "FIREBASE_CONFIG_MISSING"
                ? "build 階段缺少 NEXT_PUBLIC_FIREBASE_* 環境變數。"
                : "build 階段注入的 NEXT_PUBLIC_FIREBASE_API_KEY 無效。"}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-base">
      <div className="text-center max-w-sm w-full p-8">
        <h1 className="text-3xl font-bold text-white mb-2">ZenOS</h1>
        <p className="text-dim mb-8">
          Shared-L1 workspace access for prosumer teams
        </p>

        {emailLinkLoading ? (
          <div className="text-dim text-sm">正在完成登入...</div>
        ) : emailLinkError ? (
          <div className="space-y-4">
            <div className="text-red-400 text-sm">{emailLinkError}</div>
            <button
              onClick={signInWithGoogle}
              disabled={loading}
              className="w-full flex items-center justify-center gap-3 rounded-lg border bd-hair bg-panel px-6 py-3 text-sm font-medium text-foreground transition-colors hover:bd-hair hover:bg-soft disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
            >
              <GoogleIcon />
              Sign in with Google
            </button>
          </div>
        ) : (
          <button
            onClick={signInWithGoogle}
            disabled={loading}
            className="w-full flex items-center justify-center gap-3 rounded-lg border bd-hair bg-panel px-6 py-3 text-sm font-medium text-foreground transition-colors hover:bd-hair hover:bg-soft disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
          >
            <GoogleIcon />
            Sign in with Google
          </button>
        )}
      </div>
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      />
    </svg>
  );
}
