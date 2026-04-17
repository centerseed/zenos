import { apiRequest } from "@/lib/api-client";

async function apiFetch<T>(path: string, token: string, options?: RequestInit): Promise<T> {
  return apiRequest<T>(path, {
    ...options,
    body: options?.body ?? undefined,
    token,
  });
}

export interface Strategy {
  documentId?: string;
  updatedAt?: string;
  audience: string[];
  tone: string;
  coreMessage: string;
  platforms: string[];
  frequency: string;
  contentMix: Record<string, number>;
  campaignGoal: string;
  ctaStrategy: string;
  referenceMaterials: string[];
  pendingFields?: string[];
  sourceCitations?: Array<{ node_id: string; node_name: string; field_ids?: string[] }>;
  confidence?: "high" | "medium" | "low" | "";
  summaryEntry?: string;
}

export interface DayPlan {
  day: string;
  platform: string;
  topic: string;
  status: "published" | "confirmed" | "suggested";
}

export interface WeekPlan {
  weekLabel: string;
  isCurrent: boolean;
  days: DayPlan[];
  aiNote: string;
}

export interface PostMetrics {
  likes?: number;
  comments?: number;
  shares?: number;
  saves?: number;
  clicks?: number;
  trials?: number;
}

export interface Post {
  id: string;
  platform: string;
  status:
    | "topic_planned"
    | "intel_ready"
    | "draft_generated"
    | "draft_confirmed"
    | "platform_adapted"
    | "platform_confirmed"
    | "scheduled"
    | "published"
    | "failed";
  title: string;
  preview: string;
  imageDesc?: string;
  scheduledAt?: string;
  publishedAt?: string;
  aiReason?: string;
  metrics?: PostMetrics;
}

export interface MarketingProject {
  id: string;
  name: string;
  description: string;
  status: "active" | "blocked" | "completed";
  projectType: "long_term" | "short_term";
  updatedAt?: string;
  dateRange?: { start: string; end: string } | null;
  productId?: string | null;
  blockReason?: string;
  thisWeek: { posts: number; approved: number; published: number };
  stats: { followers: string; postsThisMonth: number; avgEngagement: string };
  trend: { followers: string; engagement: string };
  strategy?: Strategy;
  contentPlan?: WeekPlan[];
  posts: Post[];
  entries?: Array<{
    id: string;
    type: string;
    content: string;
    context?: string;
    author?: string;
    createdAt?: string;
  }>;
}

export interface MarketingProjectGroup {
  product: { id: string | null; name: string };
  projects: MarketingProject[];
}

export interface MarketingStyle {
  id: string;
  title: string;
  level: "product" | "platform" | "project";
  platform?: string | null;
  projectId?: string | null;
  content: string;
  updatedAt?: string;
}

export interface MarketingStyleBuckets {
  product: MarketingStyle[];
  platform: MarketingStyle[];
  project: MarketingStyle[];
}

export interface MarketingPrompt {
  skill: string;
  title: string;
  publishedVersion: number;
  publishedContent: string;
  draftContent: string;
  draftUpdatedAt: string;
  history: Array<{
    version: number;
    createdAt: string;
    createdBy: string;
    note: string;
    isPublished: boolean;
  }>;
}

export async function getMarketingProjectGroups(token: string): Promise<MarketingProjectGroup[]> {
  const res = await apiFetch<{ groups: MarketingProjectGroup[] }>("/api/marketing/projects", token);
  return res.groups || [];
}

export async function getMarketingProjectDetail(token: string, projectId: string): Promise<MarketingProject | null> {
  try {
    const res = await apiFetch<{ project: MarketingProject }>(`/api/marketing/projects/${projectId}`, token);
    return res.project;
  } catch {
    return null;
  }
}

export async function reviewMarketingPost(
  token: string,
  postId: string,
  data: { action: "approve" | "request_changes" | "reject"; comment?: string; reviewer?: string }
): Promise<Post | null> {
  try {
    const res = await apiFetch<{ post: Post }>(`/api/marketing/posts/${postId}/review`, token, {
      method: "POST",
      body: JSON.stringify(data),
    });
    return res.post;
  } catch {
    return null;
  }
}

