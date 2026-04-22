"use client";

import { useEffect, useMemo, useState } from "react";
import { Dialog } from "@/components/zen/Dialog";
import { useToast } from "@/components/zen/Toast";
import { useAuth } from "@/lib/auth";
import { resolveCopilotWorkspaceId } from "@/lib/copilot/scope";
import {
  buildHelperInstallAndStartCommand,
  canCopyAgentConfig,
} from "@/lib/agent-config";
import {
  checkCoworkHelperHealth,
  getDefaultHelperBaseUrl,
  getDefaultHelperCwd,
  getDefaultHelperModel,
  getDefaultHelperToken,
  setDefaultHelperBaseUrl,
  setDefaultHelperCwd,
  setDefaultHelperModel,
  setDefaultHelperToken,
} from "@/lib/cowork-helper";
import { useInk } from "@/lib/zen-ink/tokens";

const HELPER_DEFAULT_URL = "http://127.0.0.1:4317";
const DEFAULT_WORKSPACE = "$HOME/.zenos/claude-code-helper/workspace";

type HealthStatus = "idle" | "checking" | "connected" | "error";

function buildHelperLaunchCommand(params: {
  apiKey: string;
  helperToken: string;
  cwd: string;
}) {
  return buildHelperInstallAndStartCommand({
    apiKey: params.apiKey,
    helperToken: params.helperToken,
    cwd: params.cwd.trim() || DEFAULT_WORKSPACE,
  });
}

