"use client";

import { useState } from "react";
import { HealthBar } from "@/components/HealthBar";
import { BlindspotPanel } from "@/components/BlindspotPanel";
import KnowledgeGraph from "@/components/KnowledgeGraph";
import NodeDetailSheet from "@/components/NodeDetailSheet";
import Link from "next/link";
import type { Entity, Blindspot, Relationship } from "@/types";

// Mock data for preview
const MOCK_ENTITIES: Entity[] = [
  {
    id: "e1", name: "Paceriz", type: "product", summary: "AI 健身教練平台，結合運動科學與個人化訓練計畫",
    tags: { what: "健身科技平台", why: "讓每個人都有專屬教練", how: "AI + 運動科學", who: "健身愛好者" },
    status: "active", parentId: null, details: null, confirmedByUser: true,
    owner: null, sources: [], visibility: "public", lastReviewedAt: null,
    createdAt: new Date(), updatedAt: new Date("2026-03-21"),
  },
  {
    id: "e2", name: "訓練計畫系統", type: "module", summary: "根據用戶體能數據自動產生個人化週課表",
    tags: { what: "訓練計畫生成", why: "個人化訓練", how: "ACWR + 週期化", who: "教練, 用戶" },
    status: "active", parentId: "e1", details: null, confirmedByUser: true,
    owner: null, sources: [], visibility: "public", lastReviewedAt: null,
    createdAt: new Date(), updatedAt: new Date("2026-03-20"),
  },
  {
    id: "e3", name: "Rizo AI 教練", type: "module", summary: "AI 對話教練，提供即時訓練建議與動機支持",
    tags: { what: "AI 對話教練", why: "即時指導", how: "Claude API + RAG", who: "用戶" },
    status: "active", parentId: "e1", details: null, confirmedByUser: true,
    owner: null, sources: [], visibility: "public", lastReviewedAt: null,
    createdAt: new Date(), updatedAt: new Date("2026-03-19"),
  },
  {
    id: "e4", name: "運動數據整合", type: "module", summary: "整合 Apple Health、Garmin 等穿戴裝置數據",
    tags: { what: "數據整合層", why: "全面掌握用戶狀態", how: "HealthKit + API", who: "開發者" },
    status: "active", parentId: "e1", details: null, confirmedByUser: false,
    owner: null, sources: [], visibility: "public", lastReviewedAt: null,
    createdAt: new Date(), updatedAt: new Date("2026-03-18"),
  },
  {
    id: "e5", name: "ACWR 安全機制", type: "module", summary: "急慢性負荷比監控，防止過度訓練造成傷害",
    tags: { what: "負荷監控", why: "預防傷害", how: "ACWR 演算法", who: "教練, 物理治療師" },
    status: "active", parentId: "e1", details: null, confirmedByUser: true,
    owner: null, sources: [], visibility: "public", lastReviewedAt: null,
    createdAt: new Date(), updatedAt: new Date("2026-03-15"),
  },
  {
    id: "e6", name: "ZenOS", type: "product", summary: "中小企業的 AI Context 層——建一次 ontology，所有 AI agent 共享 context",
    tags: { what: "Knowledge Ontology", why: "AI agents 共享全局 context", how: "MCP + Firestore", who: "企業老闆, AI agents" },
    status: "active", parentId: null, details: null, confirmedByUser: true,
    owner: null, sources: [], visibility: "public", lastReviewedAt: null,
    createdAt: new Date(), updatedAt: new Date("2026-03-22"),
  },
  {
    id: "e7", name: "Ontology Engine", type: "module", summary: "骨架層 + 神經層雙層治理，自動維護公司知識結構",
    tags: { what: "知識治理引擎", why: "自動化知識管理", how: "事件源 + AI 分析", who: "Architect" },
    status: "active", parentId: "e6", details: null, confirmedByUser: true,
    owner: null, sources: [], visibility: "public", lastReviewedAt: null,
    createdAt: new Date(), updatedAt: new Date("2026-03-22"),
  },
  {
    id: "e8", name: "Action Layer", type: "module", summary: "Ontology 的 output 路徑——從知識洞察驅動行動",
    tags: { what: "任務管理層", why: "知識→行動閉環", how: "MCP tools + Kanban", who: "PM, Architect, Developer" },
    status: "active", parentId: "e6", details: null, confirmedByUser: true,
    owner: null, sources: [], visibility: "public", lastReviewedAt: null,
    createdAt: new Date(), updatedAt: new Date("2026-03-22"),
  },
  {
    id: "e9", name: "提升用戶留存率", type: "goal", summary: "30 天留存率從 25% 提升到 40%",
    tags: { what: "留存目標", why: "商業可持續", how: "個人化 + 社群", who: "PM, 老闆" },
    status: "active", parentId: null, details: null, confirmedByUser: true,
    owner: null, sources: [], visibility: "public", lastReviewedAt: null,
    createdAt: new Date(), updatedAt: new Date("2026-03-10"),
  },
  {
    id: "e10", name: "Barry", type: "role", summary: "創辦人 & CEO，負責產品方向與客戶關係",
    tags: { what: "創辦人", why: "公司治理", how: "決策 + 客戶開發", who: "Barry" },
    status: "active", parentId: null, details: null, confirmedByUser: true,
    owner: null, sources: [], visibility: "public", lastReviewedAt: null,
    createdAt: new Date(), updatedAt: new Date("2026-03-22"),
  },
  {
    id: "e11", name: "Dashboard", type: "module", summary: "公司知識的體檢報告——全景圖、確認佇列、Protocol viewer",
    tags: { what: "視覺化介面", why: "人的 context 消費入口", how: "Next.js + Firestore", who: "老闆, PM" },
    status: "active", parentId: "e6", details: null, confirmedByUser: false,
    owner: null, sources: [], visibility: "public", lastReviewedAt: null,
    createdAt: new Date(), updatedAt: new Date("2026-03-22"),
  },
];

