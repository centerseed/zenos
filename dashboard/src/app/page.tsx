"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function Page() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/knowledge-map");
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-[#71717A]">Loading...</div>
    </div>
  );
}
