import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearSessionStarted,
  clearSessionSnapshot,
  COPILOT_SESSION_TTL_MS,
  markSessionStarted,
  readFreshSessionStartedAt,
  readFreshSessionSnapshot,
  writeSessionSnapshot,
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

  it("stores and restores fresh session snapshots", () => {
    const storage = makeStorage();
    Object.defineProperty(window, "localStorage", {
      value: storage,
      configurable: true,
    });

    writeSessionSnapshot("chat.snapshot", {
      messages: [{ role: "assistant", content: "hello" }],
      status: "idle",
    });

    expect(readFreshSessionSnapshot<{ messages: Array<{ role: string; content: string }>; status: string }>(
      "chat.snapshot"
    )).toEqual({
      messages: [{ role: "assistant", content: "hello" }],
      status: "idle",
    });
  });

  it("expires stale snapshots and clears them", () => {
    const now = 1_000_000;
    const storage = makeStorage({
      "stale.snapshot": JSON.stringify({
        updatedAt: now - COPILOT_SESSION_TTL_MS - 1,
        data: { messages: [] },
      }),
    });
    Object.defineProperty(window, "localStorage", {
      value: storage,
      configurable: true,
    });

    expect(readFreshSessionSnapshot("stale.snapshot", [], COPILOT_SESSION_TTL_MS, now)).toBeNull();
    expect(storage.removeItem).toHaveBeenCalledWith("stale.snapshot");
  });

  it("can clear stored snapshots explicitly", () => {
    const storage = makeStorage({
      "new.snapshot": JSON.stringify({
        updatedAt: 123,
        data: { messages: [] },
      }),
      "legacy.snapshot": JSON.stringify({
        updatedAt: 456,
        data: { messages: [] },
      }),
    });
    Object.defineProperty(window, "localStorage", {
      value: storage,
      configurable: true,
    });

    clearSessionSnapshot("new.snapshot", ["legacy.snapshot"]);

    expect(storage.removeItem).toHaveBeenCalledWith("new.snapshot");
    expect(storage.removeItem).toHaveBeenCalledWith("legacy.snapshot");
  });
});
