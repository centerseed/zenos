import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor, within } from "@testing-library/react";
import type { Entity, QualitySignals } from "@/types";

// Mock Radix Sheet — renders children without portal behavior
vi.mock("@/components/ui/sheet", () => ({
  Sheet: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SheetContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SheetHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SheetTitle: ({ children }: { children: React.ReactNode }) => <h2>{children}</h2>,
  SheetDescription: ({ children }: { children: React.ReactNode }) => <p>{children}</p>,
}));

// Mock Badge to render as a span
vi.mock("@/components/ui/badge", () => ({
  Badge: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <span className={className}>{children}</span>
  ),
}));

vi.mock("@/lib/constants", () => ({
  NODE_TYPE_COLORS: { product: "#6366F1", module: "#8B5CF6" },
  NODE_TYPE_LABELS: { product: "專案", module: "模組" },
}));

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

const authState = {
  user: null as null | { getIdToken: () => Promise<string> },
  partner: null as null | { isAdmin: boolean },
};

const updateEntityVisibilityMock = vi.fn();
const getPartnersMock = vi.fn();
const getDepartmentsMock = vi.fn();

vi.mock("@/lib/auth", () => ({
  useAuth: () => authState,
}));

vi.mock("@/lib/api", () => ({
  updateEntityVisibility: (...args: unknown[]) => updateEntityVisibilityMock(...args),
  getPartners: (...args: unknown[]) => getPartnersMock(...args),
  getDepartments: (...args: unknown[]) => getDepartmentsMock(...args),
}));

import NodeDetailSheet from "@/components/NodeDetailSheet";

afterEach(cleanup);

beforeEach(() => {
  authState.user = null;
  authState.partner = null;
  updateEntityVisibilityMock.mockReset();
  getPartnersMock.mockReset();
  getDepartmentsMock.mockReset();
});

function makeEntity(overrides: Partial<Entity> = {}): Entity {
  return {
    id: "entity-1",
    name: "Auth Module",
    type: "module",
    summary: "Handles authentication for the platform",
    tags: { what: "module", why: "auth", how: "JWT", who: "engineers" },
    status: "active",
    parentId: null,
    details: null,
    confirmedByUser: true,
    owner: null,
    sources: [],
    visibility: "public",
    lastReviewedAt: null,
    createdAt: new Date(),
    updatedAt: new Date(),
    ...overrides,
  };
}

const defaultProps = {
  entity: makeEntity(),
  relationships: [],
  blindspots: [],
  entities: [],
  tasks: [],
  onClose: vi.fn(),
};

describe("NodeDetailSheet — quality signal badges", () => {
  it("shows no quality badges when qualitySignals is not provided", () => {
    render(<NodeDetailSheet {...defaultProps} />);
    expect(screen.queryByText("少被引用")).toBeNull();
    expect(screen.queryByText("摘要待改善")).toBeNull();
  });

  it("shows no quality badges when entity is not in any signal list", () => {
    const qualitySignals: QualitySignals = { search_unused: [], summary_poor: [] };
    render(<NodeDetailSheet {...defaultProps} qualitySignals={qualitySignals} />);
    expect(screen.queryByText("少被引用")).toBeNull();
    expect(screen.queryByText("摘要待改善")).toBeNull();
  });

  it("shows '少被引用' badge when entity appears in search_unused signals", () => {
    const qualitySignals: QualitySignals = {
      search_unused: [
        {
          entity_id: "entity-1",
          entity_name: "Auth Module",
          search_count: 10,
          get_count: 1,
          unused_ratio: 0.9,
          flagged: true,
        },
      ],
      summary_poor: [],
    };
    render(<NodeDetailSheet {...defaultProps} qualitySignals={qualitySignals} />);
    expect(screen.getByText("少被引用")).toBeDefined();
    expect(screen.queryByText("摘要待改善")).toBeNull();
  });

  it("shows '摘要待改善' badge when entity appears in summary_poor signals", () => {
    const qualitySignals: QualitySignals = {
      search_unused: [],
      summary_poor: [
        {
          entity_id: "entity-1",
          entity_name: "Auth Module",
          quality_score: "poor",
          has_technical_keywords: false,
          has_challenge_context: false,
          is_too_generic: true,
          marketing_ratio: 0.0,
        },
      ],
    };
    render(<NodeDetailSheet {...defaultProps} qualitySignals={qualitySignals} />);
    expect(screen.getByText("摘要待改善")).toBeDefined();
    expect(screen.queryByText("少被引用")).toBeNull();
  });

  it("shows both badges when entity is in both signal lists", () => {
    const qualitySignals: QualitySignals = {
      search_unused: [
        {
          entity_id: "entity-1",
          entity_name: "Auth Module",
          search_count: 5,
          get_count: 0,
          unused_ratio: 1.0,
          flagged: true,
        },
      ],
      summary_poor: [
        {
          entity_id: "entity-1",
          entity_name: "Auth Module",
          quality_score: "poor",
          has_technical_keywords: false,
          has_challenge_context: false,
          is_too_generic: true,
          marketing_ratio: 0.0,
        },
      ],
    };
    render(<NodeDetailSheet {...defaultProps} qualitySignals={qualitySignals} />);
    expect(screen.getByText("少被引用")).toBeDefined();
    expect(screen.getByText("摘要待改善")).toBeDefined();
  });

  it("does not show badges for a different entity's signals", () => {
    const qualitySignals: QualitySignals = {
      search_unused: [
        {
          entity_id: "other-entity",
          entity_name: "Other Module",
          search_count: 10,
          get_count: 1,
          unused_ratio: 0.9,
          flagged: true,
        },
      ],
      summary_poor: [
        {
          entity_id: "other-entity",
          entity_name: "Other Module",
          quality_score: "poor",
          has_technical_keywords: false,
          has_challenge_context: false,
          is_too_generic: true,
          marketing_ratio: 0.0,
        },
      ],
    };
    render(<NodeDetailSheet {...defaultProps} qualitySignals={qualitySignals} />);
    expect(screen.queryByText("少被引用")).toBeNull();
    expect(screen.queryByText("摘要待改善")).toBeNull();
  });
});

