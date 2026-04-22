import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockGetDeals = vi.fn();
const mockGetCompanies = vi.fn();
const mockGetDeal = vi.fn();
const mockGetDealActivities = vi.fn();
const mockFetchDealAiEntries = vi.fn();
const mockGetCompany = vi.fn();
const mockGetCompanyContacts = vi.fn();
const mockCreateDeal = vi.fn();
const mockCreateCompany = vi.fn();
const mockUpdateDeal = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: vi.fn(),
  }),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: {
      getIdToken: vi.fn(async () => "token"),
    },
    partner: {
      id: "partner-1",
    },
  }),
}));

vi.mock("@/lib/partner", () => ({
  resolveActiveWorkspace: () => ({
    isHomeWorkspace: true,
  }),
}));

vi.mock("@/lib/crm-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/crm-api")>("@/lib/crm-api");
  return {
    ...actual,
    getDeals: (...args: unknown[]) => mockGetDeals(...args),
    getCompanies: (...args: unknown[]) => mockGetCompanies(...args),
    getDeal: (...args: unknown[]) => mockGetDeal(...args),
    getDealActivities: (...args: unknown[]) => mockGetDealActivities(...args),
    fetchDealAiEntries: (...args: unknown[]) => mockFetchDealAiEntries(...args),
    getCompany: (...args: unknown[]) => mockGetCompany(...args),
    getCompanyContacts: (...args: unknown[]) => mockGetCompanyContacts(...args),
    createDeal: (...args: unknown[]) => mockCreateDeal(...args),
    createCompany: (...args: unknown[]) => mockCreateCompany(...args),
    updateDeal: (...args: unknown[]) => mockUpdateDeal(...args),
    patchDealStage: vi.fn(),
    createActivity: vi.fn(),
    createAiInsight: vi.fn(),
  };
});

vi.mock("@/features/crm/CrmAiPanel", () => ({
  CrmAiPanel: ({ mode }: { mode: string }) => <div>{`Mock CRM AI Panel:${mode}`}</div>,
}));

import ZenInkClientsWorkspace from "@/features/crm/ZenInkClientsWorkspace";

