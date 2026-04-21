import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cancelCoworkRequest,
  checkCoworkHelperHealth,
  streamCoworkChat,
} from "@/lib/cowork-helper";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("checkCoworkHelperHealth", () => {
  it("returns ok=true and parses workspace probe when helper health endpoint responds 200", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue({
          status: "ok",
          capability: {
            mcp_ok: true,
            skills_loaded: ["/marketing-plan"],
            redaction_rules_version: "2026-04-14",
          },
          workspace_probe: {
            ok: true,
            workspace_id: "ws-active",
            workspace_name: "Barry Workspace",
            available_workspaces: [{ id: "ws-active", name: "Barry Workspace" }],
          },
        }),
      })
    );

    const result = await checkCoworkHelperHealth("http://127.0.0.1:4317", "mk-token", "ws-active");
    expect(result.ok).toBe(true);
    expect(result.status).toBe("ok");
    expect(result.capability).toEqual({
      mcpOk: true,
      skillsLoaded: ["/marketing-plan"],
      missingSkills: [],
      allowedTools: [],
      redactionRulesVersion: "2026-04-14",
    });
    expect(result.workspaceProbe).toEqual({
      ok: true,
      message: undefined,
      partnerId: undefined,
      partnerEmail: undefined,
      workspaceId: "ws-active",
      workspaceName: "Barry Workspace",
      availableWorkspaces: [{ id: "ws-active", name: "Barry Workspace" }],
    });
    const [url, options] = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit & { targetAddressSpace?: string }];
    expect(url).toBe("http://127.0.0.1:4317/health?workspace_id=ws-active");
    expect((options.headers as Record<string, string>)["X-Local-Helper-Token"]).toBe("mk-token");
    expect(options.targetAddressSpace).toBe("loopback");
  });
});

describe("streamCoworkChat", () => {
  it("parses SSE helper events", async () => {
    const encoder = new TextEncoder();
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          encoder.encode(
            'event: capability_check\ndata: {"mcp_ok":true,"skills_loaded":["/marketing-plan"],"missing_skills":[]}\n\n'
          )
        );
        controller.enqueue(
          encoder.encode(
            'event: permission_request\ndata: {"tool_name":"Bash","timeout_seconds":60}\n\n'
          )
        );
        controller.enqueue(
          encoder.encode(
            'event: message\ndata: {"requestId":"req-1","line":"{\\"text\\":\\"hello\\"}"}\n\n'
          )
        );
        controller.enqueue(
          encoder.encode(
            'event: permission_result\ndata: {"tool_name":"Bash","approved":false,"reason":"timeout"}\n\n'
          )
        );
        controller.enqueue(
          encoder.encode('event: done\ndata: {"requestId":"req-1","code":0}\n\n')
        );
        controller.close();
      },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        body,
      })
    );

    const events: Array<string> = [];
    await streamCoworkChat({
      baseUrl: "http://127.0.0.1:4317",
      mode: "start",
      conversationId: "conv-1",
      prompt: "hello",
      onEvent: (event) => events.push(event.type),
    });

    expect(events).toEqual([
      "capability_check",
      "permission_request",
      "message",
      "permission_result",
      "done",
    ]);
  });

  it("sends selected model in request payload", async () => {
    const encoder = new TextEncoder();
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          encoder.encode('event: done\ndata: {"requestId":"req-1","code":0}\n\n')
        );
        controller.close();
      },
    });

    const fakeFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body,
    });
    vi.stubGlobal("fetch", fakeFetch);

    await streamCoworkChat({
      baseUrl: "http://127.0.0.1:4317",
      mode: "start",
      conversationId: "conv-2",
      prompt: "hello",
      model: "sonnet",
      onEvent: () => {},
    });

    const [, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    const payload = JSON.parse(String(options.body)) as Record<string, string>;
    expect(payload.model).toBe("sonnet");
    expect((options as RequestInit & { targetAddressSpace?: string }).targetAddressSpace).toBe("loopback");
  });
});

describe("cancelCoworkRequest", () => {
  it("posts requestId to cancel endpoint", async () => {
    const fakeFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ status: "ok" }),
    });
    vi.stubGlobal("fetch", fakeFetch);

    await cancelCoworkRequest({
      baseUrl: "http://127.0.0.1:4317",
      requestId: "req-1",
    });

    const [url, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:4317/v1/chat/cancel");
    expect(options.method).toBe("POST");
    expect(JSON.parse(String(options.body))).toEqual({ requestId: "req-1" });
    expect((options as RequestInit & { targetAddressSpace?: string }).targetAddressSpace).toBe("loopback");
  });

  it("can cancel by conversationId before the helper emits a requestId", async () => {
    const fakeFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ status: "ok" }),
    });
    vi.stubGlobal("fetch", fakeFetch);

    await cancelCoworkRequest({
      baseUrl: "http://127.0.0.1:4317",
      conversationId: "conv-2",
    });

    const [url, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:4317/v1/chat/cancel");
    expect(options.method).toBe("POST");
    expect(JSON.parse(String(options.body))).toEqual({ conversationId: "conv-2" });
    expect((options as RequestInit & { targetAddressSpace?: string }).targetAddressSpace).toBe("loopback");
  });
});
