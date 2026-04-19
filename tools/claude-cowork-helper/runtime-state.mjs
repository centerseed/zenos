export function createRuntimeState() {
  return {
    running: new Map(),
    runningByConversation: new Map(),
    runningBySessionId: new Map(),
  };
}

export function registerRun(state, run) {
  state.running.set(run.requestId, run);
  state.runningByConversation.set(run.conversationId, run);
  state.runningBySessionId.set(run.sessionId, run);
}

export function unregisterRun(state, requestId) {
  const existing = state.running.get(requestId);
  if (!existing) return null;
  state.running.delete(requestId);
  if (state.runningByConversation.get(existing.conversationId)?.requestId === requestId) {
    state.runningByConversation.delete(existing.conversationId);
  }
  if (state.runningBySessionId.get(existing.sessionId)?.requestId === requestId) {
    state.runningBySessionId.delete(existing.sessionId);
  }
  return existing;
}

export function findConflictingRuns(state, criteria) {
  const matches = [];
  const seen = new Set();
  const candidates = [
    criteria.conversationId ? state.runningByConversation.get(criteria.conversationId) : null,
    criteria.sessionId ? state.runningBySessionId.get(criteria.sessionId) : null,
  ];
  for (const run of candidates) {
    if (!run || seen.has(run.requestId)) continue;
    seen.add(run.requestId);
    matches.push(run);
  }
  return matches;
}

export function findRunForCancel(state, criteria) {
  if (criteria.requestId) {
    const match = state.running.get(criteria.requestId);
    if (match) return match;
  }
  if (criteria.conversationId) {
    const match = state.runningByConversation.get(criteria.conversationId);
    if (match) return match;
  }
  return null;
}
