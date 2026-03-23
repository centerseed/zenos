// Real data dumped from Firestore 2026-03-22
// This is what the boss will actually see — messy, incomplete, mixed languages

export interface RealEntity {
  id: string;
  name: string;
  type: "product" | "module" | "goal" | "role";
  summary: string;
  tags: { what: string; why: string; how: string; who: string };
  status: string;
  parentId: string | null;
  confirmedByUser: boolean;
  updatedAt: string;
  details?: { knownIssues?: string[] } | null;
}

export interface RealBlindspot {
  id: string;
  description: string;
  severity: "red" | "yellow" | "green";
  relatedEntityIds: string[];
  suggestedAction: string;
  status: string;
  confirmedByUser: boolean;
}

export interface RealRelationship {
  id: string;
  sourceEntityId: string;
  targetId: string;
  type: string;
  description: string;
  confirmedByUser: boolean;
}

export interface RealTask {
  id: string;
  title: string;
  status: string;
  priority: string;
  assignee: string;
  linkedEntities: string[];
  linkedBlindspot: string | null;
  contextSummary: string;
  createdBy: string;
}

export const REAL_ENTITIES: RealEntity[] = [
  { id: "5cvJJS511jo2YUzw5uqG", type: "product", name: "Paceriz", summary: "AI 驅動的個人化跑步訓練助手，整合多平台運動數據，用科學化訓練負荷管理幫跑者安全進步", status: "active", tags: { who: "休閒到競技跑者（5K ~ 馬拉松）", what: "AI 跑步教練 App", how: "整合 Garmin/Apple Health 數據 + ACWR + AI 建議", why: "讓每個跑者都有一位專業的 AI 教練" }, parentId: null, confirmedByUser: true, updatedAt: "2026-03-22T09:49:18.831Z" },
  { id: "FuRcBTQSEowtqFxoFnJT", type: "product", name: "Paceriz API Service", summary: "跑步訓練 AI 教練後端平台，Flask + Firestore + GCP Cloud Run，三層架構（API→Domain→Core）", status: "active", tags: { who: "跑步愛好者、馬拉松訓練者", what: "跑步訓練、AI 教練、訓練計畫生成、運動數據分析", how: "Flask + Firestore + Cloud Run，LLM 驅動的計畫生成與對話", why: "為跑者提供個人化 AI 訓練指導" }, parentId: null, confirmedByUser: true, updatedAt: "2026-03-21T14:00:20.858Z" },
  { id: "CTgrAyJ57vOppDiC1Tjm", type: "product", name: "Paceriz iOS App", summary: "Paceriz 跑步訓練 AI 教練的 iOS 原生客戶端，SwiftUI + Clean Architecture 四層架構", status: "active", tags: { who: "iOS 開發團隊、跑步用戶", what: "iOS native app, SwiftUI, Clean Architecture, MVVM", how: "四層 Clean Architecture + Repository Pattern + DI Container + 雙軌緩存", why: "提供跑者個人化訓練計畫與 AI 教練指導的行動端體驗" }, parentId: null, confirmedByUser: true, updatedAt: "2026-03-22T08:18:14.529Z" },
  // Modules under Paceriz (abstract)
  { id: "MjoKZuH6k8txCGO4Yj3Q", type: "module", name: "訓練計畫系統", summary: "自動產生週課表、週回顧、提前生成下週課表", status: "active", tags: { who: "跑者（終端用戶）", what: "訓練計畫模組", how: "根據 ACWR 安全機制 + 用戶目標自動排課", why: "讓跑者每週有結構化的訓練計畫" }, parentId: "5cvJJS511jo2YUzw5uqG", confirmedByUser: false, updatedAt: "2026-03-22T09:49:11.949Z" },
  { id: "FcFbsO86FsScQFnnT9Ay", type: "module", name: "ACWR 安全機制", summary: "急慢性訓練負荷比，防止過度訓練", status: "active", tags: { who: "跑者（間接受益）、後端開發者", what: "ACWR 安全機制模組", how: "計算 Acute:Chronic Workload Ratio，設定安全閾值", why: "防止跑者因過度訓練受傷" }, parentId: "5cvJJS511jo2YUzw5uqG", confirmedByUser: false, updatedAt: "2026-03-22T09:49:12.643Z", details: { knownIssues: ["第一週無保護（ACWR = 9999）", "Taper 後恢復缺失", "邏輯一致性衝突"] } },
  { id: "UqOFRtskVHN8GOCjsPyp", type: "module", name: "運動數據整合", summary: "Garmin/Apple Health/Strava 多平台運動數據統一模型", status: "active", tags: { who: "後端開發者", what: "運動數據整合模組", how: "Adapter 架構 + UnifiedWorkoutModel", why: "統一不同手錶/平台的數據格式" }, parentId: "5cvJJS511jo2YUzw5uqG", confirmedByUser: false, updatedAt: "2026-03-22T09:49:12.317Z" },
  { id: "jU8H0tSEVPFQBtDHnGQ4", type: "module", name: "Rizo AI", summary: "基於統一數據模型，提供個性化訓練建議的 AI 教練", status: "active", tags: { who: "跑者（終端用戶）", what: "AI 教練模組", how: "基於運動數據 + 訓練計畫，用 LLM 分析表現並給建議", why: "核心差異化 — 個人化 AI 訓練建議" }, parentId: "5cvJJS511jo2YUzw5uqG", confirmedByUser: false, updatedAt: "2026-03-22T09:49:11.612Z" },
  // Modules under Paceriz API Service
  { id: "8e5EjBKTMtFPwbRb0R46", type: "module", name: "訓練計畫 (Training Plan)", summary: "訓練計畫生成與管理，含總覽與週課表，V3 data model，ACWR 安全機制", status: "active", tags: { why: "根據用戶目標與體能狀態生成個人化訓練安排", who: "跑步用戶", what: "訓練期化、週課表、ACWR 安全、V3 schema", how: "LLM prompt 生成 + 規則引擎驗證" }, parentId: "FuRcBTQSEowtqFxoFnJT", confirmedByUser: true, updatedAt: "2026-03-21T14:00:22.599Z" },
  { id: "0o3RiiA70DMgPaRYeGfE", type: "module", name: "運動數據 (Workout Data)", summary: "運動記錄接收、分析、去重，含 TSB 計算與 VDOT 分析", status: "active", tags: { why: "統一處理多來源運動數據並提供分析洞察", who: "跑步用戶", what: "運動記錄、TSB 計算、VDOT、配速分析、去重", how: "unified adapter 適配多 provider" }, parentId: "FuRcBTQSEowtqFxoFnJT", confirmedByUser: true, updatedAt: "2026-03-21T14:00:25.176Z" },
  { id: "5OcRUghyBzSIIkJLtKH8", type: "module", name: "Rizo AI 教練", summary: "AI 對話教練，支援課表修改、多 agent 架構，tool calling", status: "active", tags: { why: "提供自然語言互動式訓練指導與課表調整", who: "跑步用戶", what: "AI 對話、課表修改、SmartDispatcher", how: "多 agent 架構，Orchestrator 分派至專責 delegate" }, parentId: "FuRcBTQSEowtqFxoFnJT", confirmedByUser: true, updatedAt: "2026-03-21T14:00:30.681Z" },
  { id: "jmTPN4QADleQlGxnA73R", type: "module", name: "Readiness 指標", summary: "五維體能準備度指標，驅動訓練計畫調整", status: "active", tags: { why: "量化用戶體能狀態以動態調整訓練強度", who: "跑步用戶、AI 教練系統", what: "readiness metrics、趨勢分析", how: "基於歷史運動數據計算各維度分數" }, parentId: "FuRcBTQSEowtqFxoFnJT", confirmedByUser: true, updatedAt: "2026-03-21T14:00:27.736Z" },
  { id: "RlUytNZBB7dPmdkMmtq4", type: "module", name: "週回顧 (Weekly Summary)", summary: "每週訓練摘要生成與分析，含客製化建議", status: "active", tags: { why: "幫助用戶理解每週訓練成效", who: "跑步用戶", what: "weekly_summary、訓練回顧", how: "LLM 分析週訓練數據生成摘要" }, parentId: "FuRcBTQSEowtqFxoFnJT", confirmedByUser: true, updatedAt: "2026-03-21T14:00:33.004Z" },
  { id: "Ro0lW44jSE6TAx1mZBT0", type: "module", name: "數據整合 (Integrations)", summary: "Garmin/Strava/Apple Health webhook 接收與資料適配", status: "active", tags: { why: "接收多來源運動裝置數據", who: "Garmin/Strava/Apple Health 用戶", what: "webhook pipeline、unified adapter", how: "webhook → adapter → workouts_v2" }, parentId: "FuRcBTQSEowtqFxoFnJT", confirmedByUser: true, updatedAt: "2026-03-21T14:00:34.737Z" },
  { id: "r7upDF9EvIqOEEM5oVNU", type: "module", name: "用戶管理 (User Management)", summary: "Firebase Auth 認證、用戶設定、i18n 三語系支援", status: "active", tags: { why: "管理用戶身份與個人化設定", who: "所有用戶", what: "auth、user profile、i18n", how: "Firebase Auth + Firestore" }, parentId: "FuRcBTQSEowtqFxoFnJT", confirmedByUser: true, updatedAt: "2026-03-21T14:00:36.730Z" },
  // Modules under Paceriz iOS App
  { id: "VrrlEx2A56tqoSVf92V0", type: "module", name: "Training Plan Module (iOS)", summary: "週課表生成、顯示、編輯與進度追蹤。V1/V2 雙軌實作。", status: "active", tags: { who: "跑步用戶、iOS 開發者", what: "週課表管理、V1/V2 雙軌", how: "Repository Pattern + ViewState<T>", why: "個人化週課表是產品差異化關鍵" }, parentId: "CTgrAyJ57vOppDiC1Tjm", confirmedByUser: true, updatedAt: "2026-03-22T08:18:14.791Z" },
  { id: "9aisWLZCSg0bZzDqWlD9", type: "module", name: "Workout Data Module (iOS)", summary: "HealthKit 運動記錄讀取、心率數據、背景上傳。", status: "active", tags: { who: "跑步用戶、iOS 開發者", what: "HealthKit 整合、背景上傳", how: "HealthKit → Backend API → WorkoutV2", why: "追蹤實際運動數據" }, parentId: "CTgrAyJ57vOppDiC1Tjm", confirmedByUser: true, updatedAt: "2026-03-22T08:18:14.959Z" },
  { id: "nQGyxtVapYD4dLXW9sIJ", type: "module", name: "Authentication Module (iOS)", summary: "Email/Google/Apple Sign-In，Firebase Auth。", status: "active", tags: { who: "所有用戶", what: "Email/Google/Apple 登入", how: "FirebaseAuth + syncUserWithBackend", why: "身份識別是所有功能前置條件" }, parentId: "CTgrAyJ57vOppDiC1Tjm", confirmedByUser: true, updatedAt: "2026-03-22T08:18:15.430Z" },
  { id: "lSNKpnyMD3YkYuTA8nBM", type: "module", name: "User Profile & Onboarding Module (iOS)", summary: "Onboarding 流程、用戶偏好設定。", status: "active", tags: { who: "新用戶、所有用戶", what: "Onboarding、偏好設定", how: "UserPreferencesManager + 雙軌緩存", why: "個人化訓練計畫的基礎" }, parentId: "CTgrAyJ57vOppDiC1Tjm", confirmedByUser: true, updatedAt: "2026-03-22T08:18:15.585Z" },
  { id: "D71D1PX2dnIdiwRAnEZD", type: "module", name: "Garmin Integration Module (iOS)", summary: "Garmin Connect IQ SDK 同步運動數據。", status: "active", tags: { who: "Garmin 跑者", what: "Garmin SDK、裝置配對", how: "Garmin SDK + Brand Compliance", why: "擴大穿戴裝置支援" }, parentId: "CTgrAyJ57vOppDiC1Tjm", confirmedByUser: true, updatedAt: "2026-03-22T08:18:15.916Z" },
  { id: "qI72SRek6Bnd7Wrbqp7v", type: "module", name: "Training Intensity & Readiness Module (iOS)", summary: "ACWR 計算、心率區間強度分鐘數。", status: "active", tags: { who: "跑步用戶", what: "ACWR、心率區間", how: "TrainingIntensityManager + HealthKit", why: "避免過度訓練受傷" }, parentId: "CTgrAyJ57vOppDiC1Tjm", confirmedByUser: true, updatedAt: "2026-03-22T08:18:15.742Z" },
  { id: "irOeuKIAtgYIHqrnq33l", type: "module", name: "Core Infrastructure (iOS)", summary: "HTTPClient、UnifiedCacheManager、DI Container 等共用元件。", status: "active", tags: { who: "iOS 開發者", what: "HTTPClient、CacheManager、DI", how: "Singleton + 泛型 + Protocol-Oriented", why: "共用基礎能力" }, parentId: "CTgrAyJ57vOppDiC1Tjm", confirmedByUser: true, updatedAt: "2026-03-22T08:18:16.149Z" },
];

