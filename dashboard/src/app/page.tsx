import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Network, Radar, Zap, BrainCircuit, Workflow, Search, CheckCircle2, XCircle, ShieldCheck, Users } from "lucide-react";

export const metadata: Metadata = {
  title: "ZenOS | 個人工作流的 Context Layer",
  description: "讓 AI 先看懂你的工作脈絡，再開始協作。",
};

const evidence = [
  { icon: Network, text: "變更不再停在文件裡，而會沿著影響鏈往外傳遞。" },
  { icon: Workflow, text: "任務不再是孤立 ticket，而是帶著你的決策脈絡往下執行。" },
  { icon: BrainCircuit, text: "新 agent 接手時，不用再從零補課你的工作方式與上下文。" },
];

const leftLabels = [
  { title: "Spec", subtitle: "決策 / 文件 / 討論", top: "15%", left: "0%" },
  { title: "Module", subtitle: "產品結構", top: "50%", left: "-5%" },
  { title: "Role", subtitle: "誰該知道", top: "85%", left: "5%" },
];

const rightLabels = [
  { title: "Impact", subtitle: "誰會被影響", top: "20%", right: "0%" },
  { title: "Blindspot", subtitle: "哪裡還沒補齊", top: "55%", right: "-5%" },
  { title: "Action", subtitle: "AI 怎麼開始做事", top: "85%", right: "5%" },
];

