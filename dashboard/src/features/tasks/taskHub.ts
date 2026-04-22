"use client";

import type { PlanSummary } from "@/lib/api";
import type { Entity, Task, TaskPriority, TaskStatus } from "@/types";

export type TaskHubFocus = `milestone:${string}` | `plan:${string}`;

export interface TaskHubProductRecap {
  productId: string;
  productName: string;
  productSummary: string;
  currentMilestone: { id: string; name: string } | null;
  activePlanCount: number;
  openTaskCount: number;
  blockedCount: number;
  reviewCount: number;
  overdueCount: number;
  lastUpdatedAt: Date | null;
  riskLevel: "critical" | "warning" | "healthy";
  plans: Array<{
    id: string;
    goal: string;
    openCount: number;
    blockedCount: number;
    reviewCount: number;
    overdueCount: number;
  }>;
  milestones: Array<{
    id: string;
    name: string;
    openCount: number;
    blockedCount: number;
    reviewCount: number;
    overdueCount: number;
  }>;
}

export interface TaskHubRadarItem {
  id: string;
  productId: string;
  productName: string;
  kind: "plan" | "milestone";
  title: string;
  subtitle: string;
  focus: TaskHubFocus;
  blockedCount: number;
  reviewCount: number;
  overdueCount: number;
  openCount: number;
  riskScore: number;
}

export interface TaskHubSnapshot {
  summary: {
    productCount: number;
    activeMilestoneCount: number;
    activePlanCount: number;
    blockedPlanCount: number;
    overdueWorkCount: number;
  };
  products: TaskHubProductRecap[];
  radar: TaskHubRadarItem[];
  recentChanges: Array<{
    id: string;
    productId: string;
    productName: string;
    title: string;
    subtitle: string;
    updatedAt: Date | null;
  }>;
}

export interface TaskHubNavigationState {
  selectedStatuses: TaskStatus[];
  selectedPriority: TaskPriority | null;
  selectedProject: string | null;
  selectedDispatcher: string | null;
  selectedBlockedMode: "all" | "blocked" | "unblocked";
  scrollY: number;
}

const NAV_STATE_KEY = "zenos.task-hub.nav";
const OPEN_STATUSES = new Set<TaskStatus>(["todo", "in_progress", "review"]);

function normalizeName(value: string | null | undefined): string {
  if (!value) return "";
  return value.normalize("NFKC").trim().replace(/\s+/g, " ").toLocaleLowerCase();
}

function isOpenTask(task: Task): boolean {
  return OPEN_STATUSES.has(task.status);
}

function isTaskBlocked(task: Task): boolean {
  return task.blockedBy.length > 0 || Boolean(task.blockedReason);
}

function isTaskOverdue(task: Task, now: number): boolean {
  return Boolean(task.dueDate && task.dueDate.getTime() < now && task.status !== "done");
}

function getTaskTimestamp(task: Task): number {
  return task.updatedAt?.getTime() ?? task.createdAt?.getTime() ?? 0;
}

function buildProductLookup(products: Entity[]) {
  const byId = new Map(products.map((entity) => [entity.id, entity]));
  const byName = new Map(products.map((entity) => [normalizeName(entity.name), entity]));
  return { byId, byName };
}

function resolveTaskProductId(
  task: Task,
  productsById: Map<string, Entity>,
  productsByName: Map<string, Entity>,
  goalsById: Map<string, Entity>,
  plansById: Map<string, PlanSummary>,
): string | null {
  for (const linkedId of task.linkedEntities) {
    if (productsById.has(linkedId)) return linkedId;
    const goal = goalsById.get(linkedId);
    if (goal?.parentId && productsById.has(goal.parentId)) {
      return goal.parentId;
    }
  }

  if (task.planId) {
    const plan = plansById.get(task.planId);
    if (plan?.project_id && productsById.has(plan.project_id)) return plan.project_id;
    const byPlanName = productsByName.get(normalizeName(plan?.project));
    if (byPlanName) return byPlanName.id;
  }

  const byTaskName = productsByName.get(normalizeName(task.project));
  return byTaskName?.id ?? null;
}

export function buildProjectFocusHref(productId: string, focus?: TaskHubFocus | null): string {
  const query = new URLSearchParams({ id: productId });
  if (focus) query.set("focus", focus);
  return `/projects?${query.toString()}`;
}

export function storeTaskHubNavigationState(state: TaskHubNavigationState): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(NAV_STATE_KEY, JSON.stringify(state));
}

