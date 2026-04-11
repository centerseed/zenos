---
type: REFERENCE
id: REF-zentropy-competitive-analysis-v5_1
status: Draft
ontology_entity: Zentropy
created: 2026-04-10
updated: 2026-04-10
---

# Zentropy Competitive Analysis v5.1

> Scope: 本文件以 `SPEC-zentropy-v5_1-product-definition` 與 `SPEC-zentropy-v5-product-reinforcement` 為準，分析新的 Zentropy 定義在市場上會被拿來和誰比較、差異實際來自哪裡、以及哪些空位值得主動佔領。

## 分析前提

新的 Zentropy 定義，不再是：

- AI todo list
- AI note app
- consumer 版 ZenOS

而是：

> **幫 AI-Native 工作者把工作背景留住，讓下一次不用從零開始。**

因此，競品分析不能只按傳統「任務管理 / 筆記工具 / AI agent」分類，而要按使用者真正會拿來替代的解法分類：

1. 我現在用什麼來接住腦中碎片？
2. 我現在用什麼來管理 ongoing work？
3. 我現在用什麼來保留 AI 工作背景？
4. 我現在用什麼來讓團隊不要各說各話？

## Spec 相容性

已比對：

- `SPEC-zentropy-v5_1-product-definition`
- `SPEC-zentropy-v5-product-reinforcement`
- `REF-competitive-landscape`
- `REF-market-insights`

結論：

- `REF-competitive-landscape` 與 `REF-market-insights` 主要是 ZenOS 視角，聚焦 ontology / context layer / MCP 基礎設施。
- 本文件改用 Zentropy 視角，聚焦 front product、替代品心智與市場 wedge。
- 兩者不衝突，但比較對象與勝負標準不同。

## 核心判斷

Zentropy 最容易被拿來比較的，不是 ZenOS 的那些 ontology 玩家，而是這四群產品：

1. `Todo / PM tools`
2. `AI + notes / PKM tools`
3. `Connected workspace / wiki + projects tools`
4. `AI memory infrastructure`

真正的風險不是某一家直接把 Zentropy 做掉，而是：

> 使用者覺得「我把 Todoist、Notion、Obsidian、Claude 搭起來就夠了」。

所以 Zentropy 的戰場不是功能 completeness，而是：

- 是否能比拼裝方案更少流失 context
- 是否能比單點工具更自然地把背景接到行動上
- 是否能在不增加太多心智負擔的前提下，讓 AI 真的有 continuity

## 競品地圖

## 官方定位快照（2026-04-10）

以下是本次分析對照的官方主敘事摘要：

- `Todoist`：主打 to-do list、task/project/time management，強調快速 capture、自然語言輸入、shared team tasks。
- `Notion`：主打 AI workspace，將 knowledge base、docs、projects、AI tools for work 放在同一工作空間。
- `Obsidian`：主打 private thoughts、free and flexible、本地優先筆記與插件生態。
- `Tana`：目前首頁主打 meetings 與自動形成的 context graph，強調 discussions、decisions 與後續工作連在一起。
- `Linear`：主打 product development system for teams and agents，聚焦 planning/building products。
- `Mem0`：主打 AI memory layer，明確服務 LLM applications 與 personalized AI experiences。
- `Zep`：主打 context engineering / agent memory，強調從 chat history、business data、user behavior 組裝 agent context。

這些主敘事支持一個判斷：

> Zentropy 若只講 AI、知識、任務，會被吸回現有品類；只有當它把 `work continuity` 講清楚，市場位置才會真正獨立。

### 第一圈：使用者最直覺的替代方案

#### 1. Todoist

- 官方主張：快速 capture task、自然語言輸入、優先序、跨裝置同步、團隊共享專案與 AI assist。
- 使用者怎麼看它：最輕量、最成熟、最低學習成本的 task manager。
- 真正威脅：
  - Zentropy 如果只強調 Brain Dump + task，就會直接落到 Todoist 賽道。
  - Todoist 的優勢不是 AI，而是低 friction 與清楚心智。
- Zentropy 的差異：
  - Todoist 管「要做什麼」。
  - Zentropy 必須管「為什麼會有這件事」與「下次 AI 能否接續」。
- 不能硬打的點：
  - 排程完整度
  - 清單成熟度
  - 普適性

#### 2. Notion

- 官方主張：wiki、docs、projects 在同一個 connected workspace；AI 協助寫作、research、database autofill、task/project 管理。
- 使用者怎麼看它：一個地方做文件、知識、專案、任務。
- 真正威脅：
  - 對很多小團隊來說，Notion 已經是「背景 + 專案 + 協作」的預設答案。
  - 如果 Zentropy 講不清楚，它會被當成較窄的 Notion 外掛。
- Zentropy 的差異：
  - Notion 的 source of truth 是 workspace/document/database。
  - Zentropy 應該把 source of truth 放在 ongoing work context 與 AI continuity。
  - Notion 擅長把 knowledge 和 project 並排。
  - Zentropy 必須擅長讓 AI 在每次行動時都吃到對的背景。