export default function HomePage() {
  return (
    <main id="main-content" className="relative min-h-screen overflow-hidden text-foreground bg-[#040A12]">
      {/* Dynamic Background */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent" />
        <div className="absolute -left-[10%] top-0 h-[500px] w-[500px] rounded-full bg-primary/10 blur-[120px] animate-pulse" />
        <div className="absolute right-[0%] top-[20%] h-[600px] w-[600px] rounded-full bg-cyan-700/10 blur-[150px] animate-pulse" style={{ animationDelay: '1s' }} />
        <div className="absolute bottom-0 left-[20%] h-[400px] w-[400px] rounded-full bg-blue-600/10 blur-[100px] animate-pulse" style={{ animationDelay: '2s' }} />
      </div>

      <section className="relative mx-auto flex min-h-screen w-full max-w-7xl flex-col px-6 pb-20 pt-8 lg:px-12">
        <header className="flex items-center justify-between py-4 backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-3xl px-6 mb-12 shadow-[0_4px_30px_rgba(0,0,0,0.1)]">
          <Link href="/" className="flex items-center gap-4 group">
            <div className="relative">
              <div className="absolute inset-0 rounded-2xl bg-primary/20 blur-md group-hover:bg-primary/40 transition-colors" />
              <img
                src="/brand/zenos-mark.png"
                alt="ZenOS brand mark"
                width={44}
                height={44}
                className="relative h-11 w-11 rounded-2xl object-cover object-left border border-white/10"
              />
            </div>
            <div className="flex flex-col">
              <p className="text-sm font-bold uppercase tracking-[0.28em] text-white bg-clip-text text-transparent bg-gradient-to-r from-white to-white/70">ZenOS</p>
              <p className="mt-0.5 text-[10px] uppercase tracking-[0.2em] text-primary/80">
                context before execution
              </p>
            </div>
          </Link>

          <div className="flex items-center gap-6">
            <Link
              href="/login"
              className="hidden text-sm font-medium tracking-wide text-muted-foreground transition-colors hover:text-white sm:inline-flex"
            >
              登入
            </Link>
            <Link
              href="/login"
              className="group relative inline-flex items-center justify-center overflow-hidden rounded-full py-2.5 px-6 font-medium text-white"
            >
              <div className="absolute inset-0 border border-primary/30 rounded-full bg-white/5" />
              <span className="relative text-sm tracking-wide flex items-center gap-2 text-slate-100">
                接受邀請 <Zap className="size-3.5 text-primary/80" />
              </span>
            </Link>
          </div>
        </header>

        <div className="grid flex-1 items-center gap-16 lg:grid-cols-[1fr_1.2fr] lg:gap-24">
          <div className="max-w-2xl flex flex-col justify-center">
            <div className="inline-flex w-fit items-center gap-2.5 rounded-full border border-primary/30 bg-primary/[0.03] px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.2em] text-primary backdrop-blur-sm shadow-[0_0_20px_rgba(54,225,202,0.1)]">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
              </span>
              AI Context Layer
            </div>

            <h1 className="mt-8 text-5xl font-bold leading-[1.05] tracking-tight text-white sm:text-6xl lg:text-[5.5rem] bg-clip-text text-transparent bg-gradient-to-br from-white via-white/90 to-white/60">
              先讓 AI
              <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-cyan-300 to-blue-400 drop-shadow-[0_0_30px_rgba(54,225,202,0.3)]">看懂你的脈絡</span>，
              <br />
              再讓它做事。
            </h1>

            <p className="mt-8 max-w-xl text-lg leading-relaxed text-slate-300/90 font-light">
              ZenOS 不是另一個文件庫。它把散落在文件、決策、對話與任務裡的內容，
              先整理成一張<span className="text-primary font-medium">可被 AI 使用的工作知識圖</span>。
            </p>

            <div className="mt-10 flex flex-col gap-4 sm:flex-row">
              <Link
                href="/knowledge-map"
                className="group relative inline-flex items-center justify-center gap-3 rounded-full bg-primary px-8 py-4 text-sm font-bold text-primary-foreground transition-all hover:bg-primary/90 hover:shadow-[0_0_40px_rgba(54,225,202,0.4)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                探索 Knowledge Map
                <ArrowRight className="size-4 transition-transform group-hover:translate-x-1" />
              </Link>
              <Link
                href="/login"
                className="inline-flex flex-1 sm:flex-none items-center justify-center rounded-full border border-white/10 bg-white/5 backdrop-blur-sm px-8 py-4 text-sm font-bold text-white transition-colors hover:bg-white/10"
              >
                登入或接受邀請
              </Link>
            </div>

            <div className="mt-14 space-y-5 border-t border-white/10 pt-8">
              {evidence.map((item, idx) => {
                const Icon = item.icon;
                return (
                  <div key={idx} className="flex items-center gap-4 group">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-primary/20 bg-primary/5 text-primary transition-all group-hover:bg-primary/20 group-hover:scale-110">
                      <Icon className="size-5" />
                    </div>
                    <p className="text-[15px] font-medium leading-relaxed text-slate-300 group-hover:text-white transition-colors">{item.text}</p>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="relative w-full h-[600px] lg:h-[700px] flex items-center justify-center">
            {/* Holographic backdrop */}
            <div className="absolute inset-0 rounded-[3rem] border border-white/10 bg-gradient-to-br from-[#0a1726]/80 to-[#040A12]/90 backdrop-blur-3xl shadow-[0_0_80px_rgba(0,0,0,0.6)] overflow-hidden">
               {/* Grid overlay */}
               <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_50%,#000_70%,transparent_100%)]" />
               <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-400/30 to-transparent" />
            </div>

            <div className="relative w-full h-full p-8 flex items-center justify-center">
              <div className="absolute inset-x-0 top-8 flex items-center justify-between px-8 z-20">
                <div className="backdrop-blur-md bg-black/20 rounded-2xl p-3 border border-white/5">
                  <p className="text-xs font-bold uppercase tracking-[0.25em] text-primary/70 mb-1">
                  Context topology
                  </p>
                  <p className="text-sm font-medium text-slate-200">
                    文件不是重點，<span className="text-primary border-b border-primary/30 pb-0.5">關聯才是</span>。
                  </p>
                </div>
                <div className="flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 backdrop-blur-md px-4 py-2 text-xs font-bold uppercase tracking-[0.2em] text-primary shadow-[0_0_15px_rgba(54,225,202,0.15)]">
                  <Network className="size-3.5" />
                  Graph Core
                </div>
              </div>

              <div className="relative w-full max-w-[600px] aspect-square">
                {/* Central glowing background orb */}
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(54,225,202,0.08),transparent_50%)] animate-pulse" style={{ animationDuration: '4s' }} />
                
                {leftLabels.map((item, i) => (
                  <LabelPill key={item.title} align="left" index={i} {...item} />
                ))}
                {rightLabels.map((item, i) => (
                  <LabelPill key={item.title} align="right" index={i + 3} {...item} />
                ))}

                {/* Core Element */}
                <div className="absolute left-1/2 top-1/2 h-36 w-36 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-primary/40 bg-[#081b2c]/80 backdrop-blur-xl shadow-[0_0_60px_rgba(54,225,202,0.25)] flex flex-col items-center justify-center z-20 group hover:scale-105 transition-transform duration-500 hover:border-primary/60 hover:shadow-[0_0_80px_rgba(54,225,202,0.5)] cursor-default">
                  <div className="absolute inset-0 rounded-full border border-white/5 animate-[spin_10s_linear_infinite]" />
                  <p className="text-[11px] font-bold uppercase tracking-[0.3em] text-primary drop-shadow-[0_0_8px_rgba(54,225,202,0.8)]">ZenOS</p>
                  <p className="mt-2 text-xl font-bold text-white tracking-wide">Ontology</p>
                  <p className="mt-1 text-[10px] uppercase font-semibold text-cyan-200/60 tracking-widest">what / why / how / who</p>
                </div>

                <svg
                  viewBox="0 0 760 760"
                  className="absolute inset-0 h-full w-full z-10 pointer-events-none"
                  aria-hidden="true"
                >
                  <defs>
                    <radialGradient id="nodeGlow" cx="50%" cy="50%" r="50%">
                      <stop offset="0%" stopColor="rgba(54,225,202,1)" />
                      <stop offset="100%" stopColor="rgba(54,225,202,0)" />
                    </radialGradient>
                    <filter id="glow">
                      <feGaussianBlur stdDeviation="3" result="coloredBlur" />
                      <feMerge>
                        <feMergeNode in="coloredBlur" />
                        <feMergeNode in="SourceGraphic" />
                      </feMerge>
                    </filter>
                  </defs>

                  <g fill="none" stroke="rgba(148,163,184,0.15)" strokeWidth="1.5">
                     <path className="graph-line" d="M380 380 L180 180" />
                     <path className="graph-line graph-line-2" d="M380 380 L140 380" />
                     <path className="graph-line graph-line-3" d="M380 380 L180 580" />
                     <path className="graph-line graph-line-4" d="M380 380 L580 180" />
                     <path className="graph-line graph-line-5" d="M380 380 L620 380" />
                     <path className="graph-line graph-line-6" d="M380 380 L580 580" />
                     <path className="graph-line graph-line-7" d="M180 180 Q 280 120 580 180" />
                     <path className="graph-line graph-line-8" d="M580 580 Q 480 640 180 580" />
                  </g>

                  {/* Flowing signals */}
                  <g stroke="rgba(54,225,202,0.8)" strokeWidth="2.5" strokeLinecap="round" filter="url(#glow)">
                    <path className="graph-signal graph-signal-1" d="M380 380 L180 180" />
                    <path className="graph-signal graph-signal-2" d="M380 380 L620 380" />
                    <path className="graph-signal graph-signal-3" d="M380 380 L580 580" />
                    <path className="graph-signal graph-signal-4" d="M140 380 L380 380" />
                  </g>

                  {/* Nodes */}
                  <g>
                    <circle cx="180" cy="180" r="10" fill="#7dd3fc" className="graph-node graph-node-a" filter="url(#glow)" />
                    <circle cx="140" cy="380" r="8" fill="#cbd5e1" className="graph-node graph-node-b" />
                    <circle cx="180" cy="580" r="10" fill="#a5f3fc" className="graph-node graph-node-c" filter="url(#glow)" />
                    <circle cx="580" cy="180" r="12" fill="#36e1ca" className="graph-node graph-node-d" filter="url(#glow)" />
                    <circle cx="620" cy="380" r="9" fill="#fde68a" className="graph-node graph-node-e" filter="url(#glow)" />
                    <circle cx="580" cy="580" r="10" fill="#7dd3fc" className="graph-node graph-node-a" />
                    
                    {/* Center Core outer point */}
                    <circle cx="380" cy="380" r="14" fill="#36e1ca" filter="url(#glow)" />
                  </g>

                  <g opacity="0.6">
                    <circle cx="380" cy="380" r="85" fill="url(#nodeGlow)" className="graph-core-glow" />
                  </g>
                </svg>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Problem & Solution */}
      <section className="relative mx-auto max-w-7xl px-6 py-24 lg:px-12 z-10">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold tracking-tight text-white mb-4">為什麼知識工作者需要 <span className="text-primary">Context Layer</span>？</h2>
          <p className="text-lg text-slate-400">當你同時和夥伴、文件、agent 一起工作，靠記憶和臨時補充已經不夠用了。</p>
        </div>
        <div className="grid md:grid-cols-2 gap-8 max-w-5xl mx-auto">
          <div className="rounded-3xl bg-red-950/20 border border-red-500/20 p-8 shadow-[0_0_30px_rgba(239,68,68,0.05)]">
            <h3 className="text-red-400 text-lg font-bold mb-6 flex items-center gap-3"><XCircle className="size-6" /> 傳統作法：文件即墳墓</h3>
            <ul className="space-y-4 text-slate-300">
              <li className="flex items-start gap-3"><span className="text-red-500 mt-1 pb-1">◆</span> <div><span className="text-white font-medium">Spec 永遠跟不上實作：</span>散落各處的文件難以維護，最後只剩你自己知道脈絡。</div></li>
              <li className="flex items-start gap-3"><span className="text-red-500 mt-1 pb-1">◆</span> <div><span className="text-white font-medium">改 A 壞 B：</span>只看眼前的 Ticket，看不見背後的牽連與 Why。</div></li>
              <li className="flex items-start gap-3"><span className="text-red-500 mt-1 pb-1">◆</span> <div><span className="text-white font-medium">AI 給出通用廢話：</span>模型缺乏你的專案脈絡，做不出真正貼近現況的判斷。</div></li>
            </ul>
          </div>
          <div className="rounded-3xl bg-primary/10 border border-primary/20 p-8 shadow-[0_0_30px_rgba(54,225,202,0.1)] relative overflow-hidden">
            <div className="absolute -right-10 -top-10 w-40 h-40 bg-primary/20 blur-3xl rounded-full" />
            <h3 className="text-primary text-lg font-bold mb-6 flex items-center gap-3"><CheckCircle2 className="size-6" /> ZenOS 做法：知識即圖譜</h3>
            <ul className="space-y-4 text-slate-300 relative z-10">
              <li className="flex items-start gap-3"><span className="text-primary mt-1 pb-1">◇</span> <div><span className="text-white font-medium">Capture & Sync：</span>主動在對話、討論與 Commit 過程中捕捉決策片段。</div></li>
              <li className="flex items-start gap-3"><span className="text-primary mt-1 pb-1">◇</span> <div><span className="text-white font-medium">全域關聯分析：</span>即時顯示需求變更對其它模組與角色的影響範圍。</div></li>
              <li className="flex items-start gap-3"><span className="text-primary mt-1 pb-1">◇</span> <div><span className="text-white font-medium">賦予 AI 長期記憶：</span>提供標準化 MCP 介面，讓 Agent 接手任務前先載入你的工作脈絡。</div></li>
            </ul>
          </div>
        </div>
      </section>

      {/* How it Works */}
      <section className="relative mx-auto max-w-7xl px-6 py-24 lg:px-12 z-10 bg-white/[0.02] border-y border-white/5 my-12">
        <div className="text-center mb-20">
          <h2 className="text-3xl font-bold tracking-tight text-white mb-4">How it Works</h2>
          <p className="text-lg text-slate-400">從分散的隱性知識，到可持續的人機協作</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-12 relative max-w-5xl mx-auto">
          <div className="hidden md:block absolute top-[45px] left-[18%] right-[18%] h-0.5 bg-gradient-to-r from-primary/10 via-primary/40 to-primary/10 z-0" />
          
          <div className="relative z-10 flex flex-col items-center text-center">
            <div className="w-16 h-16 rounded-full bg-[#0a1726] border border-primary/30 flex items-center justify-center text-primary text-xl font-bold mb-6 shadow-[0_0_30px_rgba(54,225,202,0.15)] ring-4 ring-[#040A12]">1</div>
            <h3 className="text-xl font-bold text-white mb-3">連接與擷取</h3>
            <p className="text-sm leading-relaxed text-slate-400">綁定你的程式碼與知識來源。透過 AI Agent 在日常工作流中擷取有價值的設計原則與決策背景。</p>
          </div>
          
          <div className="relative z-10 flex flex-col items-center text-center">
            <div className="w-16 h-16 rounded-full bg-[#0a1726] border border-primary/30 flex items-center justify-center text-primary text-xl font-bold mb-6 shadow-[0_0_30px_rgba(54,225,202,0.15)] ring-4 ring-[#040A12]">2</div>
            <h3 className="text-xl font-bold text-white mb-3">建構本體結構</h3>
            <p className="text-sm leading-relaxed text-slate-400">ZenOS 分析關聯，將原始資料轉換成 L1/L2 Ontology。理解誰需要什麼資訊來完成哪段工作。</p>
          </div>

          <div className="relative z-10 flex flex-col items-center text-center">
            <div className="w-16 h-16 rounded-full bg-[#0a1726] border border-primary/30 flex items-center justify-center text-primary text-xl font-bold mb-6 shadow-[0_0_30px_rgba(54,225,202,0.15)] ring-4 ring-[#040A12]">3</div>
            <h3 className="text-xl font-bold text-white mb-3">執行與任務分配</h3>
            <p className="text-sm leading-relaxed text-slate-400">將圖譜轉為 Task，並派發給你、夥伴或代理工具。任何 AI Agent 接手任務時，都能自動注入完整上下文。</p>
          </div>
        </div>
      </section>

      {/* Alternating Features Deep Dive */}
      <section className="relative overflow-hidden py-24 sm:py-32 z-10">
        <div className="mx-auto max-w-7xl px-6 lg:px-12">
           {/* Feature Row 1 */}
           <div className="mx-auto grid max-w-2xl grid-cols-1 gap-x-16 gap-y-16 sm:gap-y-20 lg:mx-0 lg:max-w-none lg:grid-cols-2 items-center mb-32">
             <div>
               <div className="flex items-center gap-2 text-primary text-sm font-semibold mb-4 tracking-widest uppercase"><Search className="size-4" /> Impact Analysis</div>
               <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">在寫 Code 前，<br/>先看見全域影響鏈。</h2>
               <p className="mt-6 text-lg leading-8 text-slate-300">傳統的 Ticket 只告訴你「修這個 Bug」。ZenOS 會多告訴你：「如果你改了認證模組，會影響哪些流程、文件與後續任務。」</p>
               <ul className="mt-8 space-y-4 text-slate-400">
                 <li className="flex gap-3"><CheckCircle2 className="text-primary size-5 shrink-0" /> <span className="flex-1">自動追蹤跨模組的相依性關係</span></li>
                 <li className="flex gap-3"><CheckCircle2 className="text-primary size-5 shrink-0" /> <span className="flex-1">提前預警架構決策帶來的 Side Effect</span></li>
               </ul>
             </div>
             <div className="relative bg-[#0d1c29] border border-white/10 rounded-2xl shadow-[0_0_50px_rgba(0,0,0,0.6)] overflow-hidden">
               <div className="h-10 border-b border-white/10 bg-black/40 flex items-center px-4 gap-2">
                 <div className="flex gap-1.5"><div className="w-3 h-3 rounded-full bg-red-500/50"/><div className="w-3 h-3 rounded-full bg-yellow-500/50"/><div className="w-3 h-3 rounded-full bg-green-500/50"/></div>
                 <div className="mx-auto bg-black/60 text-[11px] font-mono text-slate-400 px-4 py-1 rounded flex items-center gap-2">Visualizer — Impacts <span className="bg-primary/20 text-primary px-1.5 py-0.5 rounded text-[9px] uppercase tracking-wider">即將推出</span></div>
               </div>
               <div className="p-8 aspect-video flex flex-col items-center justify-center relative bg-[radial-gradient(ellipse_at_center,rgba(54,225,202,0.05),transparent)]">
                 <div className="flex items-center gap-3">
                   <div className="animate-pulse bg-cyan-900/40 border border-cyan-500/30 text-cyan-200 px-4 py-2 rounded-lg text-sm">Auth Module</div>
                   <ArrowRight className="text-slate-600 size-4" />
                   <div className="bg-primary/20 border border-primary/40 text-primary-foreground px-4 py-2 rounded-lg text-sm drop-shadow-[0_0_15px_rgba(54,225,202,0.5)] scale-110 font-bold">Billing Core</div>
                   <ArrowRight className="text-slate-600 size-4" />
                   <div className="bg-orange-900/40 border border-orange-500/30 text-orange-200 px-4 py-2 rounded-lg text-sm">Invoice Spec</div>
                 </div>
                 <div className="absolute bottom-6 bg-black/70 border border-red-500/20 p-4 rounded-xl text-xs text-slate-300 w-[85%] backdrop-blur-md shadow-2xl">
                    <span className="text-red-400 font-bold block mb-1">⚠️ Ripple Effect Warning</span>
                    Changing Auth format invalidates data assumptions in [Invoice Spec] for [Finance Role].
                 </div>
               </div>
             </div>
           </div>

           {/* Feature Row 2 */}
           <div className="mx-auto grid max-w-2xl grid-cols-1 gap-x-16 gap-y-16 sm:gap-y-20 lg:mx-0 lg:max-w-none lg:grid-cols-2 items-center mb-32">
             <div className="order-2 lg:order-1 relative bg-[#07131e] border border-white/10 rounded-2xl shadow-[0_0_50px_rgba(0,0,0,0.6)] overflow-hidden flex flex-col">
               <div className="h-10 border-b border-white/10 bg-black/40 flex items-center px-4 gap-2">
                 <div className="flex gap-1.5"><div className="w-3 h-3 rounded-full bg-red-500/50"/><div className="w-3 h-3 rounded-full bg-yellow-500/50"/><div className="w-3 h-3 rounded-full bg-green-500/50"/></div>
                 <div className="mx-auto bg-black/60 text-[11px] font-mono text-slate-400 px-4 py-1 rounded">Agent Terminal</div>
               </div>
               <div className="p-8 font-mono text-xs md:text-sm leading-relaxed text-slate-400 aspect-video flex flex-col justify-center">
                  <div className="mb-2 text-cyan-400">❯ /api/mcp/zenos analyze context --task "OAuth Setup"</div>
                  <div className="mb-4 text-slate-500 animate-pulse">Querying internal knowledge graph...</div>
                  <div className="mb-2 pl-4 border-l-2 border-primary/40 bg-primary/5 p-3 rounded-r-lg">
                    <span className="text-primary font-bold">Context Loaded:</span>
                    <br />• Policy: Adhere to strict GDPR standards (L1)
                    <br />• Technical limits: DB limits concurrent writes to 5k/sec
                    <br />• Past failure: Avoid Redis token cache structure from v1.2
                  </div>
                  <div className="text-green-400 mt-4 font-bold">✓ Ready. Generating implementation plan...</div>
               </div>
             </div>
             <div className="order-1 lg:order-2">
               <div className="flex items-center gap-2 text-primary font-semibold text-sm mb-4 tracking-widest uppercase"><Zap className="size-4" /> Agent Connectivity</div>
               <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">賦予 AI 真正的<br/>「工作記憶」。</h2>
               <p className="mt-6 text-lg leading-8 text-slate-300">通用型語言模型很懂寫程式，但不懂你的專案脈絡。透過 ZenOS 提供的 Model Context Protocol (MCP)，能讓你專屬的 Agent 在執行任務前，秒速擷取所有相關的決策與設計原則。</p>
               <div className="mt-8 flex flex-wrap gap-3">
                 <span className="px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs text-slate-300">Claude Code</span>
                 <span className="px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs text-slate-300">MCP Client</span>
                 <span className="px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs text-slate-300">AI Agents</span>
               </div>
             </div>
           </div>

           {/* Feature Row 3 Persona */}
           <div className="mx-auto grid max-w-2xl grid-cols-1 gap-x-16 gap-y-16 sm:gap-y-20 lg:mx-0 lg:max-w-none lg:grid-cols-2 items-center">
             <div>
               <div className="flex items-center gap-2 text-primary font-semibold text-sm mb-4 tracking-widest uppercase"><Users className="size-4" /> Designed for Personal Collaboration</div>
               <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">先服務個人工作流，<br/>再自然延伸到協作。</h2>
               <p className="mt-6 text-lg leading-8 text-slate-300">ZenOS 先幫你整理自己的脈絡，再把同一套上下文分享給夥伴與 agent。你不用每次重新交接，協作也不必從頭對齊。</p>
             </div>
             <div className="grid gap-6">
                <div className="flex gap-4 p-6 rounded-2xl bg-white/[0.02] border border-white/5 hover:border-primary/30 transition-colors">
                  <div className="h-10 w-10 shrink-0 bg-blue-500/10 text-blue-400 rounded-xl flex items-center justify-center"><Radar className="size-5" /></div>
                  <div>
                    <h3 className="text-white font-bold mb-1">Solo Builder</h3>
                    <p className="text-sm text-slate-400">把規格、決策、待辦和歷史脈絡收成同一張圖，不用每次切回腦內搜尋。</p>
                  </div>
                </div>
                <div className="flex gap-4 p-6 rounded-2xl bg-white/[0.02] border border-white/5 hover:border-primary/30 transition-colors">
                  <div className="h-10 w-10 shrink-0 bg-indigo-500/10 text-indigo-400 rounded-xl flex items-center justify-center"><Network className="size-5" /></div>
                  <div>
                    <h3 className="text-white font-bold mb-1">Small Team</h3>
                    <p className="text-sm text-slate-400">把共享脈絡交給系統維護，避免資訊只卡在某一個人腦中。</p>
                  </div>
                </div>
                <div className="flex gap-4 p-6 rounded-2xl bg-white/[0.02] border border-white/5 hover:border-primary/30 transition-colors">
                  <div className="h-10 w-10 shrink-0 bg-primary/10 text-primary rounded-xl flex items-center justify-center"><ShieldCheck className="size-5" /></div>
                  <div>
                    <h3 className="text-white font-bold mb-1">AI Copilot</h3>
                    <p className="text-sm text-slate-400">在開始動手前先載入背景、限制與影響鏈，回應更貼近你的真實工作環境。</p>
                  </div>
                </div>
             </div>
           </div>

        </div>
      </section>

      {/* CTA Section */}
      <section className="relative z-10 mx-auto max-w-5xl px-6 py-24">
        <div className="relative overflow-hidden rounded-[3rem] border border-primary/20 bg-gradient-to-b from-primary/10 to-[#040A12] px-8 py-16 text-center shadow-[0_0_60px_rgba(54,225,202,0.15)] md:px-16 md:py-20 lg:p-24">
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent" />
          <h2 className="mx-auto max-w-2xl text-3xl font-bold tracking-tight text-white sm:text-4xl">
            準備好讓 AI 真正為你的工作流協作了嗎？
          </h2>
          <p className="mx-auto mt-6 max-w-xl text-lg leading-8 text-slate-300">
            不用再手動複製貼上背景脈絡。登入後，讓你的 workspace、夥伴與 agent 共用同一份上下文。
          </p>
          <div className="mt-10 flex items-center justify-center gap-x-6">
            <Link
              href="/login"
              className="group relative inline-flex items-center justify-center rounded-full bg-primary px-8 py-4 text-sm font-bold text-primary-foreground transition-all hover:bg-primary/90 hover:shadow-[0_0_40px_rgba(54,225,202,0.4)]"
            >
              立即登入 <Zap className="ml-2 size-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-white/5 bg-black/20 mt-12 py-12">
        <div className="mx-auto max-w-7xl px-6 flex flex-col items-center justify-between gap-6 md:flex-row lg:px-12">
          <div className="flex items-center gap-3 opacity-80">
            <img src="/brand/zenos-mark.png" alt="" className="h-6 w-6 rounded-md object-cover grayscale" />
            <span className="text-sm font-bold tracking-widest text-slate-400">ZENOS</span>
          </div>
          <p className="text-xs text-slate-500">
            &copy; {new Date().getFullYear()} ZenOS. Building the context layer for personal AI collaboration.
          </p>
        </div>
      </footer>
    </main>
  );
}

function LabelPill({
  title,
  subtitle,
  top,
  left,
  right,
  align,
  index,
}: {
  title: string;
  subtitle: string;
  top: string;
  left?: string;
  right?: string;
  align: "left" | "right";
  index: number;
}) {
  return (
    <div
      className={`absolute z-30 w-48 rounded-2xl border border-white/10 bg-black/40 backdrop-blur-xl px-4 py-3 shadow-[0_8px_32px_rgba(0,0,0,0.3)] transition-all duration-500 hover:scale-105 hover:bg-black/60 hover:border-primary/40 ${
        align === "right" ? "text-right" : "text-left"
      }`}
      style={{ 
        top, 
        left, 
        right,
      }}
    >
      <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-white/[0.05] to-transparent pointer-events-none" />
      <p className="relative text-[10px] font-bold uppercase tracking-[0.25em] text-primary/90 drop-shadow-sm">{title}</p>
      <p className="relative mt-1.5 text-sm font-semibold text-slate-100">{subtitle}</p>
    </div>
  );
}
