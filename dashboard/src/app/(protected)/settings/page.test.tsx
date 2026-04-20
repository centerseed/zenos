import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

const pushToastMock = vi.fn();
const checkCoworkHelperHealthMock = vi.fn();
const setDefaultHelperBaseUrlMock = vi.fn();
const setDefaultHelperTokenMock = vi.fn();
const setDefaultHelperCwdMock = vi.fn();
const setDefaultHelperModelMock = vi.fn();

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    partner: {
      id: "partner-1",
      email: "barry@example.com",
      displayName: "Barry",
      apiKey: "test-key-12345678", // pragma: allowlist secret
      authorizedEntityIds: [],
      sharedPartnerId: null,
      workspaceRole: "owner",
      isAdmin: true,
      status: "active",
    },
  }),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({
    pushToast: pushToastMock,
  }),
}));

vi.mock("@/lib/cowork-helper", () => ({
  checkCoworkHelperHealth: (...args: unknown[]) => checkCoworkHelperHealthMock(...args),
  getDefaultHelperBaseUrl: () => "http://127.0.0.1:4317",
  getDefaultHelperToken: () => "mk-legacy-token",
  getDefaultHelperCwd: () => "/tmp/zenos-workspace",
  getDefaultHelperModel: () => "sonnet",
  setDefaultHelperBaseUrl: (...args: unknown[]) => setDefaultHelperBaseUrlMock(...args),
  setDefaultHelperToken: (...args: unknown[]) => setDefaultHelperTokenMock(...args),
  setDefaultHelperCwd: (...args: unknown[]) => setDefaultHelperCwdMock(...args),
  setDefaultHelperModel: (...args: unknown[]) => setDefaultHelperModelMock(...args),
}));

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    checkCoworkHelperHealthMock.mockResolvedValue({
      ok: true,
      status: "ok",
      message: "helper 已連線",
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
      }),
    );
  });

  afterEach(() => {
    cleanup();
  });

  it("renders MCP and helper guidance in Zen Ink settings page", async () => {
    const { default: SettingsPage } = await import("./page");
    render(<SettingsPage />);

    expect(screen.getByText("Settings")).toBeInTheDocument();
    expect(screen.getByText("MCP server")).toBeInTheDocument();
    expect(screen.getByText("Local helper")).toBeInTheDocument();
    expect(screen.getByText("MCP / Helper 怎麼分工")).toBeInTheDocument();
    expect(screen.getByText(/Marketing \/ Clients 裡的 AI rail 打不開/)).toBeInTheDocument();
  });

  it("persists helper fields to local settings", async () => {
    const { default: SettingsPage } = await import("./page");
    render(<SettingsPage />);

    fireEvent.change(screen.getByLabelText("Helper Base URL"), {
      target: { value: "http://127.0.0.1:4411" },
    });
    fireEvent.change(screen.getByLabelText("Helper Token"), {
      target: { value: "mk-new-token" },
    });
    fireEvent.change(screen.getByLabelText("Helper Workspace Path"), {
      target: { value: "/Users/demo/workspace" },
    });
    fireEvent.change(screen.getByLabelText("Helper Model"), {
      target: { value: "opus" },
    });

    fireEvent.click(screen.getByRole("button", { name: "儲存 Helper 設定" }));

    expect(setDefaultHelperBaseUrlMock).toHaveBeenCalledWith("http://127.0.0.1:4411");
    expect(setDefaultHelperTokenMock).toHaveBeenCalledWith("mk-new-token");
    expect(setDefaultHelperCwdMock).toHaveBeenCalledWith("/Users/demo/workspace");
    expect(setDefaultHelperModelMock).toHaveBeenCalledWith("opus");
    expect(pushToastMock).toHaveBeenCalled();
  });

  it("checks helper health from settings page", async () => {
    const { default: SettingsPage } = await import("./page");
    render(<SettingsPage />);

    fireEvent.click(screen.getByRole("button", { name: "檢查 Helper 連線" }));

    await waitFor(() => {
      expect(checkCoworkHelperHealthMock).toHaveBeenCalledWith(
        "http://127.0.0.1:4317",
        "mk-legacy-token",
      );
    });
  });
});
