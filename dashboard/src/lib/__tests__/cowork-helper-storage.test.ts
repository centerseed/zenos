import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  getDefaultHelperBaseUrl,
  getDefaultHelperCwd,
  getDefaultHelperModel,
  getDefaultHelperToken,
  setDefaultHelperBaseUrl,
  setDefaultHelperCwd,
  setDefaultHelperModel,
  setDefaultHelperToken,
} from "@/lib/cowork-helper";

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

describe("cowork helper storage keys", () => {
  beforeEach(() => {
    Object.defineProperty(window, "localStorage", {
      value: makeStorage(),
      configurable: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("falls back to legacy marketing storage keys when shared copilot keys are empty", () => {
    Object.defineProperty(window, "localStorage", {
      value: makeStorage({
        "zenos.marketing.cowork.helperBaseUrl": "http://127.0.0.1:9999",
        "zenos.marketing.cowork.helperToken": "legacy-token",
        "zenos.marketing.cowork.cwd": "/tmp/legacy",
        "zenos.marketing.cowork.model": "opus",
      }),
      configurable: true,
    });

    expect(getDefaultHelperBaseUrl()).toBe("http://127.0.0.1:9999");
    expect(getDefaultHelperToken()).toBe("legacy-token");
    expect(getDefaultHelperCwd()).toBe("/tmp/legacy");
    expect(getDefaultHelperModel()).toBe("opus");
  });

  it("writes new values only to the shared copilot keys", () => {
    const storage = makeStorage();
    Object.defineProperty(window, "localStorage", {
      value: storage,
      configurable: true,
    });

    setDefaultHelperBaseUrl("http://127.0.0.1:4318");
    setDefaultHelperToken("token-1");
    setDefaultHelperCwd("/tmp/workspace");
    setDefaultHelperModel("haiku");

    expect(storage.setItem).toHaveBeenCalledWith(
      "zenos.copilot.helperBaseUrl",
      "http://127.0.0.1:4318"
    );
    expect(storage.setItem).toHaveBeenCalledWith("zenos.copilot.helperToken", "token-1");
    expect(storage.setItem).toHaveBeenCalledWith("zenos.copilot.cwd", "/tmp/workspace");
    expect(storage.setItem).toHaveBeenCalledWith("zenos.copilot.model", "haiku");
  });
});
