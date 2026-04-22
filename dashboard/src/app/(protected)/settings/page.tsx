"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { Section } from "@/components/zen/Section";
import { Icon, ICONS } from "@/components/zen/Icons";
import { useToast } from "@/components/zen/Toast";
import { useAuth } from "@/lib/auth";
import {
  checkGoogleWorkspaceConnectorHealth,
  getPreferences,
  updatePreferences,
} from "@/lib/api";
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
import { getStoredActiveWorkspaceId } from "@/lib/api-client";
import { resolveActiveWorkspace } from "@/lib/partner";
import { useInk } from "@/lib/zen-ink/tokens";
import {
  AGENT_PLATFORMS,
  buildHelperInstallAndStartCommand,
  canCopyAgentConfig,
  getMcpConfig,
  getMcpUrl,
  maskApiKey,
} from "@/lib/agent-config";

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

function formatContainersInput(containers?: string[]): string {
  if (!Array.isArray(containers)) return "";
  return containers.join("\n");
}

function parseContainersInput(raw: string): string[] {
  return Array.from(
    new Set(
      raw
        .split(/[\n,]+/)
        .map((value) => value.trim())
        .filter(Boolean),
    ),
  );
}

function statusMeta(
  status: HealthStatus,
  colors: ReturnType<typeof useInk>["c"],
  message?: string,
) {
  if (status === "connected") {
    return {
      dot: colors.jade,
      label: message || "running",
      tone: colors.jade,
    };
  }
  if (status === "checking") {
    return {
      dot: colors.ocher,
      label: "checking",
      tone: colors.ocher,
    };
  }
  if (status === "error") {
    return {
      dot: colors.vermillion,
      label: message || "error",
      tone: colors.vermillion,
    };
  }
  return {
    dot: colors.inkFaint,
    label: message || "idle",
    tone: colors.inkFaint,
  };
}