describe("NodeDetailSheet — External Sources label fallback", () => {
  it("shows meaningful label when label differs from type", () => {
    const entity = makeEntity({
      sources: [{ uri: "https://github.com/org/repo/blob/main/CLAUDE.md", label: "CLAUDE.md Setup Guide", type: "github" }],
    });
    render(<NodeDetailSheet {...defaultProps} entity={entity} />);
    expect(screen.getByText("CLAUDE.md Setup Guide")).toBeDefined();
  });

  it("extracts filename from URI when label equals type", () => {
    const entity = makeEntity({
      sources: [{ uri: "https://github.com/org/repo/blob/main/README.md", label: "github", type: "github" }],
    });
    render(<NodeDetailSheet {...defaultProps} entity={entity} />);
    expect(screen.getByText("README.md")).toBeDefined();
    expect(screen.queryByText("github")).toBeNull();
  });

  it("shows full URI when label equals type and URI is not a valid URL", () => {
    const entity = makeEntity({
      sources: [{ uri: "not-a-valid-url", label: "github", type: "github" }],
    });
    render(<NodeDetailSheet {...defaultProps} entity={entity} />);
    expect(screen.getByText("not-a-valid-url")).toBeDefined();
  });

  it("shows last path segment when URI has nested path and label equals type", () => {
    const entity = makeEntity({
      sources: [{ uri: "https://github.com/org/repo/blob/main/docs/adr-001.md", label: "github", type: "github" }],
    });
    render(<NodeDetailSheet {...defaultProps} entity={entity} />);
    expect(screen.getByText("adr-001.md")).toBeDefined();
  });
});

describe("NodeDetailSheet — document reader link", () => {
  it("renders Reader link with encoded query docId for child SPEC docs", () => {
    const childSpec = makeEntity({
      id: "doc spec/1",
      name: "SPEC-Document-Delivery",
      type: "document",
      parentId: "entity-1",
      docRole: "single",
    });

    render(
      <NodeDetailSheet
        {...defaultProps}
        entities={[childSpec]}
      />
    );

    const readerLink = screen.getByRole("link", { name: "Reader" });
    expect(readerLink).toHaveAttribute("href", "/docs?docId=doc%20spec%2F1");
  });
});

