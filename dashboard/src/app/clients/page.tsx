"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { AuthGuard } from "@/components/AuthGuard";
import { AppNav } from "@/components/AppNav";
import { LoadingState } from "@/components/LoadingState";
import {
  getDeals,
  patchDealStage,
  getCompanies,
} from "@/lib/crm-api";
import type { Deal, FunnelStage, Company } from "@/lib/crm-api";
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
  useDraggable,
} from "@dnd-kit/core";

// ─── Constants ────────────────────────────────────────────────────────────────

const FUNNEL_STAGES: FunnelStage[] = [
  "潛在客戶",
  "需求訪談",
  "提案報價",
  "合約議價",
  "導入中",
  "結案",
];

const DAYS_STALE = 14;

// ─── Helper ───────────────────────────────────────────────────────────────────

function daysSince(date: Date | undefined): number | null {
  if (!date) return null;
  return Math.floor((Date.now() - date.getTime()) / (1000 * 60 * 60 * 24));
}

// ─── DealCard ─────────────────────────────────────────────────────────────────

interface DealCardProps {
  deal: Deal;
  companyName: string;
  lastActivityDate?: Date;
  isDragging?: boolean;
}

function DealCard({ deal, companyName, lastActivityDate, isDragging }: DealCardProps) {
  const staleDays = daysSince(lastActivityDate);
  const isStale = staleDays !== null && staleDays >= DAYS_STALE;

  return (
    <div
      className={`bg-card border border-border rounded-lg p-3 space-y-1.5 ${
        isDragging ? "opacity-50" : ""
      }`}
    >
      <Link
        href={`/clients/deals/${deal.id}`}
        className="block text-sm font-medium text-foreground hover:text-primary truncate"
        onClick={(e) => e.stopPropagation()}
      >
        {deal.title}
      </Link>
      <p className="text-xs text-muted-foreground truncate">{companyName}</p>
      {deal.amountTwd && (
        <p className="text-xs text-foreground font-medium">
          NT$ {deal.amountTwd.toLocaleString()}
        </p>
      )}
      {isStale && staleDays !== null && (
        <span className="inline-block text-xs bg-orange-500/15 text-orange-400 border border-orange-500/30 rounded px-1.5 py-0.5">
          {staleDays} 天未跟進
        </span>
      )}
    </div>
  );
}

// ─── DraggableDealCard ────────────────────────────────────────────────────────

interface DraggableDealCardProps {
  deal: Deal;
  companyName: string;
  lastActivityDate?: Date;
}

function DraggableDealCard({ deal, companyName, lastActivityDate }: DraggableDealCardProps) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: deal.id,
    data: { deal },
  });

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      className="cursor-grab active:cursor-grabbing"
    >
      <DealCard
        deal={deal}
        companyName={companyName}
        lastActivityDate={lastActivityDate}
        isDragging={isDragging}
      />
    </div>
  );
}

// ─── KanbanColumn ─────────────────────────────────────────────────────────────

interface KanbanColumnProps {
  stage: FunnelStage;
  deals: Deal[];
  companiesMap: Record<string, string>;
  lastActivityMap: Record<string, Date | undefined>;
}

function KanbanColumn({ stage, deals, companiesMap, lastActivityMap }: KanbanColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: stage });

  return (
    <div className="flex flex-col min-w-[200px] w-[200px] shrink-0">
      <div className="flex items-center justify-between mb-2 px-1">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          {stage}
        </span>
        <span className="text-xs bg-secondary text-muted-foreground rounded-full px-2 py-0.5">
          {deals.length}
        </span>
      </div>
      <div
        ref={setNodeRef}
        className={`flex-1 min-h-[120px] rounded-lg p-2 space-y-2 transition-colors ${
          isOver
            ? "bg-secondary/50 border-2 border-primary/40 border-dashed"
            : "bg-secondary/20 border border-border"
        }`}
      >
        {deals.map((deal) => (
          <DraggableDealCard
            key={deal.id}
            deal={deal}
            companyName={companiesMap[deal.companyId] ?? "—"}
            lastActivityDate={lastActivityMap[deal.id]}
          />
        ))}
        {deals.length === 0 && (
          <p className="text-xs text-muted-foreground text-center py-4">
            拖曳商機至此
          </p>
        )}
      </div>
    </div>
  );
}

// ─── ClientsPage ─────────────────────────────────────────────────────────────

