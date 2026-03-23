import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

// Mock next/link
vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

import { ProjectCard } from "@/components/ProjectCard";
import type { Entity } from "@/types";

afterEach(cleanup);

function makeEntity(overrides: Partial<Entity> = {}): Entity {
  return {
    id: "entity-1",
    name: "Paceriz iOS App",
    type: "product",
    summary: "A running coach app for iOS",
    tags: { what: "app", why: "coaching", how: "AI", who: "runners" },
    status: "active",
    parentId: null,
    details: null,
    confirmedByUser: true,
    owner: null,
    sources: [],
    visibility: "public",
    lastReviewedAt: null,
    createdAt: new Date("2026-01-01"),
    updatedAt: new Date("2026-03-15"),
    ...overrides,
  };
}

describe("ProjectCard", () => {
  it("renders entity name", () => {
    render(<ProjectCard entity={makeEntity()} moduleCount={5} />);
    expect(screen.getByText("Paceriz iOS App")).toBeInTheDocument();
  });

  it("renders entity summary", () => {
    render(<ProjectCard entity={makeEntity()} moduleCount={5} />);
    expect(screen.getByText("A running coach app for iOS")).toBeInTheDocument();
  });

  it("renders module count", () => {
    render(<ProjectCard entity={makeEntity()} moduleCount={7} />);
    expect(screen.getByText("7 modules")).toBeInTheDocument();
  });

  it("renders status badge", () => {
    render(<ProjectCard entity={makeEntity({ status: "paused" })} moduleCount={0} />);
    expect(screen.getByText("paused")).toBeInTheDocument();
  });

  it("renders formatted date", () => {
    render(<ProjectCard entity={makeEntity()} moduleCount={0} />);
    const dateText = new Date("2026-03-15").toLocaleDateString("zh-TW");
    expect(screen.getByText(new RegExp(`Updated\\s+${dateText.replace("/", "\\/")}`))).toBeInTheDocument();
  });

  it("links to correct project page", () => {
    render(<ProjectCard entity={makeEntity({ id: "abc-123" })} moduleCount={0} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/projects?id=abc-123");
  });

  it("renders with empty summary", () => {
    render(
      <ProjectCard
        entity={makeEntity({ summary: "" })}
        moduleCount={0}
      />
    );
    expect(screen.getByText("Paceriz iOS App")).toBeInTheDocument();
  });

  it("renders with zero modules", () => {
    render(<ProjectCard entity={makeEntity()} moduleCount={0} />);
    expect(screen.getByText("0 modules")).toBeInTheDocument();
  });

  it("renders unknown status with fallback styling", () => {
    render(
      <ProjectCard
        entity={makeEntity({ status: "planned" })}
        moduleCount={0}
      />
    );
    expect(screen.getByText("planned")).toBeInTheDocument();
  });
});
