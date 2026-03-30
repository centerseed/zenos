---
type: SPEC
id: SPEC-skill-release-management
status: Draft
ontology_entity: agent-integration
created: 2026-03-26
updated: 2026-03-26
---

# Feature Spec: ZenOS Skill 中央發佈與升級治理

## 背景

目前 ZenOS skills 分散在 repo 內容，由使用者自行 `git pull` 或手動 `cp -R` 到全域目錄。這會造成三個治理問題：

- 發佈來源不一致，使用者不知道哪一份是最新版本
- 升級入口不一致，不同 agent host 需要重複學習不同流程
- 升級失敗沒有保護，半套覆寫可能直接破壞既有 workflow

本 spec 定義一條可審計、可重複、可回滾的 skill 發佈與升級路徑。

## 目標

1. 建立單一中央發佈來源，供所有 ZenOS skills 查詢版本與下載內容。
2. 提供單一安裝/升級入口，讓使用者或 agent 可以用同一個命令完成更新。
3. 僅更新過期 skill，並輸出可追溯的升級摘要。
4. 升級失敗時保留既有可用版本，不得留下半更新狀態。
5. 明確定義版本語意與責任分工，避免 skill 發佈失序。

## 非目標

- 不在本 spec 定義每個 skill 內部 workflow。
- 不處理第三方 marketplace 的簽章、收費或權限模型。
- 不要求 dashboard 成為唯一安裝入口。

## 中央發佈來源

ZenOS skills 的中央發佈來源必須是 repo 內的 [`skills/release/manifest.json`](/Users/wubaizong/clients/ZenOS/skills/release/manifest.json)。

治理規則：

- manifest 必須列出每個可發佈 skill 的 `name`、`version`、`path`、`files`、`owner`。
- manifest 的 URL 必須可由單一穩定位置存取。正式發佈來源為 main branch 的 raw manifest。
- `path` 必須指向 manifest 同層目錄下的 skill 發佈內容；目前最小發佈單位為 `SKILL.md`。
- 未列入 manifest 的 skill 不得由官方升級入口自動安裝。
- `.claude/`、`.codex/` 僅為本機 host mirror，不得作為官方發佈內容，也不得作為版本真實來源（source of truth）。

## 版本語意

每個 skill 必須使用 `major.minor.patch` 語意版本。

- `major`：破壞既有使用方式或需要人工介入遷移。
- `minor`：向後相容的新功能、流程補強、支援更多情境。
- `patch`：向後相容的修正、文案澄清、風險降低。

治理規則：

- manifest 內版本必須與該 skill `SKILL.md` frontmatter 的 `version` 一致。
- 未符合 semantic version 格式的 skill 不得發佈。
- 發佈者不得在內容變更後重用同一版本號。

## 單一安裝/升級入口

官方入口必須是 `zenos-skills setup`。

行為規則：

- `zenos-skills setup` 必須支援目標目錄參數，預設為 `~/.codex/skills`。
- `zenos-skills setup` 必須先讀取遠端 manifest，再讀取本地已安裝 skill 版本。
- 本地版本大於等於遠端版本時，必須略過該 skill，不得重複安裝。
- 本地版本低於遠端版本時，才可執行替換。
- 執行結果必須輸出每個 skill 的 `name`、舊版、新版與動作（`installed`、`updated`、`unchanged`）。

## 失敗保護與可回滾性

升級流程必須使用 staged install + atomic replace。

具體規則：

- 新版本必須先下載到暫存目錄，不得直接覆寫既有 skill 目錄。
- 若目標 skill 已存在，必須先將舊版本移到 backup 位置，再以原子替換方式切入新版本。
- 新版本切入失敗時，系統必須自動把 backup 還原回原路徑。
- 任一 skill 升級失敗時，失敗 skill 不得留下空目錄或半寫入檔案。
- 實作必須提供可重現證據，證明 replace 失敗後原版仍可讀取。

## 責任分工

- 平台維運 owner：Barry
  - 維護中央 manifest 與正式發佈流程
  - 審核版本號是否符合 semantic version 規則
  - 驗收升級摘要與失敗保護測試
- Skill 作者
  - 提交 skill 內容與對應版本 bump
  - 保證 `SKILL.md` frontmatter 與 manifest 版本一致
- 執行者（agent 或使用者）
  - 只透過 `zenos-skills setup` 安裝或升級官方 skill
  - 保留安裝輸出作為升級證據

## 操作文件要求

README 或同級操作文件必須包含：

- 官方更新命令
- 指向中央發佈來源的說明
- 從舊版升到新版的實際範例
- 故障排除步驟，至少涵蓋 manifest 讀取失敗與本地目錄權限不足

## 驗收證據

- 程式入口：[pyproject.toml](/Users/wubaizong/clients/ZenOS/pyproject.toml) 與 [src/zenos/skills_cli.py](/Users/wubaizong/clients/ZenOS/src/zenos/skills_cli.py)
- 中央 manifest：[skills/release/manifest.json](/Users/wubaizong/clients/ZenOS/skills/release/manifest.json)
- 版本比對與原子替換：[src/zenos/skills_installer.py](/Users/wubaizong/clients/ZenOS/src/zenos/skills_installer.py)
- 回滾測試：[tests/application/test_skills_installer.py](/Users/wubaizong/clients/ZenOS/tests/application/test_skills_installer.py)
- 任務 ID：`18bece5005234ddc988ebc541a563149`