function ClientsPage() {
  const { user, partner } = useAuth();
  const [deals, setDeals] = useState<Deal[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [showInactive, setShowInactive] = useState(false);
  const [activeDragId, setActiveDragId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  );

  const loadData = useCallback(
    async (includeInactive: boolean) => {
      if (!user || !partner) return;
      setLoading(true);
      try {
        const token = await user.getIdToken();
        const [fetchedDeals, fetchedCompanies] = await Promise.all([
          getDeals(token, includeInactive),
          getCompanies(token),
        ]);
        setDeals(fetchedDeals);
        setCompanies(fetchedCompanies);
      } catch (err) {
        console.error("Failed to load CRM data:", err);
      }
      setLoading(false);
    },
    [user, partner]
  );

  useEffect(() => {
    loadData(showInactive);
  }, [loadData, showInactive]);

  const companiesMap = Object.fromEntries(
    companies.map((c) => [c.id, c.name])
  );

  // Active deals only (not closed-lost, not on-hold) unless showInactive
  const visibleDeals = showInactive
    ? deals
    : deals.filter((d) => !d.isClosedLost && !d.isOnHold);

  const dealsByStage = Object.fromEntries(
    FUNNEL_STAGES.map((stage) => [
      stage,
      visibleDeals.filter((d) => d.funnelStage === stage),
    ])
  ) as Record<FunnelStage, Deal[]>;

  // Summary stats
  const activeDeals = deals.filter((d) => !d.isClosedLost && !d.isOnHold);
  const thisMonth = new Date();
  const newThisMonth = deals.filter((d) => {
    const created = d.createdAt;
    return (
      created.getFullYear() === thisMonth.getFullYear() &&
      created.getMonth() === thisMonth.getMonth()
    );
  }).length;
  const totalSignedAmount = deals
    .filter((d) => d.funnelStage === "結案" && !d.isClosedLost)
    .reduce((sum, d) => sum + (d.amountTwd ?? 0), 0);

  function handleDragStart(event: DragStartEvent) {
    setActiveDragId(event.active.id as string);
  }

  async function handleDragEnd(event: DragEndEvent) {
    setActiveDragId(null);
    const { active, over } = event;
    if (!over) return;

    const dealId = active.id as string;
    const newStage = over.id as FunnelStage;
    const deal = deals.find((d) => d.id === dealId);
    if (!deal || deal.funnelStage === newStage) return;

    // Optimistic update
    setDeals((prev) =>
      prev.map((d) => (d.id === dealId ? { ...d, funnelStage: newStage } : d))
    );

    try {
      const token = await user!.getIdToken();
      await patchDealStage(token, dealId, newStage);
    } catch (err) {
      console.error("Failed to update deal stage:", err);
      // Rollback on failure
      setDeals((prev) =>
        prev.map((d) =>
          d.id === dealId ? { ...d, funnelStage: deal.funnelStage } : d
        )
      );
    }
  }

  const activeDragDeal = activeDragId
    ? deals.find((d) => d.id === activeDragId)
    : null;

  return (
    <div className="min-h-screen">
      <AppNav />
      <main id="main-content" className="max-w-full px-4 sm:px-6 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6 gap-3 flex-wrap">
          <h2 className="text-lg font-semibold text-foreground">客戶</h2>
          <div className="flex items-center gap-2 flex-wrap">
            <Link
              href="/clients/companies"
              className="px-3 py-1.5 text-sm rounded bg-secondary text-foreground hover:bg-secondary/80 transition-colors"
            >
              公司列表
            </Link>
            <label className="flex items-center gap-1.5 text-sm text-muted-foreground cursor-pointer">
              <input
                type="checkbox"
                checked={showInactive}
                onChange={(e) => setShowInactive(e.target.checked)}
                className="rounded"
              />
              顯示流失/暫緩
            </label>
          </div>
        </div>

        {/* Summary stats (P1) */}
        {!loading && (
          <div className="grid grid-cols-3 gap-3 mb-6 max-w-xl">
            <div className="bg-card border border-border rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-foreground">{activeDeals.length}</p>
              <p className="text-xs text-muted-foreground mt-0.5">進行中商機</p>
            </div>
            <div className="bg-card border border-border rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-foreground">{newThisMonth}</p>
              <p className="text-xs text-muted-foreground mt-0.5">本月新增</p>
            </div>
            <div className="bg-card border border-border rounded-lg p-3 text-center">
              <p className="text-xl font-bold text-foreground">
                {totalSignedAmount > 0
                  ? `${(totalSignedAmount / 10000).toFixed(0)}萬`
                  : "—"}
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">成交案值</p>
            </div>
          </div>
        )}

        {/* Kanban */}
        {loading ? (
          <LoadingState label="載入商機看板..." />
        ) : (
          <DndContext
            sensors={sensors}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <div className="flex gap-3 overflow-x-auto pb-4">
              {FUNNEL_STAGES.map((stage) => (
                <KanbanColumn
                  key={stage}
                  stage={stage}
                  deals={dealsByStage[stage]}
                  companiesMap={companiesMap}
                  lastActivityMap={{}}
                />
              ))}
            </div>
            <DragOverlay>
              {activeDragDeal && (
                <div className="rotate-2 shadow-xl opacity-90">
                  <DealCard
                    deal={activeDragDeal}
                    companyName={companiesMap[activeDragDeal.companyId] ?? "—"}
                  />
                </div>
              )}
            </DragOverlay>
          </DndContext>
        )}
      </main>
    </div>
  );
}

export default function Page() {
  return (
    <AuthGuard>
      <ClientsPage />
    </AuthGuard>
  );
}
