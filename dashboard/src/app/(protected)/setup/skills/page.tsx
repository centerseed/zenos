"use client";

import Link from "next/link";
import React, { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

const SKILL_GROUPS = [
  {
    title: "Governance Skills",
    description: "治理規則本體，負責讓 agent 知道什麼情境要讀什麼規則。",
    items: [
      {
        name: "document-governance",
        usage: "寫 SPEC / ADR / TD / 文件更新前讀。",
        attaches: "L3 document lifecycle",
      },
      {
        name: "l2-knowledge-governance",
        usage: "判斷一個概念是不是 L2、三問、impacts 時讀。",
        attaches: "L2 entity rules",
      },
      {
        name: "task-governance",
        usage: "建 task、更新 task、驗收 task 前讀。",
        attaches: "Action layer rules",
      },
    ],
  },
  {
    title: "Workflow Skills",
    description: "把治理規則包成可執行流程，對應 setup / capture / sync / governance loop。",
    items: [
      {
        name: "zenos-setup",
        usage: "MCP 已接通後，安裝或更新對應平台的 skill / agent / flow。",
        attaches: "Platform bootstrap flow",
      },
      {
        name: "zenos-capture",
        usage: "第一次建 ontology 或從當前對話 / 文件捕獲知識。",
        attaches: "Knowledge capture flow",
      },
      {
        name: "zenos-sync",
        usage: "既有 ontology 專案做 git-based 增量同步。",
        attaches: "Knowledge sync flow",
      },
      {
        name: "zenos-governance",
        usage: "自動跑治理掃描、修補、建票、回寫。",
        attaches: "Governance loop",
      },
    ],
  },
  {
    title: "Attached Agents / Roles",
    description: "安裝 release skills 後，這些角色會共用同一套 ZenOS 治理入口。",
    items: [
      {
        name: "Architect",
        usage: "做技術規劃、任務分配、交付審查。",
        attaches: "Reads governance before architecture work",
      },
      {
        name: "Developer",
        usage: "依 spec / TD 實作功能。",
        attaches: "Executes with ZenOS task and doc rules",
      },
      {
        name: "QA",
        usage: "驗收交付與測試回報。",
        attaches: "Uses task acceptance flow",
      },
      {
        name: "PM / Designer / Marketing / Debugger / Challenger",
        usage: "不同角色在需要時切換，但仍共享同一套治理地板。",
        attaches: "Role-specific prompts + shared governance",
      },
    ],
  },
];

function SetupSkillsPage() {
  const { partner } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (partner && !partner.isAdmin) {
      router.replace("/");
    }
  }, [partner, router]);

  if (!partner || !partner.isAdmin) return null;

  return (
    <div className="min-h-screen">
      <main id="main-content" className="max-w-5xl mx-auto px-6 py-8 space-y-8">
        <section className="space-y-3">
          <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
            Setup
          </p>
          <h1 className="text-3xl font-bold text-foreground">
            ZenOS skills / agents / flows
          </h1>
          <p className="max-w-3xl text-muted-foreground">
            這一頁只講安裝完成後會多出什麼治理能力，不再重複平台的 MCP 安裝步驟。
          </p>
        </section>

        {SKILL_GROUPS.map((group) => (
          <section
            key={group.title}
            className="rounded-2xl border border-border bg-card p-6"
          >
            <h2 className="text-xl font-semibold text-foreground">{group.title}</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {group.description}
            </p>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              {group.items.map((item) => (
                <div
                  key={item.name}
                  className="rounded-xl border border-border bg-background/70 p-4"
                >
                  <h3 className="font-medium text-foreground">{item.name}</h3>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {item.usage}
                  </p>
                  <p className="mt-2 text-xs uppercase tracking-[0.22em] text-muted-foreground">
                    Attached
                  </p>
                  <p className="mt-1 text-sm text-foreground/85">
                    {item.attaches}
                  </p>
                </div>
              ))}
            </div>
          </section>
        ))}

        <section className="rounded-2xl border border-blue-500/30 bg-blue-500/10 p-6">
          <h2 className="text-xl font-semibold text-foreground">
            頁面上建議補的兩句提醒
          </h2>
          <div className="mt-4 space-y-3 text-sm text-muted-foreground">
            <p>
              Skills 不是 MCP 的替代品。沒有 MCP，skills 只能提供流程指引，不能真的讀寫 ZenOS ontology。
            </p>
            <p>
              第一次上線既有專案時，先用 `zenos-capture` 建庫，再讓 `zenos-sync`
              接手日常增量同步。
            </p>
          </div>
        </section>

        <div className="flex justify-between text-sm">
          <Link href="/setup" className="text-blue-400 hover:underline">
            Back to setup
          </Link>
          <Link href="/" className="text-blue-400 hover:underline">
            Back to projects
          </Link>
        </div>
      </main>
    </div>
  );
}

export default function Page() {
  return <SetupSkillsPage />;
}
