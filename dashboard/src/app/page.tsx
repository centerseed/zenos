"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { LoadingState } from "@/components/LoadingState";

export default function Page() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/knowledge-map");
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <LoadingState label="Redirecting..." />
    </div>
  );
}