export async function createMarketingTopic(
  token: string,
  projectId: string,
  data: { topic: string; platform?: string; brief?: string; aiReason?: string }
): Promise<Post> {
  const res = await apiFetch<{ post: Post }>(`/api/marketing/projects/${projectId}/topics`, token, {
    method: "POST",
    body: JSON.stringify(data),
  });
  return res.post;
}

export async function updateMarketingProjectStrategy(
  token: string,
  projectId: string,
  data: {
    audience: string[];
    tone: string;
    coreMessage: string;
    platforms: string[];
    frequency?: string;
    contentMix?: Record<string, number>;
    campaignGoal?: string;
    ctaStrategy?: string;
    referenceMaterials?: string[];
    pendingFields?: string[];
    sourceCitations?: Array<{ node_id: string; node_name: string; field_ids?: string[] }>;
    confidence?: "high" | "medium" | "low";
    expectedUpdatedAt?: string;
  }
): Promise<MarketingProject> {
  const res = await apiFetch<{ project: MarketingProject }>(`/api/marketing/projects/${projectId}/strategy`, token, {
    method: "PUT",
    body: JSON.stringify(data),
  });
  return res.project;
}

export async function updateMarketingProjectContentPlan(
  token: string,
  projectId: string,
  contentPlan: WeekPlan[]
): Promise<MarketingProject> {
  const res = await apiFetch<{ project: MarketingProject }>(`/api/marketing/projects/${projectId}/content-plan`, token, {
    method: "PUT",
    body: JSON.stringify({ contentPlan }),
  });
  return res.project;
}

export async function createMarketingProject(
  token: string,
  data: {
    productId: string;
    name: string;
    projectType: "long_term" | "short_term";
    description?: string;
    dateRange?: { start: string; end: string } | null;
  }
): Promise<MarketingProject> {
  const res = await apiFetch<{ project: MarketingProject }>("/api/marketing/projects", token, {
    method: "POST",
    body: JSON.stringify(data),
  });
  return res.project;
}

export async function getMarketingProjectStyles(token: string, projectId: string): Promise<MarketingStyleBuckets> {
  const res = await apiFetch<{ styles: MarketingStyleBuckets }>(`/api/marketing/projects/${projectId}/styles`, token);
  return res.styles || { product: [], platform: [], project: [] };
}

export async function createMarketingStyle(
  token: string,
  data: {
    title: string;
    level: "product" | "platform" | "project";
    content: string;
    productId?: string;
    projectId?: string;
    platform?: string;
  }
): Promise<MarketingStyle> {
  const res = await apiFetch<{ style: MarketingStyle }>("/api/marketing/styles", token, {
    method: "POST",
    body: JSON.stringify(data),
  });
  return res.style;
}

export async function updateMarketingStyle(
  token: string,
  styleId: string,
  data: { title?: string; content: string }
): Promise<MarketingStyle> {
  const res = await apiFetch<{ style: MarketingStyle }>(`/api/marketing/styles/${styleId}`, token, {
    method: "PUT",
    body: JSON.stringify(data),
  });
  return res.style;
}

export async function getMarketingPrompts(token: string): Promise<{ hubId: string; prompts: MarketingPrompt[] }> {
  const res = await apiFetch<{ hubId: string; prompts: MarketingPrompt[] }>("/api/marketing/prompts", token);
  return {
    hubId: res.hubId,
    prompts: res.prompts || [],
  };
}

export async function updateMarketingPromptDraft(
  token: string,
  skill: string,
  content: string
): Promise<MarketingPrompt> {
  const res = await apiFetch<{ prompt: MarketingPrompt }>(`/api/marketing/prompts/${skill}/draft`, token, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
  return res.prompt;
}

export async function publishMarketingPrompt(
  token: string,
  skill: string,
  data?: { sourceVersion?: number; note?: string }
): Promise<MarketingPrompt> {
  const res = await apiFetch<{ prompt: MarketingPrompt }>(`/api/marketing/prompts/${skill}/publish`, token, {
    method: "POST",
    body: JSON.stringify(data || {}),
  });
  return res.prompt;
}
