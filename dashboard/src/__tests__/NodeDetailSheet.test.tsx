import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
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

import NodeDetailSheet from "@/components/NodeDetailSheet";

afterEach(cleanup);

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
