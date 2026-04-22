"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { LoadingState } from "@/components/LoadingState";
import {
  createDeal,
  createCompany,
  fetchInsights,
  fetchStaleThresholds,
  updateStaleThresholds,
} from "@/lib/crm-api";
import type { Deal, FunnelStage, Company, CrmInsights, StaleThresholds } from "@/lib/crm-api";
import {
  DndContext,
  DragOverlay,
  useDroppable,
  useDraggable,
} from "@dnd-kit/core";
import { FUNNEL_STAGES, useClientsWorkspace } from "@/features/crm/useClientsWorkspace";

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
      className={`bg-panel border bd-hair rounded-lg p-3 space-y-1.5 ${
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
      <p className="text-xs text-dim truncate">{companyName}</p>
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
        <span className="text-xs font-semibold text-dim uppercase tracking-wide">
          {stage}
        </span>
        <span className="text-xs bg-soft text-dim rounded-full px-2 py-0.5">
          {deals.length}
        </span>
      </div>
      <div
        ref={setNodeRef}
        className={`flex-1 min-h-[120px] rounded-lg p-2 space-y-2 transition-colors ${
          isOver
            ? "bg-soft border-2 border-primary/40 border-dashed"
            : "bg-soft border bd-hair"
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
          <p className="text-xs text-dim text-center py-4">
            拖曳商機至此
          </p>
        )}
      </div>
    </div>
  );
}

// ─── StaleThresholdsModal ─────────────────────────────────────────────────────

const THRESHOLD_STAGES = ["潛在客戶", "需求訪談", "提案報價", "合約議價", "導入中"] as const;

interface StaleThresholdsModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: any;
  onSaved: () => void;
}

