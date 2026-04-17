"use client";

import {
  getCoworkGraphContext,
  type GraphContextResponse,
} from "@/lib/api";

const DEFAULT_GRAPH_CONTEXT_BUDGET = 1500;
const GRAPH_CONTEXT_CACHE_TTL_MS = 60_000;

type CacheEntry = {
  expiresAt: number;
  value: GraphContextResponse;
};

const graphContextCache = new Map<string, CacheEntry>();

function buildCacheKey(seedId: string, budgetTokens: number, includeDocs: boolean): string {
  return `${seedId}:${budgetTokens}:${includeDocs ? "docs" : "entities"}`;
}

export function clearGraphContextCache(): void {
  graphContextCache.clear();
}

export function createGraphContextLoadedPayload(graphContext: GraphContextResponse): {
  l2_count: number;
  l3_count: number;
  truncated: boolean;
  fallback_mode: GraphContextResponse["fallback_mode"];
} {
  return {
    l2_count: graphContext.neighbors.length,
    l3_count: graphContext.neighbors.reduce((sum, neighbor) => sum + neighbor.documents.length, 0),
    truncated: graphContext.truncated,
    fallback_mode: graphContext.fallback_mode,
  };
}

export async function fetchGraphContext(
  token: string,
  options: {
    seedId: string | null | undefined;
    budgetTokens?: number;
    includeDocs?: boolean;
    forceRefresh?: boolean;
  }
): Promise<GraphContextResponse | null> {
  const seedId = options.seedId?.trim();
  if (!seedId) return null;

  const budgetTokens = options.budgetTokens ?? DEFAULT_GRAPH_CONTEXT_BUDGET;
  const includeDocs = options.includeDocs !== false;
  const cacheKey = buildCacheKey(seedId, budgetTokens, includeDocs);
  const now = Date.now();
  const cached = graphContextCache.get(cacheKey);
  if (!options.forceRefresh && cached && cached.expiresAt > now) {
    return cached.value;
  }

  const result = await getCoworkGraphContext(token, {
    seedId,
    budgetTokens,
    includeDocs,
  });
  if (!result) return null;

  graphContextCache.set(cacheKey, {
    expiresAt: now + GRAPH_CONTEXT_CACHE_TTL_MS,
    value: result,
  });
  return result;
}

