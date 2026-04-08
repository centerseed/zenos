---
type: TC
doc_id: TC-identity-and-access
title: 測試場景：身份、Workspace 與共享授權
ontology_entity: 身份與權限管理
status: under_review
version: "0.1"
date: 2026-04-08
supersedes: null
---

# 測試場景：身份、Workspace 與共享授權

## P0 場景（必須全部通過）

### S1: 新用戶註冊後自動建立 home workspace
Given: 一個從未存在過的 user 完成註冊
When: 註冊流程成功
Then: 系統自動建立一個空的 home workspace，且該 user 為 owner

### S2: 多 workspace user 登入後先回 home workspace
Given: 某 user 同時擁有自己的 home workspace，且被邀加入 Barry workspace
When: 該 user 重新登入
Then: 系統先進入其 home workspace，而不是直接進 Barry workspace

### S3: 單一 workspace 時顯示我的工作區入口
Given: 某 user 只有自己的 home workspace
When: 該 user 進入 Dashboard
Then: 左側顯示「我的工作區」入口，而不是完整 workspace picker

### S4: 第二個 workspace 出現後入口升級為 picker
Given: 某 user 原本只有自己的 home workspace，後來被邀加入第二個 workspace
When: 該 user 再次進入 Dashboard
Then: 原本的「我的工作區」入口升級為 workspace picker，且可切換兩個 workspace

### S5: Guest 在 shared workspace 可看到 Knowledge Map
Given: hhh1230 被 Barry 分享某個 product(L1)，角色為 guest
When: hhh1230 切到 Barry workspace
Then: 主導航顯示 Knowledge Map / Products / Tasks，且可進入 Knowledge Map

### S6: Home workspace 保持完整功能
Given: hhh1230 擁有自己的 home workspace，且也被邀加入 Barry workspace
When: hhh1230 回到自己的 home workspace
Then: 可看到完整功能集合，不因自己在 Barry workspace 是 guest 而被裁切

### S7: Guest 只可見授權 L1 子樹
Given: Barry 分享 product A 給 hhh1230，但未分享 product B
When: hhh1230 進入 Barry workspace 的 Knowledge Map
Then: 只看得到 product A 子樹，看不到 product B、其節點、其 impacts 或其存在提示

### S8: Guest 看不到 restricted 與 confidential
Given: product A 已分享給 hhh1230，且其下同時存在 public / restricted / confidential 節點
When: hhh1230 進入 Barry workspace
Then: 只看得到 public 節點，看不到 restricted 與 confidential

### S9: Member 可看整個 workspace
Given: 某 user 在 Barry workspace 的角色為 member
When: 該 user 進入 Barry workspace
Then: 可看整個 workspace 的 ontology / products / tasks，只受 visibility 規則限制

### S10: Guest 可建立 task
Given: hhh1230 在 Barry workspace 中被授權某個 product(L1)
When: hhh1230 建立一個新 task
Then: 該 task 成功建立，且掛在其授權範圍內

### S11: Guest 可建立 L3，但不可建立 L1/L2
Given: hhh1230 在 Barry workspace 中被授權某個 L1 與其下 L2
When: hhh1230 嘗試建立新的 L3
Then: 建立成功，且必須至少掛到其授權範圍內的一個 L2

### S12: Guest 建 L3 預設寫回 active workspace
Given: hhh1230 正在 Barry workspace 中建立新的 L3
When: 建立完成
Then: 該 L3 寫回 Barry workspace，而不是自動同步到 hhh1230 的 home workspace

### S13: Guest 不可建立 L1/L2
Given: hhh1230 在 Barry workspace 中的角色為 guest
When: hhh1230 嘗試建立新的 L1 或 L2
Then: 系統拒絕該操作

### S14: 多重歸屬 L3 的授權裁切
Given: 某個 L3 同時掛在 product A 與 product B，hhh1230 只被授權 product A
When: hhh1230 查看該 L3
Then: 該 L3 節點可見，但圖譜展開、關聯與 impacts 只顯示 product A 授權範圍內的部分

### S15: Tasks 與 docs 沿用 ontology 授權
Given: 某 task 與 doc 掛在未授權的節點下
When: guest 進入 shared workspace
Then: 該 task 與 doc 完全不可見

### S16: Products 取代 Projects 文案
Given: user 進入任何 workspace 的主導航
When: 導航渲染完成
Then: 對外文案顯示為 Products，而不是 Projects

## P1 場景（應通過）

### S17: 其他 workspace 有更新時顯示 badge
Given: 某 user 同時加入多個 workspace，且其中一個非 active workspace 有更新
When: user 查看 workspace picker
Then: 該 workspace 顯示更新 badge

### S18: Guest 建立 L3 預設為 public
Given: guest 在 shared workspace 中建立新的 L3
When: 建立完成
Then: 該 L3 的預設 visibility 為 public

### S19: 權限撤銷後自動移除 task assignee
Given: 某 guest 原本被授權某個 L1，且在其範圍內 tasks 被指派
When: owner 移除其 L1 授權或將其移出 workspace
Then: 系統自動移除該 guest 在失效範圍內的 task assignee 關聯