export const REAL_BLINDSPOTS: RealBlindspot[] = [
  { id: "0APWdyVpLXv64dQ2h93Y", description: "ACWR 三項安全問題已確認但未排修復時程。", severity: "red", relatedEntityIds: ["FcFbsO86FsScQFnnT9Ay"], suggestedAction: "明確定義修復優先順序。安全 > 功能。", status: "open", confirmedByUser: false },
  { id: "sxYf0UrfUXuaR76mbSzv", description: "marketing/ 裡沒有行銷素材，全是技術文件。", severity: "red", relatedEntityIds: ["5cvJJS511jo2YUzw5uqG"], suggestedAction: "用 Context Protocol 作為行銷夥伴的入口。", status: "open", confirmedByUser: false },
  { id: "Y5jVmYpH31yncW5YVNCG", description: "ZenOS ontology 缺少 output 路徑：知識捕獲已有設計，但從 ontology 到任務派發不存在。", severity: "red", relatedEntityIds: [], suggestedAction: "Architect 設計 ontology output 路徑。", status: "open", confirmedByUser: false },
  { id: "n5TpmrTunMj3s9BKAqNf", description: "ZenOS ontology 沒有 application layer 在消費它，無法驗證底座品質。", severity: "red", relatedEntityIds: [], suggestedAction: "Action Layer 優先級最高。", status: "open", confirmedByUser: false },
  { id: "z5fQmYZbRpKyJK7TI6oC", description: "缺少從檔案變化到 ontology 更新的自動觸發機制。所有更新依賴手動 /zenos-capture。", severity: "red", relatedEntityIds: [], suggestedAction: "設計 PostToolUse hook 作為 Governance Daemon。", status: "open", confirmedByUser: false },
  { id: "4BwYNyovSJHNu8Pln5lo", description: "ZenOS 的市場定位需要品類教育——台灣 SMB 不存在「AI context layer」概念。", severity: "yellow", relatedEntityIds: [], suggestedAction: "行銷以痛點故事為主，非功能介紹。", status: "open", confirmedByUser: false },
  { id: "62UgXJbvzV2g17xoinsO", description: "一次性開發報告混在活文件中。", severity: "yellow", relatedEntityIds: ["5cvJJS511jo2YUzw5uqG"], suggestedAction: "移到 archive/。", status: "open", confirmedByUser: false },
  { id: "DivaubpqZMtIwSbDtTul", description: "沒有外部公司的 Free Panorama 驗證案例。", severity: "yellow", relatedEntityIds: [], suggestedAction: "找 2-3 間 SMB 做免費全景圖對話。", status: "open", confirmedByUser: false },
  { id: "Fhl5dLXkSdfeDceU3ITj", description: "跨 agent 整合點應該是 MCP tool descriptions 品質，不是改 skill/prompt。", severity: "yellow", relatedEntityIds: [], suggestedAction: "Tool descriptions 要讓 agent 自然呼叫。", status: "open", confirmedByUser: false },
  { id: "PrYAu4cCiXi6EeRV9QNv", description: "Notebook POC 是寶貴知識但完全沒索引。", severity: "yellow", relatedEntityIds: ["jU8H0tSEVPFQBtDHnGQ4", "MjoKZuH6k8txCGO4Yj3Q"], suggestedAction: "為每個 notebook 建立索引表。", status: "open", confirmedByUser: false },
  { id: "SGy9HXg24t5hn0VxJaC4", description: "User Profile & Onboarding (iOS) 沒有專屬文檔。", severity: "yellow", relatedEntityIds: [], suggestedAction: "建立 Onboarding Flow 文檔。", status: "open", confirmedByUser: false },
  { id: "XlzVNMPUnMj2gRwQahGx", description: "Training Intensity (iOS) 沒有專屬文檔，ACWR 計算只存在程式碼中。", severity: "yellow", relatedEntityIds: [], suggestedAction: "建立 ACWR 計算邏輯文檔。", status: "open", confirmedByUser: false },
  { id: "c7YkjVPqsYVzdRTFa5B4", description: "Authentication (iOS) 沒有專屬文檔。", severity: "yellow", relatedEntityIds: [], suggestedAction: "建立 Auth 流程文檔。", status: "open", confirmedByUser: false },
];

