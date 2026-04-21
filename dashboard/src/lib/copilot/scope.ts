"use client";

import type { Partner } from "@/types";
import { getStoredActiveWorkspaceId } from "@/lib/api-client";

export function resolveCopilotWorkspaceId(partner?: Partner | null): string | undefined {
  return (
    getStoredActiveWorkspaceId() ||
    partner?.activeWorkspaceId ||
    partner?.homeWorkspaceId ||
    undefined
  );
}