export function HelperSetupDialog({
  open,
  onOpenChange,
  workspaceId,
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
  workspaceId?: string;
}) {
  const t = useInk("light");
  const { c, fontBody, fontMono } = t;
  const { pushToast } = useToast();
  const { partner } = useAuth();
  const [helperHealth, setHelperHealth] = useState<HealthStatus>("idle");
  const [helperHint, setHelperHint] = useState("尚未檢查");
  const [helperBaseUrl, setHelperBaseUrlState] = useState(HELPER_DEFAULT_URL);
  const [helperToken, setHelperTokenState] = useState("");
  const [helperCwd, setHelperCwdState] = useState(DEFAULT_WORKSPACE);
  const [helperModel, setHelperModelState] = useState("sonnet");

  useEffect(() => {
    if (!open) return;
    setHelperBaseUrlState(getDefaultHelperBaseUrl());
    setHelperTokenState(getDefaultHelperToken());
    setHelperCwdState(getDefaultHelperCwd() || DEFAULT_WORKSPACE);
    setHelperModelState(getDefaultHelperModel());
  }, [open]);

  const apiKey = partner?.apiKey ?? "";
  const canCopy = canCopyAgentConfig(apiKey);
  const resolvedWorkspaceId = workspaceId || resolveCopilotWorkspaceId(partner);
  const helperCommand = useMemo(
    () =>
      buildHelperLaunchCommand({
        apiKey,
        helperToken,
        cwd: helperCwd,
      }),
    [apiKey, helperCwd, helperToken]
  );

  async function copyText(text: string, label: string) {
    await navigator.clipboard.writeText(text);
    pushToast({
      tone: "success",
      title: `${label} 已複製`,
      description: "可以直接貼到本機終端執行。",
    });
  }

  function saveHelperSettings() {
    setDefaultHelperBaseUrl(helperBaseUrl);
    setDefaultHelperToken(helperToken);
    setDefaultHelperCwd(helperCwd);
    setDefaultHelperModel(helperModel);
    pushToast({
      tone: "success",
      title: "Helper 設定已儲存",
      description: "回到右側 copilot 就能直接續聊。",
    });
  }

  async function checkHelper() {
    setHelperHealth("checking");
    setHelperHint("正在檢查本機 helper");
    const result = await checkCoworkHelperHealth(
      helperBaseUrl,
      helperToken,
      resolvedWorkspaceId
    );
    if (result.ok) {
      setHelperHealth("connected");
      if (result.workspaceProbe?.ok && result.workspaceProbe.workspaceId) {
        const workspaceLabel = result.workspaceProbe.workspaceName
          ? `${result.workspaceProbe.workspaceName} · ${result.workspaceProbe.workspaceId}`
          : result.workspaceProbe.workspaceId;
        setHelperHint(`helper 已連線 · workspace=${workspaceLabel}`);
        return;
      }
      setHelperHint(
        result.workspaceProbe?.message ||
          result.message ||
          "helper 已連線，但尚未確認 workspace probe"
      );
      return;
    }
    setHelperHealth("error");
    setHelperHint(
      result.workspaceProbe?.message || result.message || "helper unavailable"
    );
  }

  const statusTone =
    helperHealth === "connected"
      ? c.jade
      : helperHealth === "error"
        ? c.vermillion
        : helperHealth === "checking"
          ? c.ocher
          : c.inkFaint;

  return (
    <Dialog
      t={t}
      open={open}
      onOpenChange={onOpenChange}
      size="lg"
      title="設定 helper"
      description="只在這裡處理 helper。弄好後關掉視窗，右側 copilot 會保留原本對話。"
    >
      <div style={{ display: "grid", gap: 18 }}>
        <div
          style={{
            border: `1px solid ${c.inkHair}`,
            background: c.paperWarm,
            padding: "14px 16px",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              color: statusTone,
              fontFamily: fontMono,
              fontSize: 11,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: statusTone,
              }}
            />
            {helperHealth === "connected"
              ? "helper connected"
              : helperHealth === "checking"
                ? "checking"
                : helperHealth === "error"
                  ? "helper issue"
                  : "idle"}
          </div>
          <div
            style={{
              marginTop: 8,
              fontFamily: fontBody,
              fontSize: 13,
              lineHeight: 1.7,
              color: c.inkMuted,
            }}
          >
            {helperHint}
          </div>
        </div>

        <label style={{ display: "grid", gap: 8 }}>
          <span
            style={{
              fontFamily: fontMono,
              fontSize: 10,
              color: c.inkFaint,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
            }}
          >
            Base URL
          </span>
          <input
            aria-label="Helper Base URL"
            value={helperBaseUrl}
            onChange={(event) => setHelperBaseUrlState(event.target.value)}
            style={{
              border: `1px solid ${c.inkHair}`,
              background: c.surfaceHi,
              color: c.ink,
              padding: "11px 12px",
              fontFamily: fontMono,
              fontSize: 12,
              outline: "none",
            }}
          />
        </label>

        <label style={{ display: "grid", gap: 8 }}>
          <span
            style={{
              fontFamily: fontMono,
              fontSize: 10,
              color: c.inkFaint,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
            }}
          >
            Helper Token
          </span>
          <input
            aria-label="Helper Token"
            value={helperToken}
            onChange={(event) => setHelperTokenState(event.target.value)}
            placeholder="mk-..."
            style={{
              border: `1px solid ${c.inkHair}`,
              background: c.surfaceHi,
              color: c.ink,
              padding: "11px 12px",
              fontFamily: fontMono,
              fontSize: 12,
              outline: "none",
            }}
          />
        </label>

        <label style={{ display: "grid", gap: 8 }}>
          <span
            style={{
              fontFamily: fontMono,
              fontSize: 10,
              color: c.inkFaint,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
            }}
          >
            Workspace Path
          </span>
          <input
            aria-label="Helper Workspace Path"
            value={helperCwd}
            onChange={(event) => setHelperCwdState(event.target.value)}
            style={{
              border: `1px solid ${c.inkHair}`,
              background: c.surfaceHi,
              color: c.ink,
              padding: "11px 12px",
              fontFamily: fontMono,
              fontSize: 12,
              outline: "none",
            }}
          />
        </label>

        <label style={{ display: "grid", gap: 8 }}>
          <span
            style={{
              fontFamily: fontMono,
              fontSize: 10,
              color: c.inkFaint,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
            }}
          >
            Model
          </span>
          <input
            aria-label="Helper Model"
            value={helperModel}
            onChange={(event) => setHelperModelState(event.target.value)}
            style={{
              border: `1px solid ${c.inkHair}`,
              background: c.surfaceHi,
              color: c.ink,
              padding: "11px 12px",
              fontFamily: fontMono,
              fontSize: 12,
              outline: "none",
            }}
          />
        </label>

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={() => void checkHelper()}
            style={{
              border: `1px solid ${c.inkHairBold}`,
              background: c.surface,
              color: c.ink,
              padding: "8px 12px",
              fontSize: 12,
              cursor: "pointer",
            }}
          >
            檢查 helper
          </button>
          <button
            type="button"
            onClick={saveHelperSettings}
            style={{
              border: `1px solid ${c.vermLine}`,
              background: c.vermSoft,
              color: c.vermillion,
              padding: "8px 12px",
              fontSize: 12,
              cursor: "pointer",
            }}
          >
            儲存設定
          </button>
          <button
            type="button"
            onClick={() => void copyText(helperCommand, "Helper 啟動指令")}
            disabled={!canCopy}
            style={{
              border: `1px solid ${canCopy ? c.inkHairBold : c.inkHair}`,
              background: canCopy ? c.surface : c.paperWarm,
              color: canCopy ? c.ink : c.inkFaint,
              padding: "8px 12px",
              fontSize: 12,
              cursor: canCopy ? "pointer" : "not-allowed",
            }}
          >
            複製啟動指令
          </button>
        </div>

        <div
          style={{
            border: `1px solid ${c.inkHair}`,
            background: c.paperWarm,
            padding: "14px 16px",
          }}
        >
          <div
            style={{
              fontFamily: fontMono,
              fontSize: 10,
              color: c.inkFaint,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              marginBottom: 10,
            }}
          >
            啟動指令
          </div>
          <pre
            style={{
              margin: 0,
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              fontFamily: fontMono,
              fontSize: 11,
              lineHeight: 1.7,
              color: c.ink,
            }}
          >
            {helperCommand}
          </pre>
        </div>
      </div>
    </Dialog>
  );
}