export const REAL_TASKS: RealTask[] = [
  { id: "1", title: "實作 TrainingPlanV2 模組", status: "backlog", priority: "high", assignee: "architect", linkedEntities: [], linkedBlindspot: null, contextSummary: "", createdBy: "architect" },
  { id: "2", title: "建立 deploy script + pre-deploy checklist", status: "done", priority: "high", assignee: "developer", linkedEntities: [], linkedBlindspot: null, contextSummary: "手動部署流程風險", createdBy: "architect" },
  { id: "3", title: "建立 Android 專案骨架", status: "done", priority: "critical", assignee: "architect", linkedEntities: [], linkedBlindspot: null, contextSummary: "", createdBy: "architect" },
  { id: "4", title: "建立 Dashboard 測試基礎設施", status: "done", priority: "critical", assignee: "developer", linkedEntities: [], linkedBlindspot: null, contextSummary: "沒有測試框架、沒有測試檔案", createdBy: "architect" },
  { id: "5", title: "實作國際化（en/ja/zh-Hant）", status: "backlog", priority: "medium", assignee: "architect", linkedEntities: [], linkedBlindspot: null, contextSummary: "", createdBy: "architect" },
  { id: "6", title: "QA 驗收：Action Layer + Company Pulse", status: "done", priority: "high", assignee: "qa", linkedEntities: [], linkedBlindspot: null, contextSummary: "", createdBy: "architect" },
  { id: "7", title: "整合 Garmin + Strava SDK", status: "backlog", priority: "low", assignee: "architect", linkedEntities: [], linkedBlindspot: null, contextSummary: "", createdBy: "architect" },
  { id: "8", title: "實作 MonthlyStats 模組", status: "backlog", priority: "medium", assignee: "architect", linkedEntities: [], linkedBlindspot: null, contextSummary: "", createdBy: "architect" },
  { id: "9", title: "實作 Workout 模組", status: "backlog", priority: "medium", assignee: "architect", linkedEntities: [], linkedBlindspot: null, contextSummary: "", createdBy: "architect" },
  { id: "10", title: "補強 MCP Server 測試", status: "done", priority: "medium", assignee: "developer", linkedEntities: [], linkedBlindspot: null, contextSummary: "缺少 interface/test_tools.py", createdBy: "architect" },
  { id: "11", title: "整合 Health Connect（Android）", status: "backlog", priority: "medium", assignee: "architect", linkedEntities: [], linkedBlindspot: null, contextSummary: "", createdBy: "architect" },
  { id: "12", title: "統一 Firestore 欄位命名", status: "done", priority: "high", assignee: "developer", linkedEntities: [], linkedBlindspot: null, contextSummary: "snake_case vs camelCase 不一致", createdBy: "architect" },
  { id: "13", title: "實作 Authentication（Firebase Auth + Google One Tap）", status: "review", priority: "critical", assignee: "architect", linkedEntities: [], linkedBlindspot: null, contextSummary: "", createdBy: "architect" },
  { id: "14", title: "建立 CI/CD pipeline", status: "done", priority: "critical", assignee: "developer", linkedEntities: [], linkedBlindspot: null, contextSummary: "零 CI/CD，3 個 bug 因沒測試就上線", createdBy: "architect" },
  { id: "15", title: "收尾 Action Layer 四項 Gap", status: "done", priority: "high", assignee: "developer", linkedEntities: [], linkedBlindspot: null, contextSummary: "", createdBy: "architect" },
  { id: "16", title: "建立 Android QA 測試基礎設施", status: "done", priority: "high", assignee: "architect", linkedEntities: [], linkedBlindspot: null, contextSummary: "", createdBy: "architect" },
  { id: "17", title: "實作 Target 模組（訓練目標 CRUD）", status: "backlog", priority: "high", assignee: "architect", linkedEntities: [], linkedBlindspot: null, contextSummary: "", createdBy: "architect" },
  { id: "18", title: "修復 capture skill：module 必須帶 parent_id", status: "done", priority: "high", assignee: "developer", linkedEntities: [], linkedBlindspot: null, contextSummary: "", createdBy: "architect" },
  { id: "19", title: "實作 Company Pulse Dashboard", status: "backlog", priority: "high", assignee: "architect", linkedEntities: [], linkedBlindspot: null, contextSummary: "", createdBy: "pm" },
  { id: "20", title: "實作 Onboarding 模組", status: "backlog", priority: "high", assignee: "architect", linkedEntities: [], linkedBlindspot: null, contextSummary: "", createdBy: "architect" },
  { id: "21", title: "實作 UserProfile 模組", status: "backlog", priority: "medium", assignee: "architect", linkedEntities: [], linkedBlindspot: null, contextSummary: "", createdBy: "architect" },
  { id: "22", title: "實作 Company Pulse Dashboard（P0）", status: "done", priority: "high", assignee: "developer", linkedEntities: [], linkedBlindspot: null, contextSummary: "", createdBy: "architect" },
];

