// Shared mock data for preview mockups — boss-friendly language
export interface Product {
  id: string;
  name: string;
  summary: string;
  health: "healthy" | "warning" | "critical";
  owner: string;
  modules: Module[];
  goals: Goal[];
  blindspots: BlindspotItem[];
  confirmedRate: number; // 0-100
  lastUpdated: string;
}

export interface Module {
  id: string;
  name: string;
  summary: string;
  health: "healthy" | "warning" | "critical";
  who: string;
  confirmed: boolean;
}

export interface Goal {
  id: string;
  name: string;
  metric: string;
  status: "on_track" | "at_risk" | "behind";
}

export interface BlindspotItem {
  id: string;
  title: string;       // boss-friendly title
  description: string;  // boss-friendly explanation
  severity: "red" | "yellow";
  relatedModule: string;
  suggestedAction: string;
}

export const PRODUCTS: Product[] = [
  {
    id: "paceriz",
    name: "Paceriz",
    summary: "AI 健身教練平台，結合運動科學與個人化訓練計畫",
    health: "warning",
    owner: "Barry",
    confirmedRate: 80,
    lastUpdated: "2 小時前",
    modules: [
      { id: "m1", name: "訓練計畫系統", summary: "根據體能數據自動產生個人化週課表", health: "healthy", who: "教練, 用戶", confirmed: true },
      { id: "m2", name: "Rizo AI 教練", summary: "AI 對話教練，即時訓練建議與動機支持", health: "healthy", who: "用戶", confirmed: true },
      { id: "m3", name: "運動數據整合", summary: "整合 Apple Health、Garmin 等穿戴裝置數據", health: "critical", who: "開發者", confirmed: false },
      { id: "m4", name: "ACWR 安全機制", summary: "急慢性負荷比監控，防止過度訓練傷害", health: "warning", who: "教練, 物理治療師", confirmed: true },
    ],
    goals: [
      { id: "g1", name: "提升用戶留存率", metric: "30 天留存 25% → 40%", status: "at_risk" },
    ],
    blindspots: [
      {
        id: "b1",
        title: "穿戴裝置斷線怎麼辦？沒人知道",
        description: "運動數據整合模組缺少斷線處理機制。如果用戶的手錶斷開連線，系統行為是未定義的——可能導致訓練計畫用錯誤數據生成。",
        severity: "red",
        relatedModule: "運動數據整合",
        suggestedAction: "定義斷線時的 fallback 行為",
      },
      {
        id: "b2",
        title: "ACWR 的安全閾值從哪來的？",
        description: "急慢性負荷比的參數閾值缺少運動科學文獻引用。如果這些數字不對，安全機制可能反而讓用戶受傷。",
        severity: "yellow",
        relatedModule: "ACWR 安全機制",
        suggestedAction: "補充科學依據，確認閾值合理性",
      },
    ],
  },
  {
    id: "zenos",
    name: "ZenOS",
    summary: "中小企業的 AI Context 層——讓每個 AI agent 都懂你的公司",
    health: "healthy",
    owner: "Barry",
    confirmedRate: 90,
    lastUpdated: "剛剛",
    modules: [
      { id: "m5", name: "Ontology Engine", summary: "骨架層 + 神經層雙層治理，自動維護知識結構", health: "healthy", who: "Architect", confirmed: true },
      { id: "m6", name: "Action Layer", summary: "從知識洞察驅動行動的任務管理層", health: "healthy", who: "PM, Developer", confirmed: true },
      { id: "m7", name: "Dashboard", summary: "公司知識的體檢報告——全景圖與確認佇列", health: "warning", who: "老闆, PM", confirmed: false },
    ],
    goals: [],
    blindspots: [
      {
        id: "b3",
        title: "Dashboard 的定位還在草稿階段",
        description: "Dashboard 模組的 ontology entry 尚未經過確認，四維標籤可能不準確。",
        severity: "yellow",
        relatedModule: "Dashboard",
        suggestedAction: "確認 Dashboard 的四維標籤",
      },
    ],
  },
];

export const COMPANY_STATS = {
  totalEntities: 11,
  confirmedRate: 82,
  totalBlindspots: 3,
  redBlindspots: 1,
  products: 2,
  lastUpdated: "2 小時前",
};