describe("ZenInkClientsWorkspace", () => {
  beforeEach(() => {
    mockGetDeals.mockResolvedValue([
      {
        id: "deal-1",
        partnerId: "partner-1",
        title: "企業流程導入",
        companyId: "company-1",
        ownerPartnerId: "owner-1",
        funnelStage: "需求訪談",
        amountTwd: 120000,
        deliverables: [],
        isClosedLost: false,
        isOnHold: false,
        createdAt: new Date("2026-04-01T00:00:00Z"),
        updatedAt: new Date("2026-04-01T00:00:00Z"),
      },
    ]);
    mockGetCompanies.mockResolvedValue([
      {
        id: "company-1",
        partnerId: "partner-1",
        name: "Acme Corp",
        createdAt: new Date("2026-04-01T00:00:00Z"),
        updatedAt: new Date("2026-04-01T00:00:00Z"),
      },
    ]);
    mockGetDeal.mockResolvedValue({
      id: "deal-1",
      partnerId: "partner-1",
      title: "企業流程導入",
      companyId: "company-1",
      ownerPartnerId: "owner-1",
      funnelStage: "需求訪談",
      amountTwd: 120000,
      deliverables: [],
      isClosedLost: false,
      isOnHold: false,
      createdAt: new Date("2026-04-01T00:00:00Z"),
      updatedAt: new Date("2026-04-01T00:00:00Z"),
    });
    mockGetDealActivities.mockResolvedValue([]);
    mockFetchDealAiEntries.mockResolvedValue({
      briefings: [],
      debriefs: [],
      commitments: [],
    });
    mockGetCompany.mockResolvedValue({
      id: "company-1",
      partnerId: "partner-1",
      name: "Acme Corp",
      zenosEntityId: "entity-1",
      createdAt: new Date("2026-04-01T00:00:00Z"),
      updatedAt: new Date("2026-04-01T00:00:00Z"),
    });
    mockGetCompanyContacts.mockResolvedValue([]);
    mockCreateDeal.mockReset();
    mockCreateCompany.mockReset();
    mockUpdateDeal.mockReset();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("opens the CRM briefing panel from the Zen Ink deal detail", async () => {
    render(<ZenInkClientsWorkspace />);

    await waitFor(() => expect(screen.getByText("企業流程導入")).toBeInTheDocument());
    fireEvent.click(screen.getByText("企業流程導入"));

    await waitFor(() => expect(screen.getByText("Acme Corp")).toBeInTheDocument());
    fireEvent.click(screen.getByText("準備下次會議"));

    await waitFor(() => expect(screen.getByText("Mock CRM AI Panel:briefing")).toBeInTheDocument());
  });

  it("renders null deal amounts as dash instead of literal null", async () => {
    mockGetDeals.mockResolvedValue([
      {
        id: "deal-2",
        partnerId: "partner-1",
        title: "年度顧問案",
        companyId: "company-1",
        ownerPartnerId: "owner-1",
        funnelStage: "提案報價",
        amountTwd: null,
        deliverables: [],
        isClosedLost: false,
        isOnHold: false,
        createdAt: new Date("2026-04-02T00:00:00Z"),
        updatedAt: new Date("2026-04-02T00:00:00Z"),
      },
    ]);

    render(<ZenInkClientsWorkspace />);

    await waitFor(() => expect(screen.getByText("年度顧問案")).toBeInTheDocument());
    expect(screen.queryByText(/^null$/i)).not.toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("keeps CRM AI discussion entry visible outside overview tab", async () => {
    render(<ZenInkClientsWorkspace />);

    await waitFor(() => expect(screen.getByText("企業流程導入")).toBeInTheDocument());
    fireEvent.click(screen.getByText("企業流程導入"));
    fireEvent.click(await screen.findByRole("button", { name: "活動" }));

    await waitFor(() => expect(screen.getByText("AI 會議準備")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "開始 AI 討論" })).toBeInTheDocument();
  });

  it("opens new deal modal from 新機會 CTA", async () => {
    render(<ZenInkClientsWorkspace />);

    await waitFor(() => expect(screen.getByRole("button", { name: "新機會" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "新機會" }));

    expect(await screen.findByText("新增商機")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "建立商機" })).toBeInTheDocument();
  });

  it("toggles inactive deals from 篩選 CTA", async () => {
    mockGetDeals.mockImplementation(async (_token: string, includeInactive?: boolean) => {
      const base = [
        {
          id: "deal-1",
          partnerId: "partner-1",
          title: "企業流程導入",
          companyId: "company-1",
          ownerPartnerId: "owner-1",
          funnelStage: "需求訪談",
          amountTwd: 120000,
          deliverables: [],
          isClosedLost: false,
          isOnHold: false,
          createdAt: new Date("2026-04-01T00:00:00Z"),
          updatedAt: new Date("2026-04-01T00:00:00Z"),
        },
      ];
      if (!includeInactive) return base;
      return [
        ...base,
        {
          id: "deal-2",
          partnerId: "partner-1",
          title: "封存商機",
          companyId: "company-1",
          ownerPartnerId: "owner-1",
          funnelStage: "提案報價",
          amountTwd: 80000,
          deliverables: [],
          isClosedLost: true,
          isOnHold: false,
          createdAt: new Date("2026-04-02T00:00:00Z"),
          updatedAt: new Date("2026-04-02T00:00:00Z"),
        },
      ];
    });

    render(<ZenInkClientsWorkspace />);

    await waitFor(() => expect(screen.getByRole("button", { name: "顯示封存" })).toBeInTheDocument());
    expect(screen.queryByText("封存商機")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "顯示封存" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "只看進行中" })).toBeInTheDocument());
    expect(await screen.findByText("封存商機")).toBeInTheDocument();
  });

  it("saves expected close date from 排程 CTA", async () => {
    mockUpdateDeal.mockResolvedValue({
      id: "deal-1",
      partnerId: "partner-1",
      title: "企業流程導入",
      companyId: "company-1",
      ownerPartnerId: "owner-1",
      funnelStage: "需求訪談",
      amountTwd: 120000,
      deliverables: [],
      isClosedLost: false,
      isOnHold: false,
      expectedCloseDate: new Date("2026-05-15T00:00:00Z"),
      createdAt: new Date("2026-04-01T00:00:00Z"),
      updatedAt: new Date("2026-04-03T00:00:00Z"),
    });

    render(<ZenInkClientsWorkspace />);

    await waitFor(() => expect(screen.getByText("企業流程導入")).toBeInTheDocument());
    fireEvent.click(screen.getByText("企業流程導入"));

    await waitFor(() => expect(screen.getByRole("button", { name: "排程" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "排程" }));

    const input = await screen.findByLabelText("預計結案日");
    fireEvent.change(input, { target: { value: "2026-05-15" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存" }));

    await waitFor(() =>
      expect(mockUpdateDeal).toHaveBeenCalledWith("token", "deal-1", {
        expectedCloseDate: "2026-05-15",
      })
    );
  });

  it("opens real CTA buttons instead of keeping placeholders disabled", async () => {
    render(<ZenInkClientsWorkspace />);

    await waitFor(() => expect(screen.getByRole("button", { name: "顯示封存" })).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "顯示封存" })).not.toBeDisabled();

    fireEvent.click(screen.getByText("企業流程導入"));
    await waitFor(() => expect(screen.getByRole("button", { name: "排程" })).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "排程" })).not.toBeDisabled();
  });
});
