"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  streamCoworkChat,
  checkCoworkHelperHealth,
  cancelCoworkRequest,
  getDefaultHelperBaseUrl,
  getDefaultHelperToken,
  getDefaultHelperModel,
  getDefaultHelperCwd,
  type CoworkCapabilityCheck,
} from "@/lib/cowork-helper";
import type {
  CopilotChatStatus,
  CopilotEntryConfig,
  StructuredResult,
} from "@/lib/copilot/types";
import {
  nextCopilotStatus,
  getCopilotConversationKey,
  usesScopedResume,
} from "@/lib/copilot/state";
import {
  clearSessionStarted,
  clearSessionSnapshot,
  markSessionStarted,
  readFreshSessionStartedAt,
  readFreshSessionSnapshot,
  writeSessionSnapshot,
} from "@/lib/copilot/session";
import { buildCopilotPromptEnvelope } from "@/lib/copilot/envelope";
import { COWORK_MAX_TURNS } from "@/lib/cowork-knowledge";
import { parseStructuredResult } from "@/lib/copilot/structured-result";
import { parseStreamLine } from "@/lib/copilot/stream";

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export type ConnectorStatus = "checking" | "connected" | "disconnected";

export interface CopilotChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
}

export interface UseCopilotChatReturn {
  // State
  status: CopilotChatStatus;
  connectorStatus: ConnectorStatus;
  messages: CopilotChatMessage[];
  streamingText: string;
  structuredResult: StructuredResult | null;
  missingKeys: string[];
  capability: CoworkCapabilityCheck | null;
  lastError: string | null;

  // Actions
  send: (userInput: string) => Promise<void>;
  cancel: () => Promise<void>;
  retry: () => Promise<void>;
  apply: () => Promise<void>;
  reset: () => void;
  checkHealth: () => Promise<void>;
}

const STARTED_KEY_PREFIX = "zenos.copilot.started.";
const SNAPSHOT_KEY_PREFIX = "zenos.copilot.snapshot.";

function getStartedKey(conversationKey: string): string {
  return `${STARTED_KEY_PREFIX}${conversationKey}`;
}

function getSnapshotKey(conversationKey: string): string {
  return `${SNAPSHOT_KEY_PREFIX}${conversationKey}`;
}

