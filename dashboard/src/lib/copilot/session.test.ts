import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearSessionStarted,
  COPILOT_SESSION_TTL_MS,
  markSessionStarted,
  readFreshSessionStartedAt,
} from "@/lib/copilot/session";

function makeStorage(seed: Record<string, string> = {}) {
  const store = new Map(Object.entries(seed));
  return {
    getItem: vi.fn((key: string) => store.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store.set(key, value);
    }),
    removeItem: vi.fn((key: string) => {
      store.delete(key);
    }),
  };
}

describe("copilot session storage", () => {
  beforeEach(() => {
    Object.defineProperty(window, "localStorage", {
      value: makeStorage(),
      configurable: true,
    });
  });

  it("stores timestamp-based started marker", () => {
    const storage = makeStorage();
    Object.defineProperty(window, "localStorage", {
      value: storage,
      configurable: true,
    });

    markSessionStarted("zenos.copilot.started.test", ["legacy.started"], 123456);

    expect(storage.setItem).toHaveBeenCalledWith("zenos.copilot.started.test", "123456");
    expect(storage.removeItem).toHaveBeenCalledWith("legacy.started");
  });

  it("reads a fresh timestamp and rejects stale markers", () => {
    const now = 1_000_000;
    const storage = makeStorage({
      "fresh.started": String(now - 1000),
      "stale.started": String(now - COPILOT_SESSION_TTL_MS - 1),
    });
    Object.defineProperty(window, "localStorage", {
      value: storage,
      configurable: true,
    });

    expect(readFreshSessionStartedAt("fresh.started", [], COPILOT_SESSION_TTL_MS, now)).toBe(now - 1000);
    expect(readFreshSessionStartedAt("stale.started", [], COPILOT_SESSION_TTL_MS, now)).toBeNull();
    expect(storage.removeItem).toHaveBeenCalledWith("stale.started");
  });

  it("clears legacy boolean markers so old sessions do not resume forever", () => {
    const storage = makeStorage({
      "new.started": "1",
      "legacy.started": "1",
    });
    Object.defineProperty(window, "localStorage", {
      value: storage,
      configurable: true,
    });

    expect(readFreshSessionStartedAt("new.started", ["legacy.started"], COPILOT_SESSION_TTL_MS, Date.now())).toBeNull();
    expect(storage.removeItem).toHaveBeenCalledWith("new.started");
    expect(storage.removeItem).toHaveBeenCalledWith("legacy.started");
  });

  it("can clear all markers explicitly", () => {
    const storage = makeStorage({
      "new.started": "123",
      "legacy.started": "456",
    });
    Object.defineProperty(window, "localStorage", {
      value: storage,
      configurable: true,
    });

    clearSessionStarted("new.started", ["legacy.started"]);

    expect(storage.removeItem).toHaveBeenCalledWith("new.started");
    expect(storage.removeItem).toHaveBeenCalledWith("legacy.started");
  });
});
