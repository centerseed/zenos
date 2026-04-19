const DEFAULT_SESSION_TTL_MS = 55 * 60 * 1000;

function getStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  return window.localStorage;
}

function removeKeys(storage: Storage, keys: string[]): void {
  keys.forEach((key) => storage.removeItem(key));
}

export function readFreshSessionStartedAt(
  storageKey: string,
  legacyKeys: string[] = [],
  ttlMs = DEFAULT_SESSION_TTL_MS,
  now = Date.now()
): number | null {
  const storage = getStorage();
  if (!storage) return null;

  const keys = [storageKey, ...legacyKeys];
  for (const key of keys) {
    const raw = storage.getItem(key);
    if (!raw) continue;
    const startedAt = Number(raw);
    if (!Number.isFinite(startedAt) || startedAt <= 0 || now - startedAt > ttlMs) {
      removeKeys(storage, keys);
      return null;
    }
    return startedAt;
  }

  return null;
}

export function markSessionStarted(
  storageKey: string,
  legacyKeys: string[] = [],
  startedAt = Date.now()
): void {
  const storage = getStorage();
  if (!storage) return;
  storage.setItem(storageKey, String(startedAt));
  removeKeys(storage, legacyKeys);
}

export function clearSessionStarted(storageKey: string, legacyKeys: string[] = []): void {
  const storage = getStorage();
  if (!storage) return;
  removeKeys(storage, [storageKey, ...legacyKeys]);
}

export const COPILOT_SESSION_TTL_MS = DEFAULT_SESSION_TTL_MS;