// Real relationships from Firestore subcollections
export const REAL_RELATIONSHIPS: RealRelationship[] = [
  // parentId-based (part_of) — auto-generated from entity tree
  ...REAL_ENTITIES.filter(e => e.parentId).map(e => ({
    id: `parent_${e.id}`,
    sourceEntityId: e.id,
    targetId: e.parentId!,
    type: "part_of",
    description: "",
    confirmedByUser: false,
  })),
  // Explicit relationships from Firestore
  { id: "r1", sourceEntityId: "0o3RiiA70DMgPaRYeGfE", targetId: "Ro0lW44jSE6TAx1mZBT0", type: "depends_on", description: "運動數據來自數據整合模組", confirmedByUser: false },
  { id: "r2", sourceEntityId: "5OcRUghyBzSIIkJLtKH8", targetId: "8e5EjBKTMtFPwbRb0R46", type: "depends_on", description: "Rizo AI 需讀取/修改訓練計畫", confirmedByUser: false },
  { id: "r3", sourceEntityId: "8e5EjBKTMtFPwbRb0R46", targetId: "0o3RiiA70DMgPaRYeGfE", type: "depends_on", description: "訓練計畫依賴運動數據計算 ACWR", confirmedByUser: false },
  { id: "r4", sourceEntityId: "8e5EjBKTMtFPwbRb0R46", targetId: "jmTPN4QADleQlGxnA73R", type: "depends_on", description: "訓練計畫依賴 Readiness 指標", confirmedByUser: false },
  { id: "r5", sourceEntityId: "CTgrAyJ57vOppDiC1Tjm", targetId: "FuRcBTQSEowtqFxoFnJT", type: "depends_on", description: "iOS App 依賴後端 API Service", confirmedByUser: false },
  { id: "r6", sourceEntityId: "FcFbsO86FsScQFnnT9Ay", targetId: "UqOFRtskVHN8GOCjsPyp", type: "depends_on", description: "ACWR 計算需要歷史運動數據", confirmedByUser: false },
  { id: "r7", sourceEntityId: "MjoKZuH6k8txCGO4Yj3Q", targetId: "FcFbsO86FsScQFnnT9Ay", type: "depends_on", description: "訓練計畫需要 ACWR 保護安全", confirmedByUser: false },
  { id: "r8", sourceEntityId: "jU8H0tSEVPFQBtDHnGQ4", targetId: "MjoKZuH6k8txCGO4Yj3Q", type: "depends_on", description: "Rizo AI 需要訓練計畫來給建議", confirmedByUser: false },
  { id: "r9", sourceEntityId: "jU8H0tSEVPFQBtDHnGQ4", targetId: "UqOFRtskVHN8GOCjsPyp", type: "depends_on", description: "Rizo AI 需要統一數據模型", confirmedByUser: false },
  { id: "r10", sourceEntityId: "RlUytNZBB7dPmdkMmtq4", targetId: "0o3RiiA70DMgPaRYeGfE", type: "depends_on", description: "週回顧依賴運動數據", confirmedByUser: false },
  { id: "r11", sourceEntityId: "jmTPN4QADleQlGxnA73R", targetId: "0o3RiiA70DMgPaRYeGfE", type: "depends_on", description: "Readiness 依賴運動數據", confirmedByUser: false },
  { id: "r12", sourceEntityId: "VrrlEx2A56tqoSVf92V0", targetId: "lSNKpnyMD3YkYuTA8nBM", type: "depends_on", description: "Training Plan 需要用戶偏好", confirmedByUser: false },
  { id: "r13", sourceEntityId: "VrrlEx2A56tqoSVf92V0", targetId: "qI72SRek6Bnd7Wrbqp7v", type: "depends_on", description: "Training Plan 需要 Intensity 數據", confirmedByUser: false },
  { id: "r14", sourceEntityId: "9aisWLZCSg0bZzDqWlD9", targetId: "irOeuKIAtgYIHqrnq33l", type: "depends_on", description: "Workout Data 使用 Core 層", confirmedByUser: false },
  { id: "r15", sourceEntityId: "D71D1PX2dnIdiwRAnEZD", targetId: "9aisWLZCSg0bZzDqWlD9", type: "related_to", description: "Garmin 數據流入 Workout Data", confirmedByUser: false },
  { id: "r16", sourceEntityId: "lSNKpnyMD3YkYuTA8nBM", targetId: "nQGyxtVapYD4dLXW9sIJ", type: "depends_on", description: "User Profile 需要 Auth 完成", confirmedByUser: false },
  { id: "r17", sourceEntityId: "qI72SRek6Bnd7Wrbqp7v", targetId: "9aisWLZCSg0bZzDqWlD9", type: "depends_on", description: "Intensity 依賴 HealthKit 心率數據", confirmedByUser: false },
];