const MOCK_RELATIONSHIPS: Relationship[] = [
  { id: "r1", sourceEntityId: "e2", targetId: "e1", type: "part_of", description: "訓練計畫是 Paceriz 的核心模組", confirmedByUser: true },
  { id: "r2", sourceEntityId: "e3", targetId: "e1", type: "part_of", description: "Rizo 是 Paceriz 的 AI 教練模組", confirmedByUser: true },
  { id: "r3", sourceEntityId: "e4", targetId: "e1", type: "part_of", description: "數據整合是 Paceriz 的基礎模組", confirmedByUser: true },
  { id: "r4", sourceEntityId: "e5", targetId: "e1", type: "part_of", description: "ACWR 是 Paceriz 的安全機制", confirmedByUser: true },
  { id: "r5", sourceEntityId: "e2", targetId: "e5", type: "depends_on", description: "訓練計畫依賴 ACWR 做負荷檢查", confirmedByUser: true },
  { id: "r6", sourceEntityId: "e3", targetId: "e2", type: "depends_on", description: "Rizo 需要讀取訓練計畫來給建議", confirmedByUser: true },
  { id: "r7", sourceEntityId: "e2", targetId: "e4", type: "depends_on", description: "訓練計畫需要運動數據作為輸入", confirmedByUser: true },
  { id: "r8", sourceEntityId: "e7", targetId: "e6", type: "part_of", description: "Ontology Engine 是 ZenOS 核心", confirmedByUser: true },
  { id: "r9", sourceEntityId: "e8", targetId: "e6", type: "part_of", description: "Action Layer 是 ZenOS 應用層", confirmedByUser: true },
  { id: "r10", sourceEntityId: "e11", targetId: "e6", type: "part_of", description: "Dashboard 是 ZenOS 的視覺化介面", confirmedByUser: true },
  { id: "r11", sourceEntityId: "e8", targetId: "e7", type: "depends_on", description: "Action Layer 依賴 Ontology Engine 提供 context", confirmedByUser: true },
  { id: "r12", sourceEntityId: "e9", targetId: "e1", type: "serves", description: "留存目標驅動 Paceriz 產品決策", confirmedByUser: true },
  { id: "r13", sourceEntityId: "e10", targetId: "e6", type: "owned_by", description: "Barry 擁有 ZenOS", confirmedByUser: true },
  { id: "r14", sourceEntityId: "e10", targetId: "e1", type: "owned_by", description: "Barry 擁有 Paceriz", confirmedByUser: true },
  { id: "r15", sourceEntityId: "e11", targetId: "e8", type: "depends_on", description: "Dashboard 消費 Action Layer 的任務資料", confirmedByUser: true },
];