function MetricCard({
  label,
  value,
  sub,
  t,
}: {
  label: string;
  value: string;
  sub: string;
  t: ReturnType<typeof useInk>;
}) {
  const { c, fontHead, fontMono } = t;
  return (
    <div
      style={{
        background: c.surface,
        border: `1px solid ${c.inkHair}`,
        padding: "18px 20px",
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
        {label}
      </div>
      <div
        style={{
          fontFamily: fontHead,
          fontSize: 30,
          lineHeight: 1,
          color: c.ink,
          letterSpacing: "0.02em",
        }}
      >
        {value}
      </div>
      <div
        style={{
          marginTop: 8,
          fontFamily: fontMono,
          fontSize: 11,
          color: c.inkMuted,
          letterSpacing: "0.02em",
        }}
      >
        {sub}
      </div>
    </div>
  );
}

function Panel({
  title,
  eyebrow,
  subtitle,
  status,
  t,
  children,
  right,
}: {
  title: string;
  eyebrow: string;
  subtitle: string;
  status?: ReactNode;
  t: ReturnType<typeof useInk>;
  children: ReactNode;
  right?: ReactNode;
}) {
  const { c, fontHead, fontBody, fontMono } = t;
  return (
    <section
      style={{
        background: c.surface,
        border: `1px solid ${c.inkHair}`,
        borderRadius: 2,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "22px 24px 18px",
          borderBottom: `1px solid ${c.inkHair}`,
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 16,
        }}
      >
        <div>
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
            {eyebrow}
          </div>
          <div
            style={{
              fontFamily: fontHead,
              fontSize: 18,
              color: c.ink,
              letterSpacing: "0.03em",
            }}
          >
            {title}
          </div>
          <p
            style={{
              margin: "8px 0 0",
              fontFamily: fontBody,
              fontSize: 13,
              lineHeight: 1.7,
              color: c.inkMuted,
              maxWidth: 560,
            }}
          >
            {subtitle}
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {status}
          {right}
        </div>
      </div>
      <div style={{ padding: 24 }}>{children}</div>
    </section>
  );
}

function ActionButton({
  label,
  onClick,
  tone = "default",
  ariaLabel,
  disabled = false,
  t,
}: {
  label: string;
  onClick?: () => void;
  tone?: "default" | "accent";
  ariaLabel?: string;
  disabled?: boolean;
  t: ReturnType<typeof useInk>;
}) {
  const { c, fontMono } = t;
  const isAccent = tone === "accent";
  return (
    <button
      onClick={onClick}
      aria-label={ariaLabel || label}
      disabled={disabled}
      style={{
        background: isAccent ? c.vermillion : c.surfaceHi,
        color: isAccent ? c.surfaceHi : c.ink,
        border: `1px solid ${isAccent ? c.vermLine : c.inkHair}`,
        borderRadius: 2,
        padding: "10px 14px",
        fontFamily: fontMono,
        fontSize: 11,
        letterSpacing: "0.12em",
        textTransform: "uppercase",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
      }}
    >
      {label}
    </button>
  );
}

function DetailRow({
  label,
  value,
  mono = false,
  t,
}: {
  label: string;
  value: ReactNode;
  mono?: boolean;
  t: ReturnType<typeof useInk>;
}) {
  const { c, fontBody, fontMono } = t;
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "132px 1fr",
        gap: 16,
        padding: "12px 0",
        borderBottom: `1px solid ${c.inkHair}`,
      }}
    >
      <div
        style={{
          fontFamily: fontMono,
          fontSize: 10,
          color: c.inkFaint,
          letterSpacing: "0.18em",
          textTransform: "uppercase",
          paddingTop: 3,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: mono ? fontMono : fontBody,
          fontSize: mono ? 12 : 13,
          color: c.ink,
          lineHeight: 1.7,
          wordBreak: "break-all",
        }}
      >
        {value}
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const { partner, user } = useAuth();
  const { pushToast } = useToast();
  const t = useInk("light");
  const { c, fontBody, fontMono } = t;

  const [showApiKey, setShowApiKey] = useState(false);
  const [mcpHealth, setMcpHealth] = useState<HealthStatus>("idle");
  const [mcpLatency, setMcpLatency] = useState<number | null>(null);
  const [helperHealth, setHelperHealth] = useState<HealthStatus>("idle");
  const [helperHint, setHelperHint] = useState<string>("尚未檢查");

  const [helperBaseUrl, setHelperBaseUrlState] = useState(HELPER_DEFAULT_URL);
  const [helperToken, setHelperTokenState] = useState("");
  const [helperCwd, setHelperCwdState] = useState(DEFAULT_WORKSPACE);
  const [helperModel, setHelperModelState] = useState("sonnet");
  const [preferencesLoading, setPreferencesLoading] = useState(true);
  const [googleHealth, setGoogleHealth] = useState<HealthStatus>("idle");
  const [googleHint, setGoogleHint] = useState<string>("尚未檢查");
  const [googleBaseUrl, setGoogleBaseUrl] = useState("");
  const [googleToken, setGoogleToken] = useState("");
  const [googleContainers, setGoogleContainers] = useState("");

  useEffect(() => {
    setHelperBaseUrlState(getDefaultHelperBaseUrl());
    setHelperTokenState(getDefaultHelperToken());
    setHelperCwdState(getDefaultHelperCwd() || DEFAULT_WORKSPACE);
    setHelperModelState(getDefaultHelperModel());
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadPreferences() {
      if (!user) {
        if (!cancelled) setPreferencesLoading(false);
        return;
      }
      try {
        const token = await user.getIdToken();
        const prefs = await getPreferences(token);
        if (cancelled) return;
        const gw = prefs.googleWorkspace ?? {};
        setGoogleBaseUrl(gw.sidecar_base_url ?? "");
        setGoogleToken(gw.sidecar_token ?? "");
        setGoogleContainers(formatContainersInput(prefs.connectorScopes?.gdrive?.containers));
      } catch {
        if (!cancelled) {
          setGoogleHint("無法載入 Google Workspace connector 設定");
        }
      } finally {
        if (!cancelled) setPreferencesLoading(false);
      }
    }

    void loadPreferences();
    return () => {
      cancelled = true;
    };
  }, [user]);

  const apiKey = partner?.apiKey ?? "";
  const canCopy = canCopyAgentConfig(apiKey);
  const maskedApiKey = maskApiKey(apiKey);
  const displayApiKey = showApiKey ? apiKey : maskedApiKey;
  const workspace = resolveActiveWorkspace(partner);
  const canManageGoogleWorkspace = workspace.isHomeWorkspace && workspace.workspaceRole === "owner";

  const helperCommand = useMemo(
    () =>
      buildHelperLaunchCommand({
        apiKey,
        helperToken,
        cwd: helperCwd,
      }),
    [apiKey, helperToken, helperCwd],
  );

  const googleBadge = statusMeta(googleHealth, c, googleHint);

  async function runMcpCheck() {
    if (!apiKey) return;
    setMcpHealth("checking");
    setMcpLatency(null);
    const startedAt = Date.now();
    try {
      const res = await fetch(getMcpUrl({ useSSE: false }, apiKey), {
        method: "GET",
        signal: AbortSignal.timeout(8000),
      });
      setMcpLatency(Date.now() - startedAt);
      setMcpHealth(res.ok || res.status === 405 ? "connected" : "error");
    } catch {
      setMcpHealth("error");
      setMcpLatency(null);
    }
  }

  useEffect(() => {
    if (!apiKey) return;
    void runMcpCheck();
  }, [apiKey]);

  async function copyText(text: string, label: string) {
    await navigator.clipboard.writeText(text);
    pushToast({
      tone: "success",
      title: `${label} 已複製`,
      description: "可以直接貼到對應位置。",
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
      description: "Marketing / Clients 的 AI rail 會讀取這組本機設定。",
    });
  }

  async function checkHelper() {
    setHelperHealth("checking");
    setHelperHint("正在檢查本機 helper");
    const targetWorkspaceId =
      getStoredActiveWorkspaceId() || partner?.activeWorkspaceId || partner?.homeWorkspaceId || undefined;
    const result = await checkCoworkHelperHealth(helperBaseUrl, helperToken, targetWorkspaceId);
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
    setHelperHint(result.workspaceProbe?.message || result.message || "helper unavailable");
  }

  async function saveGoogleWorkspaceSettings() {
    if (!user) return;
    try {
      const token = await user.getIdToken();
      const containers = parseContainersInput(googleContainers);
      const prefs = await updatePreferences(token, {
        googleWorkspace: {
          sidecar_base_url: googleBaseUrl.trim(),
          sidecar_token: googleToken.trim(),
          principal_mode: "partner_email",
        },
        connectorScopes: {
          gdrive: {
            containers,
          },
        },
      });
      setGoogleBaseUrl(prefs.googleWorkspace?.sidecar_base_url ?? "");
      setGoogleToken(prefs.googleWorkspace?.sidecar_token ?? "");
      setGoogleContainers(formatContainersInput(prefs.connectorScopes?.gdrive?.containers));
      pushToast({
        tone: "success",
        title: "Google Workspace connector 設定已儲存",
        description: "server 端 live retrieval 會讀這組 sidecar 與 gdrive allowlist。",
      });
    } catch {
      pushToast({
        tone: "error",
        title: "儲存失敗",
        description: "無法保存 Google Workspace connector 設定。",
      });
    }
  }

  async function checkGoogleWorkspaceHealth() {
    if (!user) return;
    setGoogleHealth("checking");
    setGoogleHint("正在檢查 Google Workspace connector");
    try {
      const token = await user.getIdToken();
      const result = await checkGoogleWorkspaceConnectorHealth(token, {
        sidecar_base_url: googleBaseUrl.trim(),
        sidecar_token: googleToken.trim(),
      });
      if (result.ok) {
        setGoogleHealth("connected");
        setGoogleHint(result.message || "connector 已連線");
        return;
      }
      setGoogleHealth("error");
      setGoogleHint(result.message || "connector unavailable");
    } catch {
      setGoogleHealth("error");
      setGoogleHint("connector unavailable");
    }
  }

  const mcpBadge = statusMeta(
    mcpHealth,
    c,
    mcpHealth === "connected" && mcpLatency != null ? `${mcpLatency} ms` : undefined,
  );
  const helperBadge = statusMeta(helperHealth, c, helperHint);

  return (
    <div style={{ padding: "40px 48px 60px", maxWidth: 1480 }}>
      <Section
        t={t}
        eyebrow="Workspace · Preferences"
        title="Settings"
        en="Control Room"
        subtitle="這一頁按用途整理設定：API key、外部 agent 的 MCP、Dashboard AI 的 Helper、以及 connector / diagnostics。進階 manifest / skill 細節仍看 Agent 頁。"
        right={
          <Link
            href="/agent"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              color: c.ink,
              textDecoration: "none",
              border: `1px solid ${c.inkHair}`,
              background: c.surface,
              padding: "10px 14px",
              borderRadius: 2,
              fontFamily: fontMono,
              fontSize: 11,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
            }}
          >
            深入 Agent 設定
            <Icon d={ICONS.arrow} size={13} />
          </Link>
        }
      />

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 1,
          background: c.inkHair,
          border: `1px solid ${c.inkHair}`,
          marginBottom: 28,
        }}
      >
        <MetricCard
          label="Workspace"
          value={workspace.isHomeWorkspace ? "Home" : "Shared"}
          sub={workspace.workspaceRole === "owner" ? "owner scope" : `${workspace.workspaceRole} scope`}
          t={t}
        />
        <MetricCard
          label="MCP"
          value={mcpHealth === "connected" ? "1" : "—"}
          sub={mcpHealth === "connected" ? "hosted endpoint ready" : "needs check"}
          t={t}
        />
        <MetricCard
          label="Helper"
          value={helperHealth === "connected" ? "local" : "off"}
          sub={helperHealth === "connected" ? helperHint : "dashboard AI relay"}
          t={t}
        />
        <MetricCard
          label="GWorkspace"
          value={googleHealth === "connected" ? "live" : preferencesLoading ? "…" : "off"}
          sub={googleHealth === "connected" ? googleHint : "per-user sidecar"}
          t={t}
        />
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.1fr) minmax(340px, 0.9fr)",
          gap: 22,
          alignItems: "start",
        }}
      >
        <div style={{ display: "grid", gap: 22 }}>
          <Panel
            eyebrow="Access / API Key"
            title="API key 與外部 agent 設定"
            subtitle="先確認這把 key。下面所有 MCP 設定與 Helper 啟動指令，都會直接帶入同一把 user API key。"
            t={t}
            status={
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  color: mcpBadge.tone,
                }}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: mcpBadge.dot,
                  }}
                />
                <span
                  style={{
                    fontFamily: fontMono,
                    fontSize: 10,
                    letterSpacing: "0.14em",
                    textTransform: "uppercase",
                  }}
                >
                  {mcpBadge.label}
                </span>
              </div>
            }
            right={<ActionButton label="重新檢查" ariaLabel="重新檢查 MCP" onClick={() => void runMcpCheck()} t={t} />}
          >
            <div style={{ display: "grid", gap: 0 }}>
              <DetailRow label="API key" value={displayApiKey} mono t={t} />
              <DetailRow label="HTTP" value={getMcpUrl({ useSSE: false }, apiKey)} mono t={t} />
              <DetailRow label="SSE" value={getMcpUrl({ useSSE: true }, apiKey)} mono t={t} />
              <DetailRow
                label="用途"
                value="外部 agent 要接 ZenOS 時，用這一組 hosted MCP 設定。Dashboard 內建 AI 不走這條。"
                t={t}
              />
            </div>

            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 10,
                marginTop: 18,
              }}
            >
              <ActionButton
                label={showApiKey ? "隱藏 key" : "顯示 key"}
                onClick={() => setShowApiKey((value) => !value)}
                t={t}
              />
              <ActionButton
                label="複製 HTTP 設定"
                onClick={() => void copyText(getMcpConfig(AGENT_PLATFORMS[0], apiKey), "HTTP MCP 設定")}
                tone="accent"
                disabled={!canCopy}
                t={t}
              />
              <ActionButton
                label="複製 SSE 設定"
                onClick={() =>
                  void copyText(
                    getMcpConfig(
                      AGENT_PLATFORMS.find((platform) => platform.useSSE) || AGENT_PLATFORMS[0],
                      apiKey,
                    ),
                    "SSE MCP 設定",
                  )
                }
                disabled={!canCopy}
                t={t}
              />
            </div>

            <div
              style={{
                marginTop: 22,
                padding: "16px 18px",
                background: c.paperWarm,
                border: `1px solid ${c.inkHair}`,
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
                設定說明
              </div>
              <div
                style={{
                  display: "grid",
                  gap: 10,
                  fontFamily: fontBody,
                  fontSize: 13,
                  color: c.inkMuted,
                  lineHeight: 1.7,
                }}
              >
                <div>1. 外部 agent：先複製 MCP 設定，再在 agent 內跑 <code style={{ fontFamily: fontMono }}>/zenos-setup</code>。</div>
                <div>2. Dashboard 內建 AI：看右側的 Helper，不要改這組 MCP URL。</div>
                <div>3. 如果 API key 還沒載入完成，複製按鈕會先停用，避免你拿到不能用的 placeholder。</div>
              </div>
            </div>
          </Panel>

          <Panel
            eyebrow="分類導引"
            title="設定分成兩條線"
            subtitle="外部 agent 用 MCP。Dashboard 內建 AI 用 Helper。這兩條線的故障排查也不同。"
            t={t}
          >
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
                gap: 16,
              }}
            >
              {[
                {
                  title: "MCP",
                  icon: ICONS.spark,
                  points: [
                    "讓 Claude Code / ChatGPT / Codex / Gemini 看得到 ZenOS 資料。",
                    "主要影響 setup、capture、task、search、get 這些 tool 流程。",
                    "一個 AI 工具接一次，之後多半不用再碰。",
                  ],
                },
                {
                  title: "Helper",
                  icon: ICONS.link,
                  points: [
                    "讓 dashboard 內的 Marketing / Clients AI rail 把操作代理到本機 CLI。",
                    "主要影響討論、briefing、debrief、apply 這些頁內 AI 功能。",
                    "helper 沒開時，頁面會退化成說明或 repair guidance。",
                  ],
                },
              ].map((item) => (
                <div
                  key={item.title}
                  style={{
                    background: c.surfaceHi,
                    border: `1px solid ${c.inkHair}`,
                    padding: 18,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      marginBottom: 12,
                      color: c.ink,
                    }}
                  >
                    <Icon d={item.icon} size={15} />
                    <div
                      style={{
                        fontFamily: t.fontHead,
                        fontSize: 16,
                        letterSpacing: "0.03em",
                      }}
                    >
                      {item.title}
                    </div>
                  </div>
                  <div style={{ display: "grid", gap: 8 }}>
                    {item.points.map((point) => (
                      <div
                        key={point}
                        style={{
                          display: "grid",
                          gridTemplateColumns: "14px 1fr",
                          gap: 8,
                          alignItems: "start",
                          fontFamily: fontBody,
                          fontSize: 13,
                          color: c.inkMuted,
                          lineHeight: 1.65,
                        }}
                      >
                        <span style={{ color: c.vermillion }}>•</span>
                        <span>{point}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        <div style={{ display: "grid", gap: 22 }}>
          <Panel
            eyebrow="Dashboard AI / Helper"
            title="Local helper"
            subtitle="這是給 dashboard 內建 AI 功能用的本機代理。複製後可直接在新機器執行，已自動帶入你的 API key。"
            t={t}
            status={
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  color: helperBadge.tone,
                }}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: helperBadge.dot,
                  }}
                />
                <span
                  style={{
                    fontFamily: fontMono,
                    fontSize: 10,
                    letterSpacing: "0.14em",
                    textTransform: "uppercase",
                  }}
                >
                  {helperBadge.label}
                </span>
              </div>
            }
            right={<ActionButton label="檢查 helper" ariaLabel="檢查 Helper 連線" onClick={() => void checkHelper()} t={t} />}
          >
            <label style={{ display: "grid", gap: 8, marginBottom: 16 }}>
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

            <label style={{ display: "grid", gap: 8, marginBottom: 16 }}>
              <span
                style={{
                  fontFamily: fontMono,
                  fontSize: 10,
                  color: c.inkFaint,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                }}
              >
                Local helper token
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

            <label style={{ display: "grid", gap: 8, marginBottom: 16 }}>
              <span
                style={{
                  fontFamily: fontMono,
                  fontSize: 10,
                  color: c.inkFaint,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                }}
              >
                Workspace path
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

            <label style={{ display: "grid", gap: 8, marginBottom: 18 }}>
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

            <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 18 }}>
              <ActionButton label="儲存本機設定" ariaLabel="儲存 Helper 設定" tone="accent" onClick={saveHelperSettings} t={t} />
              <ActionButton
                label="複製啟動指令"
                onClick={() => void copyText(helperCommand, "Helper 啟動指令")}
                disabled={!canCopy}
                t={t}
              />
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
            {!canCopy && (
              <div
                style={{
                  marginTop: 12,
                  fontFamily: fontBody,
                  fontSize: 12,
                  color: c.ocher,
                  lineHeight: 1.6,
                }}
              >
                尚未取得 API key，暫時不能產生可直接執行的 helper 指令。
              </div>
            )}
          </Panel>

          <Panel
            eyebrow="Google Workspace"
            title="Per-user live retrieval"
            subtitle="這條線給企業文件治理用。ZenOS 只存 metadata / summary；真的讀全文時，server 會改走客戶環境內的 Google Workspace sidecar，並帶當前使用者身份去 live fetch。"
            t={t}
            status={
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  color: googleBadge.tone,
                }}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: googleBadge.dot,
                  }}
                />
                <span
                  style={{
                    fontFamily: fontMono,
                    fontSize: 10,
                    letterSpacing: "0.14em",
                    textTransform: "uppercase",
                  }}
                >
                  {googleBadge.label}
                </span>
              </div>
            }
            right={<ActionButton label="檢查 Connector" ariaLabel="檢查 Google Workspace Connector" onClick={() => void checkGoogleWorkspaceHealth()} t={t} />}
          >
            <label style={{ display: "grid", gap: 8, marginBottom: 16 }}>
              <span
                style={{
                  fontFamily: fontMono,
                  fontSize: 10,
                  color: c.inkFaint,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                }}
              >
                Sidecar base URL
              </span>
              <input
                aria-label="Google Workspace Sidecar Base URL"
                value={googleBaseUrl}
                onChange={(event) => setGoogleBaseUrl(event.target.value)}
                placeholder="http://google-workspace-sidecar.internal:8787"
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

            <label style={{ display: "grid", gap: 8, marginBottom: 16 }}>
              <span
                style={{
                  fontFamily: fontMono,
                  fontSize: 10,
                  color: c.inkFaint,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                }}
              >
                Sidecar token
              </span>
              <input
                aria-label="Google Workspace Sidecar Token"
                value={googleToken}
                onChange={(event) => setGoogleToken(event.target.value)}
                placeholder="gwsc-..."
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

            <label style={{ display: "grid", gap: 8, marginBottom: 16 }}>
              <span
                style={{
                  fontFamily: fontMono,
                  fontSize: 10,
                  color: c.inkFaint,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                }}
              >
                Allowed containers
              </span>
              <textarea
                aria-label="Google Workspace Allowed Containers"
                value={googleContainers}
                onChange={(event) => setGoogleContainers(event.target.value)}
                placeholder={"drive:finance\nfolder:roadmap"}
                rows={4}
                style={{
                  border: `1px solid ${c.inkHair}`,
                  background: c.surfaceHi,
                  color: c.ink,
                  padding: "11px 12px",
                  fontFamily: fontMono,
                  fontSize: 12,
                  outline: "none",
                  resize: "vertical",
                }}
              />
            </label>

            <div style={{ display: "grid", gap: 10, marginBottom: 18 }}>
              <DetailRow
                label="Principal"
                value="固定使用當前 caller 的 partner email。ZenOS 不會把 A 用自己權限抓到的全文變成 workspace 共享 cache。"
                t={t}
              />
              <DetailRow
                label="可編輯者"
                value={canManageGoogleWorkspace ? "目前 workspace owner 可管理這組設定。" : "你目前不是 home workspace owner；建議由 owner 維護這組設定。"}
                t={t}
              />
            </div>

            <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 18 }}>
              <ActionButton
                label={preferencesLoading ? "載入中..." : "儲存 Connector 設定"}
                ariaLabel="儲存 Google Workspace Connector 設定"
                tone="accent"
                onClick={() => void saveGoogleWorkspaceSettings()}
                t={t}
              />
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
                設定步驟
              </div>
              <div
                style={{
                  display: "grid",
                  gap: 8,
                  fontFamily: fontBody,
                  fontSize: 13,
                  color: c.inkMuted,
                  lineHeight: 1.7,
                }}
              >
                <div>1. 在客戶環境內部署 Google Workspace sidecar，確保 ZenOS server 可以連到它。</div>
                <div>2. 讓每位公司成員先在 sidecar / CLI 內用自己的公司 Google 帳號完成綁定。</div>
                <div>3. 在這裡填入 sidecar URL、token，並限制允許的 Shared Drive / folder container。</div>
                <div>4. 點「檢查 Connector」確認 health 正常後，`read_source(full)` 才會走 per-user live retrieval。</div>
              </div>
            </div>
          </Panel>

          <Panel
            eyebrow="Repair Notes"
            title="故障排查"
            subtitle="這裡只放最常見的判斷點，讓你先知道該改哪條線。"
            t={t}
          >
            <div style={{ display: "grid", gap: 12 }}>
              {[
                "外部 agent 讀不到 task / entity / document：先看 MCP URL、API key、/zenos-setup。",
                "Marketing / Clients 裡的 AI rail 打不開或只剩 repair guidance：先看 helper 有沒有啟動。",
                "helper 檢查失敗但 MCP 正常：通常是本機 `server.mjs` 沒跑，或 token / base URL 不一致。",
                "helper 正常但頁內沒有資料上下文：再回頭查 MCP capability / skills 載入狀態。",
              ].map((item) => (
                <div
                  key={item}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "16px 1fr",
                    gap: 10,
                    fontFamily: fontBody,
                    fontSize: 13,
                    color: c.inkMuted,
                    lineHeight: 1.7,
                  }}
                >
                  <span style={{ color: c.vermillion }}>→</span>
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
