"use client";

import { useAuth } from "@/lib/auth";
import { getAuthInstance } from "@/lib/firebase";
import { isSignInWithEmailLink, signInWithEmailLink } from "firebase/auth";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function LoginPage() {
  const { user, partner, loading, signInWithGoogle } = useAuth();
  const router = useRouter();
  const [emailLinkLoading, setEmailLinkLoading] = useState(false);
  const [emailLinkError, setEmailLinkError] = useState<string | null>(null);

  // Handle email link sign-in
  useEffect(() => {
    const auth = getAuthInstance();
    if (isSignInWithEmailLink(auth, window.location.href)) {
      setEmailLinkLoading(true);
      let email = window.localStorage.getItem("emailForSignIn");
      if (!email) {
        email = window.prompt("請輸入你的 email 以完成登入");
      }
      if (!email) {
        setEmailLinkLoading(false);
        setEmailLinkError("需要 email 才能完成登入");
        return;
      }
      signInWithEmailLink(auth, email, window.location.href)
        .then(() => {
          window.localStorage.removeItem("emailForSignIn");
          router.replace("/");
        })
        .catch((err) => {
          console.error("Email link sign-in failed:", err);
          setEmailLinkError("登入連結無效或已過期，請重新申請邀請。");
        })
        .finally(() => {
          setEmailLinkLoading(false);
        });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Redirect if already authenticated
  useEffect(() => {
    if (!loading && user && partner) {
      router.replace("/");
    }
  }, [loading, user, partner, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center max-w-sm w-full p-8">
        <h1 className="text-3xl font-bold text-white mb-2">ZenOS</h1>
        <p className="text-muted-foreground mb-8">
          Knowledge Ontology for your AI agents
        </p>

        {emailLinkLoading ? (
          <div className="text-muted-foreground text-sm">正在完成登入...</div>
        ) : emailLinkError ? (
          <div className="space-y-4">
            <div className="text-red-400 text-sm">{emailLinkError}</div>
            <button
              onClick={signInWithGoogle}
              disabled={loading}
              className="w-full bg-card border border-border rounded-lg px-6 py-3 text-sm font-medium text-foreground hover:bg-secondary hover:border-border transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3"
            >
              <GoogleIcon />
              Sign in with Google
            </button>
          </div>
        ) : (
          <button
            onClick={signInWithGoogle}
            disabled={loading}
            className="w-full bg-card border border-border rounded-lg px-6 py-3 text-sm font-medium text-foreground hover:bg-secondary hover:border-border transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3"
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
    <svg className="w-5 h-5" viewBox="0 0 24 24">
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