- 不能硬打的點：
  - 通用工作空間
  - 文件編輯器
  - 可配置資料庫

#### 3. Obsidian

- 官方主張：Markdown knowledge base、本地優先、資料自有、雙向連結、圖譜視圖、插件生態。
- 使用者怎麼看它：第二大腦、個人知識管理、私人且可塑。
- 真正威脅：
  - 新的 Zentropy 很容易被理解成「AI + Obsidian」。
  - 這個比較一旦成立，Zentropy 會被要求在資料 ownership、插件、生態自由度上正面硬碰。
- Zentropy 的差異：
  - Obsidian 的重心是 knowledge possession。
  - Zentropy 的重心應該是 knowledge-in-use。
  - Obsidian 幫你把想法留下來。
  - Zentropy 要幫你在工作進行中，把正確背景帶進下一步。
- 不能硬打的點：
  - 本地檔案所有權
  - 外掛生態
  - 通用筆記自由度

### 第二圈：理念相近但心智不同的產品

#### 4. Tana

- 官方主張：knowledge graph、outline editor、supertags、AI、notes/tasks/projects 都在同一個 graph 上。
- 使用者怎麼看它：更 AI-native、更 graph-native 的個人知識工作台。
- 真正威脅：
  - Tana 已經很接近「notes turn into action」的敘事。
  - 它對重度 PKM / AI 工作流用戶很有吸引力。
- Zentropy 的差異：
  - Tana 是 graph-native workspace。
  - Zentropy 應該是 work-context-native product。
  - Tana 主要幫用戶在單一系統內結構化知識與工作。
  - Zentropy 的 wedge 應是跨 AI 工具、跨時間、跨角色的 continuity。
- 贏面：
  - 更直接的工作承諾
  - 更低的 graph 學習負擔
  - 更清楚的「不用再重講背景」心智
- 輸面：
  - 若產品做得太像圖譜/結構工具，會落到 Tana 更成熟的心智區

#### 5. Linear

- 官方主張：issues、projects、cycles、triage，為產品與工程團隊提供高效執行系統。
- 使用者怎麼看它：最乾淨、最快、最成熟的 execution OS。
- 真正威脅：
  - 在工程團隊內，任何「更懂背景的 task 工具」都會被拿去和 Linear 比。
- Zentropy 的差異：
  - Linear 最強在 execution clarity。
  - Zentropy 若要贏，不是更快開 issue，而是讓 issue 前後的 context 不蒸發。
- 不能硬打的點：
  - issue workflow 完整度
  - 工程團隊操作速度
  - PM/Eng pipeline 標準化

### 第三圈：底層能力相似，但購買者不同

#### 6. Mem0 / Zep

- 官方主張：AI memory layer、session/user/org memory、graph memory、讓 agent 有長期記憶。
- 使用者怎麼看它：給產品或 agent builder 的 memory infrastructure。
- 真正威脅：
  - 它們驗證了「continuity / memory」需求是真實的。
  - 但它們也可能讓懂技術的用戶覺得「自己接 memory layer 就好，不需要 Zentropy」。
- Zentropy 的差異：
  - Mem0 / Zep 賣給 builder。
  - Zentropy 賣給 end user / prosumer / micro team。
  - Mem0 / Zep 解的是 agent context persistence。
  - Zentropy 應解的是 human + AI shared work continuity。
- 結論：
  - 它們更像 enabling substitutes，而不是直接產品競品。

## 競爭不是一條線，而是四種心智競爭

### 心智 1：`我只需要把事情記下來`

代表替代品：

- Todoist
- Apple Reminders
- Notion tasks

Zentropy 要贏，不能說「我也能記 task」，而要說：

> 我不只記 task，我幫你保留 task 的背景，讓 AI 下次還知道為什麼。

### 心智 2：`我需要一個地方整理知識`

代表替代品：

- Obsidian
- Tana
- Heptabase

Zentropy 要贏，不能說「我也有知識地圖」，而要說：

> 我不是拿來收藏知識，我是拿來避免工作中的背景斷裂。

### 心智 3：`我想把專案和文件放在一起`

代表替代品：

- Notion
- ClickUp
- Asana

Zentropy 要贏，不能說「我也有 projects + docs」，而要說：

> 我讓 AI 與人每次開始工作時，拿到的是同一份最新背景。

### 心智 4：`我需要讓 agent 有記憶`

代表替代品：

- Mem0
- Zep
- 自建 memory stack

Zentropy 要贏，不能說「我也有 memory」，而要說：

> 我不是 memory infra，我是把記憶變成可被人直接感知的工作連續性。

## 接上 ZenOS 後，Zentropy 真正放大的差異

如果沒有 ZenOS，Zentropy 很容易被看成：

- 比較聰明的 todo list
- 比較有結構的 AI note app

接上 ZenOS 後，差異才變成結構性的：

### 1. 從 `capture tool` 升級成 `continuity system`

競品大多停在 capture / organize / retrieve。

Zentropy 可以往前走一步：

- capture 背景
- 把背景附到行動
- 讓結果再回寫背景

這是閉環，不是收納。