export function readTaskHubNavigationState(): TaskHubNavigationState | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(NAV_STATE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<TaskHubNavigationState>;
    return {
      selectedStatuses: Array.isArray(parsed.selectedStatuses) ? parsed.selectedStatuses : [],
      selectedPriority: parsed.selectedPriority ?? null,
      selectedProject: parsed.selectedProject ?? null,
      selectedDispatcher: parsed.selectedDispatcher ?? null,
      selectedBlockedMode:
        parsed.selectedBlockedMode === "blocked" || parsed.selectedBlockedMode === "unblocked"
          ? parsed.selectedBlockedMode
          : "all",
      scrollY: typeof parsed.scrollY === "number" ? parsed.scrollY : 0,
    };
  } catch {
    return null;
  }
}

export function clearTaskHubNavigationState(): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(NAV_STATE_KEY);
}

export function buildTaskHubSnapshot(params: {
  entities: Entity[];
  tasks: Task[];
  plans: PlanSummary[];
  now?: Date;
}): TaskHubSnapshot {
  const { entities, tasks, plans, now = new Date() } = params;
  const products = entities.filter((entity) => entity.type === "product");
  const goals = entities.filter((entity) => entity.type === "goal");
  const goalsById = new Map(goals.map((goal) => [goal.id, goal]));
  const plansById = new Map(plans.map((plan) => [plan.id, plan]));
  const { byId: productsById, byName: productsByName } = buildProductLookup(products);
  const nowMs = now.getTime();

  const productTasks = new Map<string, Task[]>();
  const tasksByPlan = new Map<string, Task[]>();
  const tasksByMilestone = new Map<string, Task[]>();

  for (const task of tasks) {
    const productId = resolveTaskProductId(task, productsById, productsByName, goalsById, plansById);
    if (!productId) continue;
    productTasks.set(productId, [...(productTasks.get(productId) ?? []), task]);
    if (task.planId) {
      tasksByPlan.set(task.planId, [...(tasksByPlan.get(task.planId) ?? []), task]);
    }
    for (const linkedId of task.linkedEntities) {
      const goal = goalsById.get(linkedId);
      if (!goal) continue;
      tasksByMilestone.set(goal.id, [...(tasksByMilestone.get(goal.id) ?? []), task]);
    }
  }

  const productRecaps = products.map((product) => {
    const relatedGoals = goals.filter((goal) => goal.parentId === product.id);
    const relatedPlans = plans.filter((plan) => {
      if (plan.project_id === product.id) return true;
      return normalizeName(plan.project) === normalizeName(product.name);
    });
    const relatedTasks = (productTasks.get(product.id) ?? []).filter(isOpenTask);
    const relatedPlansWithCounts = relatedPlans.map((plan) => {
      const planTasks = (tasksByPlan.get(plan.id) ?? []).filter(isOpenTask);
      const blockedCount = planTasks.filter(isTaskBlocked).length;
      const reviewCount = planTasks.filter((task) => task.status === "review").length;
      const overdueCount = planTasks.filter((task) => isTaskOverdue(task, nowMs)).length;
      return {
        id: plan.id,
        goal: plan.goal,
        openCount: planTasks.length,
        blockedCount,
        reviewCount,
        overdueCount,
      };
    });
    const relatedMilestones = relatedGoals.map((goal) => {
      const milestoneTasks = (tasksByMilestone.get(goal.id) ?? []).filter(isOpenTask);
      return {
        id: goal.id,
        name: goal.name,
        openCount: milestoneTasks.length,
        blockedCount: milestoneTasks.filter(isTaskBlocked).length,
        reviewCount: milestoneTasks.filter((task) => task.status === "review").length,
        overdueCount: milestoneTasks.filter((task) => isTaskOverdue(task, nowMs)).length,
      };
    });

    const currentMilestoneEntity =
      relatedGoals
        .filter((goal) => goal.status === "active" || goal.status === "current" || goal.status === "planned")
        .sort((left, right) => (right.updatedAt?.getTime() ?? 0) - (left.updatedAt?.getTime() ?? 0))[0] ?? null;
    const blockedCount = relatedTasks.filter(isTaskBlocked).length;
    const reviewCount = relatedTasks.filter((task) => task.status === "review").length;
    const overdueCount = relatedTasks.filter((task) => isTaskOverdue(task, nowMs)).length;
    const lastUpdatedAt = relatedTasks
      .slice()
      .sort((left, right) => getTaskTimestamp(right) - getTaskTimestamp(left))[0]?.updatedAt ?? product.updatedAt;
    const riskLevel: TaskHubProductRecap["riskLevel"] =
      blockedCount > 0 || overdueCount > 0
        ? "critical"
        : reviewCount > 0
          ? "warning"
          : "healthy";

    return {
      productId: product.id,
      productName: product.name,
      productSummary: product.summary,
      currentMilestone: currentMilestoneEntity
        ? { id: currentMilestoneEntity.id, name: currentMilestoneEntity.name }
        : null,
      activePlanCount: relatedPlansWithCounts.filter(
        (plan) => plan.openCount > 0 || plan.blockedCount > 0 || plan.reviewCount > 0 || plan.overdueCount > 0,
      ).length,
      openTaskCount: relatedTasks.length,
      blockedCount,
      reviewCount,
      overdueCount,
      lastUpdatedAt,
      riskLevel,
      plans: relatedPlansWithCounts.sort((left, right) => right.openCount - left.openCount),
      milestones: relatedMilestones.sort((left, right) => right.openCount - left.openCount),
    };
  });

  const radar = [
    ...productRecaps.flatMap((product) =>
      product.plans
        .filter((plan) => plan.blockedCount > 0 || plan.overdueCount > 0 || plan.reviewCount > 0)
        .map<TaskHubRadarItem>((plan) => ({
          id: `plan-${plan.id}`,
          productId: product.productId,
          productName: product.productName,
          kind: "plan",
          title: plan.goal,
          subtitle: `${product.productName} · plan`,
          focus: `plan:${plan.id}`,
          blockedCount: plan.blockedCount,
          reviewCount: plan.reviewCount,
          overdueCount: plan.overdueCount,
          openCount: plan.openCount,
          riskScore: plan.blockedCount * 100 + plan.overdueCount * 10 + plan.reviewCount,
        })),
    ),
    ...productRecaps.flatMap((product) =>
      product.milestones
        .filter((milestone) => milestone.blockedCount > 0 || milestone.overdueCount > 0 || milestone.reviewCount > 0)
        .map<TaskHubRadarItem>((milestone) => ({
          id: `milestone-${milestone.id}`,
          productId: product.productId,
          productName: product.productName,
          kind: "milestone",
          title: milestone.name,
          subtitle: `${product.productName} · milestone`,
          focus: `milestone:${milestone.id}`,
          blockedCount: milestone.blockedCount,
          reviewCount: milestone.reviewCount,
          overdueCount: milestone.overdueCount,
          openCount: milestone.openCount,
          riskScore: milestone.blockedCount * 100 + milestone.overdueCount * 10 + milestone.reviewCount,
        })),
    ),
  ]
    .sort((left, right) => right.riskScore - left.riskScore)
    .slice(0, 6);

  const recentChanges = productRecaps
    .filter((product) => product.lastUpdatedAt)
    .sort((left, right) => (right.lastUpdatedAt?.getTime() ?? 0) - (left.lastUpdatedAt?.getTime() ?? 0))
    .slice(0, 6)
    .map((product) => ({
      id: product.productId,
      productId: product.productId,
      productName: product.productName,
      title: product.plans[0]?.goal ?? product.productName,
      subtitle:
        product.blockedCount > 0
          ? `${product.blockedCount} blocked`
          : product.reviewCount > 0
            ? `${product.reviewCount} review`
            : `${product.openTaskCount} open work`,
      updatedAt: product.lastUpdatedAt,
    }));

  return {
    summary: {
      productCount: productRecaps.length,
      activeMilestoneCount: productRecaps.filter((product) => product.currentMilestone).length,
      activePlanCount: productRecaps.reduce((sum, product) => sum + product.activePlanCount, 0),
      blockedPlanCount: productRecaps.reduce(
        (sum, product) => sum + product.plans.filter((plan) => plan.blockedCount > 0).length,
        0,
      ),
      overdueWorkCount: productRecaps.reduce((sum, product) => sum + product.overdueCount, 0),
    },
    products: productRecaps.sort((left, right) => {
      const riskOrder: Record<TaskHubProductRecap["riskLevel"], number> = {
        critical: 0,
        warning: 1,
        healthy: 2,
      };
      const riskDiff = riskOrder[left.riskLevel] - riskOrder[right.riskLevel];
      if (riskDiff !== 0) return riskDiff;
      return (right.lastUpdatedAt?.getTime() ?? 0) - (left.lastUpdatedAt?.getTime() ?? 0);
    }),
    radar,
    recentChanges,
  };
}