interface CopilotSessionSnapshot {
  messages: CopilotChatMessage[];
  streamingText: string;
  structuredResult: StructuredResult | null;
  missingKeys: string[];
  lastError: string | null;
  lastSubmittedInput: string;
  status: CopilotChatStatus;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useCopilotChat(
  entry: CopilotEntryConfig | null
): UseCopilotChatReturn {
  const conversationKey = entry ? getCopilotConversationKey(entry) : null;
  const scopedResume = entry ? usesScopedResume(entry) : false;

  // Core chat state
  const [status, setStatus] = useState<CopilotChatStatus>("idle");
  const [connectorStatus, setConnectorStatus] =
    useState<ConnectorStatus>("checking");
  const [messages, setMessages] = useState<CopilotChatMessage[]>([]);
  const [streamingText, setStreamingText] = useState<string>("");
  const [structuredResult, setStructuredResult] =
    useState<StructuredResult | null>(null);
  const [missingKeys, setMissingKeys] = useState<string[]>([]);
  const [capability, setCapability] = useState<CoworkCapabilityCheck | null>(
    null
  );
  const [lastError, setLastError] = useState<string | null>(null);

  // Internal refs — survive re-renders without triggering them
  const abortControllerRef = useRef<AbortController | null>(null);
  const currentRequestIdRef = useRef<string | undefined>(undefined);
  const lastSubmittedInputRef = useRef<string>("");
  const isRunningRef = useRef<boolean>(false);
  const didHydrateRef = useRef<boolean>(false);
  const messagesRef = useRef<CopilotChatMessage[]>([]);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  const pushMessage = useCallback((
    role: CopilotChatMessage["role"],
    content: string
  ): void => {
    setMessages((prev) => [...prev, { role, content, timestamp: Date.now() }]);
  }, []);

  // ---------------------------------------------------------------------------
  // checkHealth
  // ---------------------------------------------------------------------------

  const checkHealth = useCallback(async (): Promise<void> => {
    setConnectorStatus("checking");
    const baseUrl = getDefaultHelperBaseUrl();
    const token = getDefaultHelperToken();
    try {
      const result = await checkCoworkHelperHealth(
        baseUrl,
        token,
        entry?.scope.workspace_id
      );
      if (result.capability) {
        setCapability(result.capability);
      }
      setConnectorStatus(result.ok ? "connected" : "disconnected");
    } catch {
      setConnectorStatus("disconnected");
    }
  }, [entry?.scope.workspace_id]);

  // Run health check on mount
  useEffect(() => {
    void checkHealth();
  }, [checkHealth]);

  useEffect(() => {
    abortControllerRef.current?.abort();
    currentRequestIdRef.current = undefined;
    isRunningRef.current = false;
    didHydrateRef.current = false;

    setStatus("idle");
    setConnectorStatus("checking");
    setStreamingText("");
    setStructuredResult(null);
    setMissingKeys([]);
    setCapability(null);
    setLastError(null);
    setMessages([]);
    lastSubmittedInputRef.current = "";

    if (!conversationKey || !scopedResume) return;

    const snapshot = readFreshSessionSnapshot<CopilotSessionSnapshot>(
      getSnapshotKey(conversationKey)
    );
    if (!snapshot) {
      didHydrateRef.current = true;
      return;
    }

    setMessages(snapshot.messages ?? []);
    setStreamingText(snapshot.streamingText ?? "");
    setStructuredResult(snapshot.structuredResult ?? null);
    setMissingKeys(snapshot.missingKeys ?? []);
    setLastError(snapshot.lastError ?? null);
    setStatus(
      snapshot.status === "loading" || snapshot.status === "streaming"
        ? "idle"
        : snapshot.status ?? "idle"
    );
    lastSubmittedInputRef.current = snapshot.lastSubmittedInput ?? "";
    didHydrateRef.current = true;
  }, [conversationKey, scopedResume]);

  useEffect(() => {
    if (!conversationKey || !scopedResume) return;
    if (!didHydrateRef.current) return;

    const hasState =
      messages.length > 0 ||
      Boolean(streamingText) ||
      Boolean(structuredResult) ||
      missingKeys.length > 0 ||
      Boolean(lastError) ||
      Boolean(lastSubmittedInputRef.current);

    if (!hasState) {
      clearSessionSnapshot(getSnapshotKey(conversationKey));
      return;
    }

    writeSessionSnapshot<CopilotSessionSnapshot>(getSnapshotKey(conversationKey), {
      messages,
      streamingText,
      structuredResult,
      missingKeys,
      lastError,
      lastSubmittedInput: lastSubmittedInputRef.current,
      status,
    });
  }, [
    conversationKey,
    lastError,
    messages,
    missingKeys,
    scopedResume,
    status,
    streamingText,
    structuredResult,
  ]);

  // ---------------------------------------------------------------------------
  // send
  // ---------------------------------------------------------------------------

  const send = useCallback(
    async (userInput: string): Promise<void> => {
      if (!entry) return;
      if (!conversationKey) return;
      if (isRunningRef.current) return;

      isRunningRef.current = true;
      lastSubmittedInputRef.current = userInput;

      const recentConversation = messagesRef.current.map((message) => ({
        role: message.role,
        content: message.content,
      }));

      if (userInput.trim()) {
        pushMessage("user", userInput);
      }
      setStatus(nextCopilotStatus("idle", "send")); // → "loading"
      setLastError(null);
      setStructuredResult(null);
      setMissingKeys([]);
      setStreamingText("");

      const baseUrl = getDefaultHelperBaseUrl();
      const token = getDefaultHelperToken();
      const model = getDefaultHelperModel();
      const cwd = getDefaultHelperCwd();

      // Determine mode: "continue" if scoped_resume and session already started
      const alreadyStarted =
        scopedResume &&
        conversationKey &&
        Boolean(readFreshSessionStartedAt(getStartedKey(conversationKey)));
      const mode: "start" | "continue" = alreadyStarted ? "continue" : "start";

      const prompt = buildCopilotPromptEnvelope(entry, userInput, recentConversation);

      const abortController = new AbortController();
      abortControllerRef.current = abortController;
      currentRequestIdRef.current = undefined;

      let collectedText = "";
      let didFallbackToStart = false;

      const runStream = async (streamMode: "start" | "continue"): Promise<void> => {
        collectedText = "";

        await streamCoworkChat({
          baseUrl,
          token,
          mode: streamMode,
          conversationId: conversationKey,
          prompt,
          model,
          cwd,
          maxTurns: COWORK_MAX_TURNS,
          signal: abortController.signal,
          onEvent: (event) => {
            switch (event.type) {
              case "message": {
                // Capture requestId from first message event if not yet captured
                if (event.requestId && !currentRequestIdRef.current) {
                  currentRequestIdRef.current = event.requestId;
                }
                const { delta, debug, strategy } = parseStreamLine(event.line);
                if (delta) {
                  if (strategy === "replace") {
                    collectedText = delta;
                    setStreamingText(delta);
                  } else {
                    collectedText += delta;
                    setStreamingText((prev) => prev + delta);
                  }
                  // Transition to "streaming" if still "loading"
                  setStatus((prev) =>
                    prev === "loading"
                      ? nextCopilotStatus(prev, "message")
                      : prev
                  );
                }
                if (debug) {
                  pushMessage("system", debug);
                }
                break;
              }

              case "capability_check": {
                setCapability(event.capability);
                break;
              }

              case "permission_request": {
                setStatus(nextCopilotStatus("streaming", "permission_request"));
                pushMessage(
                  "system",
                  `[Permission Request] Tool: ${event.request.toolName} (timeout: ${event.request.timeoutSeconds}s)`
                );
                break;
              }

              case "permission_result": {
                setStatus(nextCopilotStatus("awaiting-local-approval", "permission_result"));
                const outcome = event.result.approved ? "approved" : "denied";
                const reasonSuffix = event.result.reason
                  ? ` — ${event.result.reason}`
                  : "";
                pushMessage(
                  "system",
                  `[Permission Result] Tool: ${event.result.toolName} ${outcome}${reasonSuffix}`
                );
                break;
              }

              case "stderr": {
                if (event.requestId && !currentRequestIdRef.current) {
                  currentRequestIdRef.current = event.requestId;
                }
                if (event.text) {
                  pushMessage("system", `[stderr] ${event.text}`);
                }
                break;
              }

              case "done": {
                if (event.requestId && !currentRequestIdRef.current) {
                  currentRequestIdRef.current = event.requestId;
                }

                // Push completed assistant message
                if (collectedText) {
                  pushMessage("assistant", collectedText);
                }

                // Try to parse structured result
                let parsedResult: StructuredResult | null = null;
                let parsedMissing: string[] = [];

                if (entry.parse_structured_result) {
                  parsedResult = entry.parse_structured_result(collectedText);
                } else if (entry.write_targets && entry.write_targets.length > 0) {
                  const parsed = parseStructuredResult(collectedText, {
                    allowedTargets: entry.write_targets,
                  });
                  parsedResult = parsed.result;
                  parsedMissing = parsed.missingKeys;
                }

                if (parsedResult) {
                  setStructuredResult(parsedResult);
                  setMissingKeys(parsedMissing);
                  setStatus(nextCopilotStatus("streaming", "apply_available"));
                } else {
                  setStatus(nextCopilotStatus("streaming", "reset")); // → "idle"
                }

                // Clear streaming buffer
                setStreamingText("");
                break;
              }

              case "error": {
                setLastError(event.message);
                setStatus(nextCopilotStatus("streaming", "error"));
                pushMessage("system", `[Error] ${event.message}`);
                break;
              }
            }
          },
        });
      };

      try {
        try {
          await runStream(mode);
        } catch (err) {
          // If we tried "continue" and it failed with a session-not-found style
          // error, fall back to "start"
          if (
            mode === "continue" &&
            !didFallbackToStart &&
            err instanceof Error &&
            (err.message.includes("404") ||
              err.message.toLowerCase().includes("not found") ||
              err.message.toLowerCase().includes("session"))
          ) {
            didFallbackToStart = true;
            collectedText = "";
            setStreamingText("");
            await runStream("start");
          } else {
            throw err;
          }
        }

        // Mark the conversation as started so subsequent sends use "continue"
        if (scopedResume && conversationKey) {
          markSessionStarted(getStartedKey(conversationKey));
        }
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          // AbortError is handled by cancel() — don't overwrite the status
          return;
        }
        const message = err instanceof Error ? err.message : "Unknown error";
        setLastError(message);
        setStatus(nextCopilotStatus("streaming", "error"));
        pushMessage("system", `[Error] ${message}`);
      } finally {
        abortControllerRef.current = null;
        currentRequestIdRef.current = undefined;
        isRunningRef.current = false;
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [conversationKey, entry, pushMessage, scopedResume]
  );

  // ---------------------------------------------------------------------------
  // cancel
  // ---------------------------------------------------------------------------

  const cancel = useCallback(async (): Promise<void> => {
    // Abort the in-flight fetch first
    abortControllerRef.current?.abort();

    const requestId = currentRequestIdRef.current;
    const conversationId = entry ? getCopilotConversationKey(entry) : undefined;
    if (requestId || conversationId) {
      try {
        await cancelCoworkRequest({
          baseUrl: getDefaultHelperBaseUrl(),
          token: getDefaultHelperToken(),
          requestId,
          conversationId,
        });
      } catch {
        // Best-effort cancel — ignore errors
      }
    }

    isRunningRef.current = false;
    setStreamingText("");
    setStatus(nextCopilotStatus("streaming", "cancel")); // → "idle"
    pushMessage("system", "[Cancelled]");
  }, [entry, pushMessage]);

  // ---------------------------------------------------------------------------
  // retry
  // ---------------------------------------------------------------------------

  const retry = useCallback(async (): Promise<void> => {
    const lastInput = lastSubmittedInputRef.current;
    if (!lastInput) return;
    await send(lastInput);
  }, [send]);

  // ---------------------------------------------------------------------------
  // apply
  // ---------------------------------------------------------------------------

  const apply = useCallback(async (): Promise<void> => {
    if (!structuredResult || !entry?.on_apply) return;

    setStatus(nextCopilotStatus("apply-ready", "apply_start")); // → "applying"
    try {
      await entry.on_apply(structuredResult);
      setStatus(nextCopilotStatus("applying", "apply_done")); // → "idle"
      pushMessage("system", `[Applied] ${structuredResult.summary ?? structuredResult.target}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Apply failed";
      setLastError(message);
      setStatus(nextCopilotStatus("applying", "error")); // → "error"
      pushMessage("system", `[Apply Error] ${message}`);
    }
  }, [entry, structuredResult]);

  // ---------------------------------------------------------------------------
  // reset
  // ---------------------------------------------------------------------------

  const reset = useCallback((): void => {
    // Abort any running stream
    abortControllerRef.current?.abort();
    isRunningRef.current = false;

    setStatus(nextCopilotStatus("idle", "reset")); // → "idle"
    setStreamingText("");
    setStructuredResult(null);
    setMissingKeys([]);
    setLastError(null);
    setMessages([]);
    if (entry && usesScopedResume(entry)) {
      const activeConversationKey = getCopilotConversationKey(entry);
      clearSessionStarted(getStartedKey(activeConversationKey));
      clearSessionSnapshot(getSnapshotKey(activeConversationKey));
    }
  }, [entry]);

  // ---------------------------------------------------------------------------
  // Return
  // ---------------------------------------------------------------------------

  return {
    status,
    connectorStatus,
    messages,
    streamingText,
    structuredResult,
    missingKeys,
    capability,
    lastError,
    send,
    cancel,
    retry,
    apply,
    reset,
    checkHealth,
  };
}