describe("NodeDetailSheet — doc bundle highlights", () => {
  it("shows bundle highlights for a document entity", () => {
    const entity = makeEntity({
      type: "document",
      docRole: "index",
      sources: [{ uri: "https://github.com/org/repo/blob/main/docs/spec.md", label: "SPEC", type: "github", source_id: "src-1" }],
      bundleHighlights: [{
        source_id: "src-1",
        headline: "這是 onboarding flow 的 SSOT",
        reason_to_read: "先看這份就知道完整流程",
        priority: "primary",
      }],
    });
    render(<NodeDetailSheet {...defaultProps} entity={entity} />);
    expect(screen.getByText("What To Read First")).toBeInTheDocument();
    expect(screen.getByText("這是 onboarding flow 的 SSOT")).toBeInTheDocument();
    expect(screen.getByText("先讀這份")).toBeInTheDocument();
  });

  it("shows doc bundle cards on an L2 entity", () => {
    const parent = makeEntity();
    const childDoc = makeEntity({
      id: "doc-1",
      parentId: "entity-1",
      type: "document",
      name: "Dashboard Onboarding Bundle",
      docRole: "index",
      summary: "Onboarding-related documents",
      sources: [{ uri: "https://github.com/org/repo/blob/main/docs/spec.md", label: "SPEC", type: "github", source_id: "src-1" }],
      bundleHighlights: [{
        source_id: "src-1",
        headline: "先看這份規格",
        reason_to_read: "它定義了流程與 AC",
        priority: "primary",
      }],
    });
    render(<NodeDetailSheet {...defaultProps} entity={parent} entities={[childDoc]} />);
    expect(screen.getByText("Doc Bundles")).toBeInTheDocument();
    expect(screen.getByText("Dashboard Onboarding Bundle")).toBeInTheDocument();
    expect(screen.getByText("先看這份規格")).toBeInTheDocument();
  });
});

describe("NodeDetailSheet — permission editor", () => {
  it("renders selectable permission options for admins and saves normalized arrays", async () => {
    authState.user = {
      getIdToken: vi.fn().mockResolvedValue("token-123"),
    };
    authState.partner = { isAdmin: true };
    getPartnersMock.mockResolvedValue([
      {
        id: "partner-1",
        email: "alice@example.com",
        displayName: "Alice",
        apiKey: "key", // pragma: allowlist secret
        authorizedEntityIds: [],
        isAdmin: false,
        status: "active",
        roles: ["engineering"],
        department: "finance",
        invitedBy: null,
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    ]);
    getDepartmentsMock.mockResolvedValue(["finance", "hr"]);
    updateEntityVisibilityMock.mockResolvedValue(undefined);

    render(<NodeDetailSheet {...defaultProps} entity={makeEntity({ visibility: "restricted" })} />);

    fireEvent.click(screen.getByText("Edit"));

    const visibilitySelect = screen.getByRole("combobox");
    expect(within(visibilitySelect).queryByText("role-restricted")).toBeNull();
    expect(within(visibilitySelect).getByText("Public — 所有人可見")).toBeDefined();
    expect(within(visibilitySelect).getByText("Restricted — 僅授權的工作區成員可見")).toBeDefined();
    expect(within(visibilitySelect).getByText("Confidential — 僅 owner 可見")).toBeDefined();

    fireEvent.change(visibilitySelect, { target: { value: "restricted" } });

    expect(await screen.findByText("Pick the visibility level first, then scope the workspace audiences below.")).toBeDefined();
    const rolesField = screen.getByText("Workspace roles").closest("div")?.parentElement as HTMLElement;
    const departmentsField = screen.getByText("Workspace groups").closest("div")?.parentElement as HTMLElement;
    const membersField = screen.getByText("Authorized members").closest("div")?.parentElement as HTMLElement;

    expect(within(rolesField).getByRole("button", { name: /engineering/i })).toBeDefined();
    expect(within(departmentsField).getByRole("button", { name: /^finance/i })).toBeDefined();
    expect(within(membersField).getByRole("button", { name: /Alice/i })).toBeDefined();

    fireEvent.click(within(rolesField).getByRole("button", { name: /engineering/i }));
    fireEvent.click(within(departmentsField).getByRole("button", { name: /^finance/i }));
    fireEvent.click(within(membersField).getByRole("button", { name: /Alice/i }));
    fireEvent.click(screen.getByText("Save Visibility"));

    await waitFor(() => {
      expect(updateEntityVisibilityMock).toHaveBeenCalledWith("token-123", "entity-1", {
        visibility: "restricted",
        visible_to_roles: ["engineering"],
        visible_to_members: ["partner-1"],
        visible_to_departments: ["finance"],
      });
    });
  });
});
