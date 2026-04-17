"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { PointerSensor, type DragEndEvent, type DragStartEvent, useSensor, useSensors } from "@dnd-kit/core";
import { useAuth } from "@/lib/auth";
import { resolveActiveWorkspace } from "@/lib/partner";
import { getCompanies, getDeals, patchDealStage } from "@/lib/crm-api";
import type { Company, Deal, FunnelStage } from "@/lib/crm-api";

export const FUNNEL_STAGES: FunnelStage[] = [
  "潛在客戶",
  "需求訪談",
  "提案報價",
  "合約議價",
  "導入中",
  "結案",
];

export function useClientsWorkspace() {
  const { user, partner } = useAuth();
  const router = useRouter();
  const { isHomeWorkspace } = resolveActiveWorkspace(partner);
  const [deals, setDeals] = useState<Deal[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [showInactive, setShowInactive] = useState(false);
  const [activeDragId, setActiveDragId] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [insightsRefreshKey, setInsightsRefreshKey] = useState(0);

  useEffect(() => {
    if (partner && !isHomeWorkspace) {
      router.replace("/tasks");
    }
  }, [isHomeWorkspace, partner, router]);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

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
      } finally {
        setLoading(false);
      }
    },
    [partner, user]
  );

  useEffect(() => {
    void loadData(showInactive);
  }, [loadData, showInactive]);

  const companiesMap = useMemo(
    () => Object.fromEntries(companies.map((company) => [company.id, company.name])),
    [companies]
  );

  const lastActivityMap = useMemo(
    () => Object.fromEntries(deals.map((deal) => [deal.id, deal.lastActivityAt ?? undefined])),
    [deals]
  );

  const visibleDeals = useMemo(
    () => (showInactive ? deals : deals.filter((deal) => !deal.isClosedLost && !deal.isOnHold)),
    [deals, showInactive]
  );

  const dealsByStage = useMemo(
    () =>
      Object.fromEntries(
        FUNNEL_STAGES.map((stage) => [stage, visibleDeals.filter((deal) => deal.funnelStage === stage)])
      ) as Record<FunnelStage, Deal[]>,
    [visibleDeals]
  );

  const activeDealsCount = useMemo(
    () => deals.filter((deal) => !deal.isClosedLost && !deal.isOnHold).length,
    [deals]
  );

  const newThisMonthCount = useMemo(() => {
    const thisMonth = new Date();
    return deals.filter((deal) => {
      const created = deal.createdAt;
      return created.getFullYear() === thisMonth.getFullYear() && created.getMonth() === thisMonth.getMonth();
    }).length;
  }, [deals]);

  const totalSignedAmount = useMemo(
    () =>
      deals
        .filter((deal) => deal.funnelStage === "結案" && !deal.isClosedLost)
        .reduce((sum, deal) => sum + (deal.amountTwd ?? 0), 0),
    [deals]
  );

  const handleDragStart = useCallback((event: DragStartEvent) => {
    setActiveDragId(event.active.id as string);
  }, []);

  const handleDragEnd = useCallback(
    async (event: DragEndEvent) => {
      setActiveDragId(null);
      const { active, over } = event;
      if (!over || !user) return;

      const dealId = active.id as string;
      const newStage = over.id as FunnelStage;
      const currentDeal = deals.find((deal) => deal.id === dealId);
      if (!currentDeal || currentDeal.funnelStage === newStage) return;

      setDeals((prev) => prev.map((deal) => (deal.id === dealId ? { ...deal, funnelStage: newStage } : deal)));

      try {
        const token = await user.getIdToken();
        await patchDealStage(token, dealId, newStage);
      } catch (err) {
        console.error("Failed to update deal stage:", err);
        setDeals((prev) =>
          prev.map((deal) => (deal.id === dealId ? { ...deal, funnelStage: currentDeal.funnelStage } : deal))
        );
      }
    },
    [deals, user]
  );

  const activeDragDeal = useMemo(
    () => (activeDragId ? deals.find((deal) => deal.id === activeDragId) ?? null : null),
    [activeDragId, deals]
  );

  const handleDealCreated = useCallback((newDeal: Deal, newCompany?: Company) => {
    if (newCompany) {
      setCompanies((prev) => [...prev, newCompany]);
    }
    setDeals((prev) => [newDeal, ...prev]);
  }, []);

  const handleInsightsSaved = useCallback(() => {
    setInsightsRefreshKey((prev) => prev + 1);
  }, []);

  return {
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
  };
}