function StaleThresholdsModal({ isOpen, onClose, user, onSaved }: StaleThresholdsModalProps) {
  const [thresholds, setThresholds] = useState<StaleThresholds>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !user) return;
    setLoading(true);
    setError(null);
    user.getIdToken().then((token: string) =>
      fetchStaleThresholds(token)
        .then(setThresholds)
        .catch((err: unknown) =>
          setError(err instanceof Error ? err.message : "無法載入設定")
        )
        .finally(() => setLoading(false))
    );
  }, [isOpen, user]);

  async function handleSave() {
    if (!user) return;
    setSaving(true);
    setError(null);
    try {
      const token = await user.getIdToken();
      await updateStaleThresholds(token, thresholds);
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "儲存失敗");
    } finally {
      setSaving(false);
    }
  }

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-base backdrop-blur-sm p-4">
      <div className="bg-panel border bd-hair rounded-zen shadow-2xl w-full max-w-sm overflow-hidden">
        <div className="p-4 border-b bd-hair flex items-center justify-between">
          <h3 className="font-semibold text-foreground">停滯提醒天數設定</h3>
          <button
            onClick={onClose}
            disabled={saving}
            className="text-dim hover:text-foreground disabled:opacity-30"
          >
            ✕
          </button>
        </div>
        <div className="p-4 space-y-3">
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-400">
              {error}
            </div>
          )}
          {loading ? (
            <div className="py-6 text-center text-sm text-dim">載入中...</div>
          ) : (
            THRESHOLD_STAGES.map((stage) => (
              <div key={stage} className="flex items-center justify-between gap-4">
                <label className="text-sm text-foreground w-24 shrink-0">{stage}</label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min={1}
                    value={thresholds[stage] ?? ""}
                    onChange={(e) =>
                      setThresholds((prev) => ({
                        ...prev,
                        [stage]: parseInt(e.target.value, 10) || 0,
                      }))
                    }
                    className="w-20 bg-soft border bd-hair rounded px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-2 focus:ring-primary/50"
                  />
                  <span className="text-sm text-dim">天</span>
                </div>
              </div>
            ))
          )}
        </div>
        <div className="p-4 border-t bd-hair flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 text-sm text-foreground hover:bg-soft rounded transition-colors disabled:opacity-50"
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || loading}
            className="px-4 py-2 text-sm bg-accent-soft text-primary-foreground rounded hover:bg-accent-soft disabled:opacity-50 transition-colors"
          >
            {saving ? "儲存中..." : "儲存"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── DealHealthInsights ───────────────────────────────────────────────────────

interface DealHealthInsightsProps {
  user: any;
  refreshKey: number;
}

function DealHealthInsights({ user, refreshKey }: DealHealthInsightsProps) {
  const [data, setData] = useState<CrmInsights | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    setError(null);
    user.getIdToken().then((token: string) =>
      fetchInsights(token)
        .then(setData)
        .catch((err: unknown) =>
          setError(err instanceof Error ? err.message : "無法載入洞察")
        )
        .finally(() => setLoading(false))
    );
  }, [user, refreshKey]);

  if (loading) {
    return (
      <div className="mb-6 space-y-2">
        <div className="h-4 w-32 bg-soft rounded animate-pulse" />
        <div className="h-16 bg-soft rounded-lg animate-pulse" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mb-6 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-400">
        AI 洞察載入失敗：{error}
      </div>
    );
  }

  if (!data) return null;

  const { insights, pipeline_summary } = data;

  return (
    <div className="mb-6">
      <p className="text-xs font-semibold text-dim uppercase tracking-wide mb-2">
        Deal Health AI 洞察
      </p>
      {insights.length === 0 ? (
        <div className="bg-panel border bd-hair rounded-lg p-3 border-l-4 border-l-green-400 flex items-center gap-3">
          <span className="text-base">✅</span>
          <div>
            <p className="text-sm font-medium text-foreground">目前一切正常</p>
            <p className="text-xs text-dim mt-0.5">
              進行中 {pipeline_summary.active_deals} 案
              {pipeline_summary.estimated_monthly_close_twd > 0 &&
                ` · 本月預計 $${pipeline_summary.estimated_monthly_close_twd.toLocaleString()}`}
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {insights.map((insight) => (
            <a
              key={insight.deal_id}
              href={`/clients/deals/${insight.deal_id}`}
              className="block bg-panel border bd-hair rounded-lg p-3 border-l-4 border-l-orange-400 hover:bg-soft transition-colors"
            >
              <div className="flex items-start gap-2">
                <span className="text-base mt-0.5">⚠️</span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-foreground truncate">
                    {insight.deal_title}
                    {insight.company_name && (
                      <span className="font-normal text-dim ml-1">
                        · {insight.company_name}
                      </span>
                    )}
                  </p>
                  <p className="text-xs text-orange-400 mt-0.5">
                    停滯 {insight.days_stale} 天（{insight.stage}，門檻 {insight.threshold_days} 天）
                  </p>
                  <p className="text-xs text-dim mt-0.5">{insight.suggestion}</p>
                </div>
              </div>
            </a>
          ))}
        </div>
      )}
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

export function NewDealModal({
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-base backdrop-blur-sm p-4">
      <div className="bg-panel border bd-hair rounded-zen shadow-2xl w-full max-w-md overflow-hidden">
        <div className="p-4 border-b bd-hair flex items-center justify-between">
          <h3 className="font-semibold text-foreground">新增商機</h3>
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="text-dim hover:text-foreground disabled:opacity-30"
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
              className={`w-full bg-soft border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 transition-colors ${
                errors.title ? "border-red-500" : "bd-hair"
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
              className={`w-full bg-soft border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 transition-colors ${
                errors.companyId ? "border-red-500" : "bd-hair"
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
                className={`w-full bg-soft border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 transition-colors ${
                  errors.newCompanyName ? "border-red-500" : "bd-hair"
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
                className="w-full bg-soft border bd-hair rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
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
                className="w-full bg-soft border bd-hair rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                placeholder="選填"
              />
            </div>
          </div>
          <div className="pt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-foreground hover:bg-soft rounded transition-colors"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 text-sm bg-accent-soft text-primary-foreground rounded hover:bg-accent-soft disabled:opacity-50 transition-colors"
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
  const {
    activeDealsCount,
    activeDragDeal,
    companies,
    companiesMap,
    dealsByStage,
    handleDealCreated,
    handleDragEnd,
    handleDragStart,
    handleInsightsSaved,
    insightsRefreshKey,
    isHomeWorkspace,
    isModalOpen,
    isSettingsOpen,
    lastActivityMap,
    loading,
    newThisMonthCount,
    partner,
    sensors,
    setIsModalOpen,
    setIsSettingsOpen,
    setShowInactive,
    showInactive,
    totalSignedAmount,
    user,
  } = useClientsWorkspace();

  if (!isHomeWorkspace) return null;

  return (
    <div className="min-h-screen">
      <main id="main-content" className="max-w-full px-4 sm:px-6 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6 gap-3 flex-wrap">
          <h2 className="text-lg font-semibold text-foreground">客戶</h2>
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => setIsModalOpen(true)}
              className="px-3 py-1.5 text-sm rounded bg-accent-soft text-primary-foreground hover:bg-accent-soft transition-colors"
            >
              + 新增商機
            </button>
            <Link
              href="/clients/companies"
              className="px-3 py-1.5 text-sm rounded bg-soft text-foreground hover:bg-soft transition-colors"
            >
              公司列表
            </Link>
            <button
              onClick={() => setIsSettingsOpen(true)}
              className="px-3 py-1.5 text-sm rounded bg-soft text-foreground hover:bg-soft transition-colors"
              title="停滯天數設定"
            >
              ⚙️
            </button>
            <label className="flex items-center gap-1.5 text-sm text-dim cursor-pointer">
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
            <div className="bg-panel border bd-hair rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-foreground">{activeDealsCount}</p>
              <p className="text-xs text-dim mt-0.5">進行中商機</p>
            </div>
            <div className="bg-panel border bd-hair rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-foreground">{newThisMonthCount}</p>
              <p className="text-xs text-dim mt-0.5">本月新增</p>
            </div>
            <div className="bg-panel border bd-hair rounded-lg p-3 text-center">
              <p className="text-xl font-bold text-foreground">
                {totalSignedAmount > 0
                  ? `${(totalSignedAmount / 10000).toFixed(0)}萬`
                  : "—"}
              </p>
              <p className="text-xs text-dim mt-0.5">成交案值</p>
            </div>
          </div>
        )}

        {/* AI Insights */}
        {!loading && (
          <DealHealthInsights user={user} refreshKey={insightsRefreshKey} />
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
                  lastActivityMap={lastActivityMap}
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

        {/* New Deal Modal */}
        <NewDealModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          companies={companies}
          onCreated={handleDealCreated}
          user={user}
          userId={partner?.id ?? ""}
        />

        {/* Settings Modal */}
        <StaleThresholdsModal
          isOpen={isSettingsOpen}
          onClose={() => setIsSettingsOpen(false)}
          user={user}
          onSaved={handleInsightsSaved}
        />
      </main>
    </div>
  );
}

export default function Page() {
  return <ClientsPage />;
}
