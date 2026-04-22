const DEFAULT_SESSION_TTL_MS = 55 * 60 * 1000;

function getStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  return window.localStorage;
}

function safeGetItem(storage: Storage, key: string): string | null {
  return typeof storage.getItem === "function" ? storage.getItem(key) : null;
}

function safeSetItem(storage: Storage, key: string, value: string): void {
  if (typeof storage.setItem === "function") {
    storage.setItem(key, value);
  }
}

function safeRemoveItem(storage: Storage, key: string): void {
  if (typeof storage.removeItem === "function") {
    storage.removeItem(key);
  }
}

function removeKeys(storage: Storage, keys: string[]): void {
  keys.forEach((key) => safeRemoveItem(storage, key));
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
    const raw = safeGetItem(storage, key);
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
  safeSetItem(storage, storageKey, String(startedAt));
  removeKeys(storage, legacyKeys);
}

export function clearSessionStarted(storageKey: string, legacyKeys: string[] = []): void {
  const storage = getStorage();
  if (!storage) return;
  removeKeys(storage, [storageKey, ...legacyKeys]);
}

interface StoredSessionSnapshot<T> {
  updatedAt: number;
  data: T;
}

function readSnapshotRecord<T>(
  storage: Storage,
  key: string
): StoredSessionSnapshot<T> | null {
  const raw = safeGetItem(storage, key);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<StoredSessionSnapshot<T>>;
    if (
      !parsed ||
      typeof parsed !== "object" ||
      !Number.isFinite(parsed.updatedAt) ||
      parsed.updatedAt! <= 0 ||
      !("data" in parsed)
    ) {
      safeRemoveItem(storage, key);
      return null;
    }
    return {
      updatedAt: Number(parsed.updatedAt),
      data: parsed.data as T,
    };
  } catch {
    safeRemoveItem(storage, key);
    return null;
  }
}

export function readFreshSessionSnapshot<T>(
  storageKey: string,
  legacyKeys: string[] = [],
  ttlMs = DEFAULT_SESSION_TTL_MS,
  now = Date.now()
): T | null {
  const storage = getStorage();
  if (!storage) return null;

  const keys = [storageKey, ...legacyKeys];
  for (const key of keys) {
    const snapshot = readSnapshotRecord<T>(storage, key);
    if (!snapshot) continue;
    if (now - snapshot.updatedAt > ttlMs) {
      removeKeys(storage, keys);
      return null;
    }
    return snapshot.data;
  }

  return null;
}

export function writeSessionSnapshot<T>(
  storageKey: string,
  data: T,
  legacyKeys: string[] = [],
  updatedAt = Date.now()
): void {
  const storage = getStorage();
  if (!storage) return;
  safeSetItem(
    storage,
    storageKey,
    JSON.stringify({
      updatedAt,
      data,
    } satisfies StoredSessionSnapshot<T>)
  );
  removeKeys(storage, legacyKeys);
}

export function clearSessionSnapshot(storageKey: string, legacyKeys: string[] = []): void {
  const storage = getStorage();
  if (!storage) return;
  removeKeys(storage, [storageKey, ...legacyKeys]);
}

export const COPILOT_SESSION_TTL_MS = DEFAULT_SESSION_TTL_MS;
