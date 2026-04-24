"use client";

import type { Entity, Blindspot } from "@/types";
import { isL1Entity } from "@/lib/entity-level";

interface HealthBarProps {
  entities: Entity[];
  blindspots: Blindspot[];
}

export function HealthBar({ entities, blindspots }: HealthBarProps) {
  const products = entities.filter(isL1Entity);
  const activeProducts = entities.filter((e) => isL1Entity(e) && e.status === "active");
  const openBlindspots = blindspots.filter((b) => b.status === "open");
  const redBlindspots = openBlindspots.filter((b) => b.severity === "red");

  // Overall status determination
  let statusText: string;
  let statusColor: string;
  let statusBg: string;
  if (redBlindspots.length > 0) {
    statusText = `${redBlindspots.length} 個需要注意的問題`;
    statusColor = "text-red-400";
    statusBg = "bg-red-900/20 border-red-500/30";
  } else if (openBlindspots.length > 0) {
    statusText = "有小問題，但整體正常";
    statusColor = "text-yellow-400";
    statusBg = "bg-yellow-900/20 border-yellow-500/30";
  } else {
    statusText = "一切正常";
    statusColor = "text-green-400";
    statusBg = "bg-green-900/20 border-green-500/30";
  }

  return (
    <div className={`rounded-lg border p-4 flex items-center justify-between ${statusBg}`}>
      <div className="flex items-center gap-6">
        {/* Overall status */}
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full ${redBlindspots.length > 0 ? "bg-red-500 animate-pulse" : openBlindspots.length > 0 ? "bg-yellow-500" : "bg-green-500"}`} />
          <span className={`text-sm font-medium ${statusColor}`}>{statusText}</span>
        </div>

        {/* Separator */}
        <div className="w-px h-5 bg-border" />

        {/* Quick stats in plain language */}
        <div className="flex items-center gap-4 text-xs text-dim">
          <span>{activeProducts.length} 個工作台進行中</span>
          <span>·</span>
          <span>{entities.length} 個知識節點</span>
          {openBlindspots.length > 0 && (
            <>
              <span>·</span>
              <span className={redBlindspots.length > 0 ? "text-red-400" : "text-yellow-400"}>
                {openBlindspots.length} 個待處理盲點
              </span>
            </>
          )}
        </div>
      </div>

      {/* Last updated */}
      <div className="text-xs text-dim">
        {entities.length > 0 && (
          <span>
            最後更新 {formatRelativeTime(
              new Date(Math.max(...entities.map((e) => e.updatedAt.getTime())))
            )}
          </span>
        )}
      </div>
    </div>
  );
}

function formatRelativeTime(date: Date): string {
  const now = Date.now();
  const diffMs = now - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffMin < 1) return "剛剛";
  if (diffMin < 60) return `${diffMin} 分鐘前`;
  if (diffHr < 24) return `${diffHr} 小時前`;
  if (diffDay < 30) return `${diffDay} 天前`;
  return date.toLocaleDateString("zh-TW");
}