### 2. 從 `single-user knowledge` 升級成 `shared reality`

大多數 PKM 工具的強項仍然偏單人。

Zentropy 接上 ZenOS 後，可以自然發展成：

- 共享 current narrative
- 共享 decision context
- 共享 task rationale

這是團隊 AI 時代真正更稀缺的層。

### 3. 從 `AI memory` 升級成 `human-AI alignment`

一般 memory layer 只處理 agent 記住什麼。

Zentropy 更大的價值是處理：

- 人腦中的背景
- AI 對背景的理解
- 團隊對背景的共同版本

這比單純讓 agent 記得 user preference 更高一層。

## 市場還沒被明確佔住的空位

### 空位 1：Cross-AI Working Memory for end users

現在市場上已經有：

- 單一 AI 的 chat history
- 開發者用的 memory infra
- 個人的筆記/知識圖譜工具

但還很少有產品把這件事包裝成一個簡單承諾：

> 不管你用了哪個 AI，下一次都不用重講背景。

這是 Zentropy 最值得先搶的 wedge。

### 空位 2：Context-first work OS for micro teams

小團隊常見現況是：

- 任務在一個地方
- 文件在一個地方
- AI 在很多地方

但沒有一個產品以「團隊共享背景」作為主售點。

Notion 比較像 shared workspace。  
Linear 比較像 execution system。  
Obsidian/Tana 比較像 knowledge system。  
Zentropy 可以切入：

> shared context for ongoing work

### 空位 3：From AI productivity to AI continuity

現在大多數 AI productivity 產品賣的是：

- 更快
- 更自動
- 更少手動輸入

但真正痛的問題常常不是速度，而是：

- 上下文丟失
- 決策反覆
- 團隊 AI 不一致

也就是說，下一個更有價值的品類，可能不是 AI productivity，而是 AI continuity。

### 空位 4：Narrative integrity layer

市場上大多數產品把 task、doc、wiki 當主體。

但對創業者與微型團隊來說，真正更稀缺的是：

- 我們現在到底在講哪個故事
- 這週做的事有沒有偏離那個故事

如果 Zentropy 能把這件事產品化，它會比一般 productivity 類產品更難被替代。

## 哪些地方不能誤判

### 誤判 1：以為競品是功能表相似的工具

真正的競爭不是「誰也有 Brain Dump」或「誰也有 graph」。

真正的競爭是：使用者今天會用什麼組合來滿足這個 job。

最常見的實際競品組合是：

- `Claude + Notion`
- `Claude + Todoist`
- `Claude + Obsidian`
- `Cursor + Linear + Notion`

### 誤判 2：以為要正面打所有工作管理場景

Zentropy 不應該打：

- 全能工作空間
- 全能專案管理
- 全能第二大腦

應該只打最痛的一件事：

> AI 工作背景無法延續。

### 誤判 3：以為越多治理越有差異

用戶不會為「更多治理流程」買單。

用戶會為這些體感買單：

- 不用再重講背景
- task 終於知道 why
- 團隊的 AI 不再各說各話

治理應該是底層能力，不是前台賣點。

## 產品定位建議

### 應該怎麼打

第一層訊息：

> 把 AI 工作的背景留住，讓下一次不用從零開始。

第二層訊息：

> 每個 task 都帶著 why，不再只是待辦。

第三層訊息：

> 讓你和團隊的 AI 都基於同一套最新背景工作。

### 不應該怎麼打

- 不要先講 ontology
- 不要先講 graph
- 不要先講治理
- 不要先講 ZenOS 底層
- 不要先講比 Notion/Obsidian 更強的知識整理

## GTM 啟示

### Beachhead market

最適合先打：

1. AI-heavy 個體工作者
2. 2-5 人微型創業團隊

因為這兩群人：

- 已經感受到 AI context loss
- 不需要企業級銷售
- 能直接感知 continuity 的價值

### 最佳 demo 不是看板，而是 continuity moment

最有說服力的 demo 應該是：

1. 在不同 AI 工具裡延續同一個 Product 背景
2. 打開 task 時直接看到來源 reasoning
3. 切到另一位團隊成員時，AI 仍基於同一份 current narrative

### 最佳競品替換話術

不是：

- 比 Todoist 更聰明
- 比 Notion 更會整理
- 比 Obsidian 更 AI-native

而是：

> 你今天已經有工具管理任務、寫文件、做 AI 對話了。真正缺的是一層能把這些工作背景接起來的系統。

## 結論

新的 Zentropy 定義下，競爭格局很清楚：

- 它會被拿去和 Todoist、Notion、Obsidian、Tana、Linear 比
- 但不能在它們最強的主場上打

Zentropy 真正要佔的位置是：

> **AI-Native 工作者的 work continuity layer**

如果這個位置站穩，ZenOS 在背後提供的價值就不會和前台敘事衝突，反而會讓 Zentropy 拿到更難被複製的產品結構：

- 前台是簡單的 continuity promise
- 後台是可演進成 shared reality 的結構能力

這才是 Zentropy 接上 ZenOS 後，最值得主動擴大的差異。