// Real documents (152 in Firestore, but linked to OLD entity IDs — none link to current entities)
export interface RealDocument {
  id: string;
  title: string;
  linkedEntityIds: string[];
}

// Just a representative sample — full list is 152 docs
export const REAL_DOCUMENTS: RealDocument[] = [
  { id: "d1", title: "ARCHITECTURE.md — Havital iOS", linkedEntityIds: ["skx4doPcejJL8AtgXFjY"] },
  { id: "d2", title: "CLAUDE.md — Paceriz iOS", linkedEntityIds: ["skx4doPcejJL8AtgXFjY"] },
  { id: "d3", title: "SPEC: Weekly Plan V2", linkedEntityIds: ["36glKJ29gqgwJ2N5oFVY"] },
  { id: "d4", title: "Training V2 API Integration Guide", linkedEntityIds: ["x74gkbGCq7NU8XSPWO1g"] },
  { id: "d5", title: "Agent Architecture Plan", linkedEntityIds: ["lNdk2iZMJSRxbpvu6L4m"] },
  { id: "d6", title: "PRD-001: Paceriz Agent Spec (Rizo V2)", linkedEntityIds: ["lNdk2iZMJSRxbpvu6L4m"] },
  { id: "d7", title: "Garmin Brand Compliance Report", linkedEntityIds: ["Y9VWevHRyxV2dcwpQzEC"] },
  { id: "d8", title: "Database Schema", linkedEntityIds: ["ZgOtG1Nwwm4t1cVzEE2t"] },
  { id: "d9", title: "ACWR Literature Review", linkedEntityIds: [] },
  { id: "d10", title: "Coach Knowledge Base: Training Methods Spectrum", linkedEntityIds: [] },
  // ... 142 more in Firestore
];

