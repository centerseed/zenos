"use client";

import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, partner, loading, error, signOut } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  if (!user) return null;

  if (error === "NO_PARTNER" || (!partner && !loading)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center max-w-md p-8">
          <div className="text-4xl mb-4">🔒</div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            尚未開通權限
          </h2>
          <p className="text-gray-600 mb-6">
            你的帳號尚未被授權使用 ZenOS Dashboard。請聯繫管理員開通權限。
          </p>
          <p className="text-sm text-gray-400 mb-4">{user.email}</p>
          <button
            onClick={() => signOut()}
            className="text-sm text-blue-600 hover:underline cursor-pointer"
          >
            使用其他帳號登入
          </button>
        </div>
      </div>
    );
  }

  if (error === "FETCH_FAILED") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center max-w-md p-8">
          <div className="text-4xl mb-4">⚠️</div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            載入失敗
          </h2>
          <p className="text-gray-600">無法連線到 ZenOS，請稍後再試。</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
