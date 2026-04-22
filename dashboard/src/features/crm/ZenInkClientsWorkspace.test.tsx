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

  it("disables placeholder CTA buttons that are not implemented yet", async () => {
    render(<ZenInkClientsWorkspace />);

    await waitFor(() => expect(screen.getByRole("button", { name: "篩選" })).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "篩選" })).toBeDisabled();

    fireEvent.click(screen.getByText("企業流程導入"));
    await waitFor(() => expect(screen.getByRole("button", { name: "排程" })).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "排程" })).toBeDisabled();
  });
});