export const TOTAL_DOCUMENTS = 152;

export function getDocumentsForEntity(entityId: string): RealDocument[] {
  return REAL_DOCUMENTS.filter(d => d.linkedEntityIds.includes(entityId));
}

// Derived stats
export function getRealStats() {
  const products = REAL_ENTITIES.filter(e => e.type === "product");
  const modules = REAL_ENTITIES.filter(e => e.type === "module");
  const confirmed = REAL_ENTITIES.filter(e => e.confirmedByUser);
  const openBlindspots = REAL_BLINDSPOTS.filter(b => b.status === "open");
  const redBlindspots = openBlindspots.filter(b => b.severity === "red");
  const orphanBlindspots = openBlindspots.filter(b => b.relatedEntityIds.length === 0);
  const activeTasks = REAL_TASKS.filter(t => t.status !== "done" && t.status !== "cancelled");
  const disconnectedTasks = REAL_TASKS.filter(t => t.linkedEntities.length === 0);

  return {
    totalEntities: REAL_ENTITIES.length,
    products: products.length,
    modules: modules.length,
    confirmedCount: confirmed.length,
    confirmedRate: Math.round((confirmed.length / REAL_ENTITIES.length) * 100),
    totalBlindspots: openBlindspots.length,
    redBlindspots: redBlindspots.length,
    yellowBlindspots: openBlindspots.length - redBlindspots.length,
    orphanBlindspots: orphanBlindspots.length,
    totalTasks: REAL_TASKS.length,
    activeTasks: activeTasks.length,
    doneTasks: REAL_TASKS.filter(t => t.status === "done").length,
    disconnectedTasks: disconnectedTasks.length,
    disconnectedTaskRate: Math.round((disconnectedTasks.length / REAL_TASKS.length) * 100),
  };
}

export function getModulesForProduct(productId: string): RealEntity[] {
  return REAL_ENTITIES.filter(e => e.parentId === productId && e.type === "module");
}

export function getBlindspotsForEntity(entityId: string): RealBlindspot[] {
  return REAL_BLINDSPOTS.filter(b => b.relatedEntityIds.includes(entityId));
}

export function getOrphanBlindspots(): RealBlindspot[] {
  return REAL_BLINDSPOTS.filter(b => b.relatedEntityIds.length === 0 && b.status === "open");
}