const MOCK_BLINDSPOTS: Blindspot[] = [
  {
    id: "b1", description: "運動數據整合模組缺少 API 錯誤處理文件，穿戴裝置斷線時行為未定義",
    severity: "red", relatedEntityIds: ["e4"], suggestedAction: "建立 API 錯誤處理規格文件",
    status: "open", confirmedByUser: false, createdAt: new Date(),
  },
  {
    id: "b2", description: "ACWR 演算法的參數閾值來源不明，缺少運動科學文獻引用",
    severity: "yellow", relatedEntityIds: ["e5"], suggestedAction: "補充 ACWR 參數的科學依據文件",
    status: "open", confirmedByUser: false, createdAt: new Date(),
  },
  {
    id: "b3", description: "Dashboard 模組的 ontology entry 尚未確認（confirmedByUser=false）",
    severity: "yellow", relatedEntityIds: ["e11"], suggestedAction: "確認 Dashboard entity 的四維標籤",
    status: "open", confirmedByUser: false, createdAt: new Date(),
  },
];

export default function PreviewPage() {
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);

  const blindspotsByEntity = new Map<string, Blindspot[]>();
  for (const bs of MOCK_BLINDSPOTS) {
    for (const eid of bs.relatedEntityIds) {
      if (!blindspotsByEntity.has(eid)) blindspotsByEntity.set(eid, []);
      blindspotsByEntity.get(eid)!.push(bs);
    }
  }

  const openBlindspots = MOCK_BLINDSPOTS.filter((b) => b.status === "open");
  const products = MOCK_ENTITIES.filter((e) => e.type === "product");
  const selectedEntityBlindspots = selectedEntity
    ? blindspotsByEntity.get(selectedEntity.id) ?? []
    : [];

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-[#1F1F23]">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <h1 className="text-xl font-bold text-white">ZenOS</h1>
            <nav className="flex items-center gap-4 text-sm">
              <span className="font-semibold text-white underline underline-offset-4">
                Panorama
              </span>
              <Link href="/tasks" className="text-[#71717A] hover:text-white">
                Tasks
              </Link>
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-[#71717A]">Barry Wu</span>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        <HealthBar
          entities={MOCK_ENTITIES}
          blindspots={MOCK_BLINDSPOTS}
        />

        <div
          className="bg-[#0A0A0B] rounded-lg border border-[#1F1F23] overflow-hidden"
          style={{ height: "560px" }}
        >
          <KnowledgeGraph
            entities={MOCK_ENTITIES}
            relationships={MOCK_RELATIONSHIPS}
            blindspotsByEntity={blindspotsByEntity}
            onNodeClick={(entity) => setSelectedEntity(entity)}
          />
        </div>

        <BlindspotPanel blindspots={openBlindspots} entities={MOCK_ENTITIES} />

        {products.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-[#FAFAFA]/60 uppercase tracking-wider mb-3">
              Projects
            </h3>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {products.map((p) => (
                <div
                  key={p.id}
                  className="bg-[#111113] border border-[#1F1F23] rounded-lg p-4 hover:border-[#3F3F46] transition-colors"
                >
                  <div className="text-sm font-medium text-white">{p.name}</div>
                  <div className="text-xs text-[#71717A] mt-1">{p.summary.slice(0, 40)}...</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      <NodeDetailSheet
        entity={selectedEntity}
        relationships={MOCK_RELATIONSHIPS}
        blindspots={selectedEntityBlindspots}
        entities={MOCK_ENTITIES}
        tasks={[]}
        onClose={() => setSelectedEntity(null)}
      />
    </div>
  );
}
