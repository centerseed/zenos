"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { AuthGuard } from "@/components/AuthGuard";
import { AppNav } from "@/components/AppNav";
import { LoadingState } from "@/components/LoadingState";
import { resolveActiveWorkspace } from "@/lib/partner";
import {
  getDeals,
  patchDealStage,
  getCompanies,
  createDeal,
  createCompany,
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

// ─── NewDealModal ─────────────────────────────────────────────────────────────

interface NewDealModalProps {
  isOpen: boolean;
  onClose: () => void;
  companies: Company[];
  onCreated: (deal: Deal, newCompany?: Company) => void;
  user: any;
  userId: string;
}

function NewDealModal({
  isOpen,
  onClose,
  companies,
  onCreated,
  user,
  userId,
}: NewDealModalProps) {
  const [title, setTitle] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [newCompanyName, setNewCompanyName] = useState("");
  const [stage, setStage] = useState<FunnelStage>("潛在客戶");
  const [amount, setAmount] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, boolean>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);

  const isNewCompany = companyId === "NEW_COMPANY";

  if (!isOpen) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    
    // Manual validation
    const newErrors: Record<string, boolean> = {
      title: !title.trim(),
      companyId: !companyId,
      newCompanyName: isNewCompany && !newCompanyName.trim(),
    };
    setErrors(newErrors);

    if (newErrors.title || newErrors.companyId || newErrors.newCompanyName || !user) {
      return;
    }

    setIsSubmitting(true);
    try {
      const token = await user.getIdToken();
      
      let finalCompanyId = companyId;
      let createdCompany: Company | undefined;

      // Create company first if needed
      if (isNewCompany) {
        // MATCH SNAKE_CASE expected by Python backend
        const companyPayload = {
          name: newCompanyName.trim(),
          industry: undefined,
          size_range: undefined,
          region: undefined,
          notes: undefined,
        };
        
        console.log("Creating company with payload:", companyPayload);
        createdCompany = await createCompany(token, companyPayload as any);
        finalCompanyId = createdCompany.id;
      }

      const dealPayload = {
        title: title.trim(),
        company_id: finalCompanyId, 
        funnel_stage: stage,
        amount_twd: amount ? parseInt(amount, 10) : undefined,
        owner_partner_id: userId,
        deliverables: [],
        is_closed_lost: false,
        is_on_hold: false,
        notes: "", // Added notes field
      };

      console.log("Creating deal with payload:", dealPayload);
      const newDeal = await createDeal(token, dealPayload as any);

      onCreated(newDeal, createdCompany);
      
      // Reset all
      setTitle("");
      setCompanyId("");
      setNewCompanyName("");
      setStage("潛在客戶");
      setAmount("");
      setErrors({});
      setSubmitError(null);
      onClose();
    } catch (err) {
      console.error("Failed to create deal/company:", err);
      setSubmitError(err instanceof Error ? err.message : "建立失敗，請檢查網路或聯絡系統管理員");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
      <div className="bg-card border border-border rounded-xl shadow-2xl w-full max-w-md overflow-hidden">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h3 className="font-semibold text-foreground">新增商機</h3>
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="text-muted-foreground hover:text-foreground disabled:opacity-30"
          >
            ✕
          </button>
        </div>
        <form onSubmit={handleSubmit} noValidate className="p-4 space-y-4">
          {submitError && (
            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-400">
              {submitError}
            </div>
          )}
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-foreground">
              商機標題 <span className="text-red-500">*</span>
            </label>
            <input
              autoFocus
              value={title}
              onChange={(e) => {
                setTitle(e.target.value);
                if (errors.title) setErrors(prev => ({ ...prev, title: false }));
              }}
              className={`w-full bg-secondary border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 transition-colors ${
                errors.title ? "border-red-500" : "border-border"
              }`}
              placeholder="例如：AI 顧問專案"
            />
            {errors.title && <p className="text-[10px] text-red-500">請輸入商機標題</p>}
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium text-foreground">
              所屬公司 <span className="text-red-500">*</span>
            </label>
            <select
              value={companyId}
              onChange={(e) => {
                setCompanyId(e.target.value);
                if (errors.companyId) setErrors(prev => ({ ...prev, companyId: false }));
              }}
              className={`w-full bg-secondary border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 transition-colors ${
                errors.companyId ? "border-red-500" : "border-border"
              }`}
            >
              <option value="">請選擇公司...</option>
              <option value="NEW_COMPANY" className="text-primary font-medium text-blue-400">+ 新增新公司...</option>
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            {errors.companyId && <p className="text-[10px] text-red-500">請選擇所屬公司</p>}
          </div>

          {isNewCompany && (
            <div className="space-y-1.5 animate-in fade-in slide-in-from-top-2 duration-200">
              <label className="text-sm font-medium text-foreground">
                新公司名稱 <span className="text-red-500">*</span>
              </label>
              <input
                value={newCompanyName}
                onChange={(e) => {
                  setNewCompanyName(e.target.value);
                  if (errors.newCompanyName) setErrors(prev => ({ ...prev, newCompanyName: false }));
                }}
                className={`w-full bg-secondary border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 transition-colors ${
                  errors.newCompanyName ? "border-red-500" : "border-border"
                }`}
                placeholder="輸入公司全名"
              />
              {errors.newCompanyName && <p className="text-[10px] text-red-500">請輸入新公司名稱</p>}
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-foreground">漏斗階段</label>
              <select
                value={stage}
                onChange={(e) => setStage(e.target.value as FunnelStage)}
                className="w-full bg-secondary border border-border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              >
                {FUNNEL_STAGES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-foreground">金額 (TWD)</label>
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="w-full bg-secondary border border-border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                placeholder="選填"
              />
            </div>
          </div>
          <div className="pt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-foreground hover:bg-secondary rounded transition-colors"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {isSubmitting ? "建立中..." : "建立商機"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── ClientsPage ─────────────────────────────────────────────────────────────

function ClientsPage() {
  const { user, partner } = useAuth();
  const router = useRouter();
  const { isHomeWorkspace } = resolveActiveWorkspace(partner);
  const [deals, setDeals] = useState<Deal[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [showInactive, setShowInactive] = useState(false);
  const [activeDragId, setActiveDragId] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Route guard: shared-workspace users cannot access the CRM page
  useEffect(() => {
    if (partner && !isHomeWorkspace) {
      router.replace("/tasks");
    }
  }, [partner, isHomeWorkspace, router]);

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

  const visibleDeals = showInactive
    ? deals
    : deals.filter((d) => !d.isClosedLost && !d.isOnHold);

  const dealsByStage = Object.fromEntries(
    FUNNEL_STAGES.map((stage) => [
      stage,
      visibleDeals.filter((d) => d.funnelStage === stage),
    ])
  ) as Record<FunnelStage, Deal[]>;

  const activeDealsCount = deals.filter((d) => !d.isClosedLost && !d.isOnHold).length;
  const thisMonth = new Date();
  const newThisMonthCount = deals.filter((d) => {
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

    setDeals((prev) =>
      prev.map((d) => (d.id === dealId ? { ...d, funnelStage: newStage } : d))
    );

    try {
      const token = await user!.getIdToken();
      await patchDealStage(token, dealId, newStage);
    } catch (err) {
      console.error("Failed to update deal stage:", err);
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

  if (!isHomeWorkspace) return null;

  return (
    <div className="min-h-screen">
      <AppNav />
      <main id="main-content" className="max-w-full px-4 sm:px-6 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6 gap-3 flex-wrap">
          <h2 className="text-lg font-semibold text-foreground">客戶</h2>
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => setIsModalOpen(true)}
              className="px-3 py-1.5 text-sm rounded bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              + 新增商機
            </button>
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

        {/* Summary stats */}
        {!loading && (
          <div className="grid grid-cols-3 gap-3 mb-6 max-w-xl">
            <div className="bg-card border border-border rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-foreground">{activeDealsCount}</p>
              <p className="text-xs text-muted-foreground mt-0.5">進行中商機</p>
            </div>
            <div className="bg-card border border-border rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-foreground">{newThisMonthCount}</p>
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
                  lastActivityMap={Object.fromEntries(
                    deals.map((d) => [d.id, d.lastActivityAt ?? undefined])
                  )}
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

        {/* Modal */}
        <NewDealModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          companies={companies}
          onCreated={(newDeal, newCompany) => {
            if (newCompany) {
              setCompanies((prev) => [...prev, newCompany]);
            }
            setDeals((prev) => [newDeal, ...prev]);
          }}
          user={user}
          userId={partner?.id ?? ""}
        />
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
