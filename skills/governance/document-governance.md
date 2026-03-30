# L3 文件治理規則 v1.0（完整版）

## 文件的定位
L3 document entity 是正式文件的語意代理——metadata 在 ZenOS，實際內容在外部。
文件不是 L2（文件是 L2 概念的具體體現），不是 task（文件沒有 owner 和 AC）。

## 必要欄位
- title: 文件標題
- type: SPEC / ADR / TD / PB / REF / SC
- source.uri: 文件的存放位置（GitHub URL 或本地路徑）
- ontology_entity: 掛載到哪個 L2 entity 的名稱
- status: draft / under_review / approved / superseded / archived

## 完整 Frontmatter 格式
```yaml
---
doc_id: SPEC-feature-name          # 唯一 ID（格式：類型-描述）
title: 功能規格：功能名稱
type: SPEC                          # SPEC|ADR|TD|PB|REF|SC
ontology_entity: L2 Entity 名稱     # 掛載的 L2 entity
status: draft                       # draft|under_review|approved|superseded|archived
version: "0.1"
date: 2026-01-01
supersedes: null                    # 被此文件取代的文件 ID（如有）
---
```

## 生命週期
draft → under_review → approved（正式文件）
approved → superseded（被新版取代時，保留原文件，建立指向）
任何狀態 → archived（廢棄）

## Supersede 流程細節
1. 建立新版文件（新 doc_id，status=draft）
2. 新文件 frontmatter 加 supersedes: 舊文件 ID
3. 舊文件 status 更新為 superseded
4. 在 ZenOS 建 relationship：新文件 supersedes 舊文件
5. 保留舊文件（不刪除），讓歷史可追溯

## Stale 偵測規則
文件可能過時的訊號：
- approved 文件已超過 90 天未被 review
- 掛載的 L2 entity 已變為 stale 狀態
- 相關 task 的 result 顯示文件描述的行為已改變
- git log 顯示實作已大幅偏離文件描述

偵測到 stale 時：建 task 要求 review，tag 文件為 under_review。

## Batch Sync 操作說明
從 git log 批量同步文件狀態：
1. 掃描 git log，找出最近修改的 SPEC/ADR/TD 文件
2. 比對 ZenOS 中對應 document entity 的 status
3. 如果 git 文件有新 commit 但 ZenOS status 仍是 draft → 建議更新為 under_review
4. 如果 git 文件已刪除但 ZenOS 仍 approved → 標記為 archived

## 分類說明（含決策準則）
- SPEC: 功能規格（what + why）—— 面向產品，定義做什麼
- ADR: 架構決策紀錄（why this choice）—— 面向工程，記錄為什麼這樣選
- TD: 技術設計（how）—— 面向實作，說明怎麼做
- PB: 操作手冊 / Playbook —— 面向操作，SOP 類文件
- REF: 參考資料 —— 外部研究、競品分析、不可改變的參考
- SC: Script / 腳本 —— 自動化腳本的說明文件

選型準則：看受眾和目的，不看篇幅。一份短的「為什麼」= ADR，長的「怎麼做」= TD。
