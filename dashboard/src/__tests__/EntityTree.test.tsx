import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { Entity } from "@/types";

const authState = {
  user: null as null | { getIdToken: () => Promise<string> },
  partner: null as null | { isAdmin: boolean },
};

const getRelationshipsMock = vi.fn();
const updateEntityVisibilityMock = vi.fn();

vi.mock("@/lib/auth", () => ({
  useAuth: () => authState,
}));

vi.mock("@/lib/api", () => ({
  getRelationships: (...args: unknown[]) => getRelationshipsMock(...args),
  updateEntityVisibility: (...args: unknown[]) => updateEntityVisibilityMock(...args),
}));

import { EntityTree } from "@/components/EntityTree";

afterEach(cleanup);

beforeEach(() => {
  authState.user = null;
  authState.partner = null;
  getRelationshipsMock.mockReset();
  updateEntityVisibilityMock.mockReset();
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

describe("EntityTree — visibility selector", () => {
  it("normalizes legacy visibility and only exposes the new visibility options", async () => {
    authState.user = {
      getIdToken: vi.fn().mockResolvedValue("token-123"),
    };
    authState.partner = { isAdmin: true };
    getRelationshipsMock.mockResolvedValue([]);

    const legacyEntity = makeEntity({
      visibility: "role-restricted" as unknown as Entity["visibility"],
    });

    render(<EntityTree entities={[legacyEntity]} allEntities={[legacyEntity]} />);

    fireEvent.click(screen.getByLabelText("Expand Auth Module"));

    const select = await screen.findByLabelText("Visibility for Auth Module");
    expect(within(select).queryByText("role-restricted")).toBeNull();
    expect(within(select).getByText("public")).toBeDefined();
    expect(within(select).getByText("restricted")).toBeDefined();
    expect(within(select).getByText("confidential")).toBeDefined();
    expect((select as HTMLSelectElement).value).toBe("restricted");

    fireEvent.change(select, { target: { value: "confidential" } });
    fireEvent.click(screen.getByText("Save Visibility"));

    await waitFor(() => {
      expect(updateEntityVisibilityMock).toHaveBeenCalledWith("token-123", "entity-1", {
        visibility: "confidential",
        visible_to_roles: [],
        visible_to_departments: [],
        visible_to_members: [],
      });
    });
  });
});
