"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { AuthGuard } from "@/components/AuthGuard";
import { AppNav } from "@/components/AppNav";
import { LoadingState } from "@/components/LoadingState";
import {
  getDeal,
  patchDealStage,
  getDealActivities,
  createActivity,
} from "@/lib/crm-api";
import type { Deal, Activity, FunnelStage, ActivityType } from "@/lib/crm-api";

// ─── Constants ────────────────────────────────────────────────────────────────

const FUNNEL_STAGES: FunnelStage[] = [
  "潛在客戶",
  "需求訪談",
  "提案報價",
  "合約議價",
  "導入中",
  "結案",
];

const ACTIVITY_TYPES: ActivityType[] = ["電話", "Email", "會議", "Demo", "備忘"];

// ─── ActivityItem ─────────────────────────────────────────────────────────────

interface ActivityItemProps {
  activity: Activity;
}

function ActivityItem({ activity }: ActivityItemProps) {
  const date = activity.activityAt;
  const dateStr = date instanceof Date
    ? date.toLocaleDateString("zh-TW", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })
    : String(date);

  return (
    <div className={`flex gap-3 ${activity.isSystem ? "opacity-60" : ""}`}>
      <div className="flex flex-col items-center">
        <div
          className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${
            activity.isSystem ? "bg-muted-foreground" : "bg-primary"
          }`}
        />
        <div className="w-px flex-1 bg-border mt-1" />
      </div>
      <div className="pb-4 min-w-0">
        <div className="flex items-center gap-2 flex-wrap mb-0.5">
          <span
            className={`text-xs rounded px-1.5 py-0.5 ${
              activity.isSystem
                ? "bg-secondary text-muted-foreground"
                : "bg-primary/15 text-primary"
            }`}
          >
            {activity.activityType}
          </span>
          <span className="text-xs text-muted-foreground">{dateStr}</span>
        </div>
        <p className="text-sm text-foreground">{activity.summary}</p>
      </div>
    </div>
  );
}

// ─── New Activity Form ────────────────────────────────────────────────────────

interface NewActivityFormProps {
  dealId: string;
  token: string;
  recordedBy: string;
  onCreated: (activity: Activity) => void;
}

function NewActivityForm({ dealId, token, recordedBy, onCreated }: NewActivityFormProps) {
  const [activityType, setActivityType] = useState<ActivityType>("會議");
  const [summary, setSummary] = useState("");
  const [activityAt, setActivityAt] = useState(
    new Date().toISOString().slice(0, 16)
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!summary.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const activity = await createActivity(token, dealId, {
        activityType,
        activityAt: new Date(activityAt),
        summary: summary.trim(),
        recordedBy,
      });
      onCreated(activity);
      setSummary("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "建立失敗");
    }
    setSaving(false);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-secondary/20 border border-border rounded-xl p-4 space-y-3"
    >
      <h4 className="text-sm font-medium text-foreground">新增活動</h4>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-muted-foreground mb-1">類型</label>
          <select
            value={activityType}
            onChange={(e) => setActivityType(e.target.value as ActivityType)}
            className="w-full bg-background border border-border rounded-lg px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          >
            {ACTIVITY_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">日期時間</label>
          <input
            type="datetime-local"
            value={activityAt}
            onChange={(e) => setActivityAt(e.target.value)}
            className="w-full bg-background border border-border rounded-lg px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
      </div>
      <div>
        <label className="block text-xs text-muted-foreground mb-1">
          摘要 <span className="text-red-400">*</span>
        </label>
        <textarea
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          placeholder="本次互動的重點..."
          rows={3}
          required
          className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary resize-none"
        />
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
      <div className="flex justify-end">
        <button
          type="submit"
          disabled={saving || !summary.trim()}
          className="px-4 py-1.5 text-sm rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
        >
          {saving ? "建立中..." : "新增活動"}
        </button>
      </div>
    </form>
  );
}

// ─── DealDetailPage ───────────────────────────────────────────────────────────

function DealDetailPage() {
  const { user, partner } = useAuth();
  const params = useParams();
  const [dealId, setDealId] = useState<string>("");

  useEffect(() => {
    const rawParam = params.id;
    const paramId = Array.isArray(rawParam) ? rawParam[0] : rawParam;
    if (paramId && paramId !== "_") {
      setDealId(paramId);
      return;
    }

    if (typeof window !== "undefined") {
      const segments = window.location.pathname.split("/").filter(Boolean);
      const fallbackId = segments[segments.length - 1];
      if (fallbackId && fallbackId !== "_") {
        setDealId(fallbackId);
      }
    }
  }, [params]);

  const [deal, setDeal] = useState<Deal | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState("");
  const [stageUpdating, setStageUpdating] = useState(false);

  useEffect(() => {
    if (!user || !partner || !dealId) return;

    async function load() {
      const t = await user!.getIdToken();
      setToken(t);
      try {
        const [fetchedDeal, fetchedActivities] = await Promise.all([
          getDeal(t, dealId),
          getDealActivities(t, dealId),
        ]);
        setDeal(fetchedDeal);
        // Sort: newest first
        setActivities(
          [...fetchedActivities].sort(
            (a, b) => b.activityAt.getTime() - a.activityAt.getTime()
          )
        );
      } catch (err) {
        console.error("Failed to load deal:", err);
      }
      setLoading(false);
    }

    load();
  }, [user, partner, dealId]);

  async function handleStageChange(newStage: FunnelStage) {
    if (!deal || deal.funnelStage === newStage) return;
    setStageUpdating(true);
    try {
      const updated = await patchDealStage(token, dealId, newStage);
      setDeal(updated);
    } catch (err) {
      console.error("Failed to update stage:", err);
    }
    setStageUpdating(false);
  }

  function handleActivityCreated(activity: Activity) {
    setActivities((prev) =>
      [activity, ...prev].sort(
        (a, b) => b.activityAt.getTime() - a.activityAt.getTime()
      )
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen">
        <AppNav />
        <div className="flex-1 flex items-center justify-center py-20">
          <LoadingState label="載入商機資料..." />
        </div>
      </div>
    );
  }

  if (!deal) {
    return (
      <div className="min-h-screen">
        <AppNav />
        <main className="max-w-3xl mx-auto px-4 py-6">
          <p className="text-muted-foreground">找不到該商機</p>
        </main>
      </div>
    );
  }

  const formatDate = (date: Date | undefined) =>
    date instanceof Date
      ? date.toLocaleDateString("zh-TW", { year: "numeric", month: "2-digit", day: "2-digit" })
      : "—";

  return (
    <div className="min-h-screen">
      <AppNav />
      <main id="main-content" className="max-w-3xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Link href="/clients" className="hover:text-foreground transition-colors">
            客戶
          </Link>
          <span>/</span>
          <span className="text-foreground">{deal.title}</span>
        </div>

        {/* Deal header + stage selector */}
        <div className="bg-card border border-border rounded-xl p-5">
          <div className="flex items-start justify-between gap-3 mb-4">
            <h2 className="text-xl font-semibold text-foreground">{deal.title}</h2>
            <div className="flex gap-1.5 shrink-0 flex-wrap justify-end">
              {deal.isClosedLost && (
                <span className="text-xs bg-red-500/15 text-red-400 border border-red-500/30 rounded px-2 py-0.5">
                  流失
                </span>
              )}
              {deal.isOnHold && (
                <span className="text-xs bg-yellow-500/15 text-yellow-400 border border-yellow-500/30 rounded px-2 py-0.5">
                  暫緩
                </span>
              )}
            </div>
          </div>

          {/* Funnel stage selector */}
          <div className="mb-4">
            <label className="block text-xs text-muted-foreground mb-1.5">漏斗階段</label>
            <div className="flex gap-1.5 flex-wrap">
              {FUNNEL_STAGES.map((stage) => (
                <button
                  key={stage}
                  onClick={() => handleStageChange(stage)}
                  disabled={stageUpdating}
                  className={`px-3 py-1 text-xs rounded-full transition-colors ${
                    deal.funnelStage === stage
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary text-muted-foreground hover:bg-secondary/80 hover:text-foreground"
                  } disabled:opacity-50`}
                >
                  {stage}
                </button>
              ))}
            </div>
          </div>

          {/* Deal fields */}
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <div>
              <dt className="text-xs text-muted-foreground">案值</dt>
              <dd className="text-foreground">
                {deal.amountTwd ? `NT$ ${deal.amountTwd.toLocaleString()}` : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">案子類型</dt>
              <dd className="text-foreground">{deal.dealType ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">來源</dt>
              <dd className="text-foreground">{deal.sourceType ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">介紹人</dt>
              <dd className="text-foreground">{deal.referrer ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">預計成交日</dt>
              <dd className="text-foreground">{formatDate(deal.expectedCloseDate)}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">合約簽署日</dt>
              <dd className="text-foreground">{formatDate(deal.signedDate)}</dd>
            </div>
          </dl>

          {deal.scopeDescription && (
            <div className="mt-3 pt-3 border-t border-border">
              <dt className="text-xs text-muted-foreground mb-1">工作範圍</dt>
              <dd className="text-sm text-foreground">{deal.scopeDescription}</dd>
            </div>
          )}

          {deal.deliverables && deal.deliverables.length > 0 && (
            <div className="mt-3 pt-3 border-t border-border">
              <p className="text-xs text-muted-foreground mb-1">交付物</p>
              <ul className="list-disc list-inside space-y-0.5">
                {deal.deliverables.map((item, i) => (
                  <li key={i} className="text-sm text-foreground">{item}</li>
                ))}
              </ul>
            </div>
          )}

          {deal.notes && (
            <div className="mt-3 pt-3 border-t border-border">
              <p className="text-xs text-muted-foreground mb-1">備忘</p>
              <p className="text-sm text-foreground">{deal.notes}</p>
            </div>
          )}
        </div>

        {/* New activity form */}
        {partner && (
          <NewActivityForm
            dealId={dealId}
            token={token}
            recordedBy={partner.id}
            onCreated={handleActivityCreated}
          />
        )}

        {/* Activity timeline */}
        <section>
          <h3 className="text-sm font-semibold text-foreground mb-4">
            活動紀錄 ({activities.length})
          </h3>
          {activities.length === 0 ? (
            <p className="text-sm text-muted-foreground">尚無活動紀錄</p>
          ) : (
            <div>
              {activities.map((activity) => (
                <ActivityItem key={activity.id} activity={activity} />
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default function DealDetailClient() {
  return (
    <AuthGuard>
      <DealDetailPage />
    </AuthGuard>
  );
}
