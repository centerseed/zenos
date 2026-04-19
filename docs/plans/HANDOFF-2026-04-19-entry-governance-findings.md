---
type: HANDOFF
id: HANDOFF-2026-04-19-entry-governance-findings
status: Active
created: 2026-04-19
related:
  - docs/decisions/ADR-010-entity-entries.md
  - docs/specs/SPEC-entry-distillation-quality.md
  - docs/specs/SPEC-entry-consolidation-skill.md
  - docs/decisions/ADR-020-passive-governance-health-signal.md
---

# Entry 治理稽核發現（2026-04-19）

## 稽核對象

Entity 「訓練計畫系統」(`82b9cfa9d9284671b9a1b1d70fac0a5f`)，53 active entries。ADR-010 設計上限 20，超載 165%。

## 治理動作

手動 archive 10 條（reason=manual），剩 36 active。仍超載 80%，但結構性根因未解。

## 三層失效

### Layer 1 — Server gate 缺席

`src/zenos/interface/mcp/write.py:718` 的 20 條上限只 append warning，不 reject。`capture-governance.md` 也寫「寫入 entry 自動不需確認」。結果：**entry 品質規則全寫在 prompt 文字，runtime 零強制**。

### Layer 2 — Capture / Sync 逆向選擇

- `zenos-sync` 的輸入就是 git log，而 ADR-010 明定「code / git history 看得到的不記」→ 本質悖論
- `zenos-capture` 從對話萃取，但對話 90% 是實作討論 → 天然偏 commit-log
- 兩條路徑的**輸入來源與 entry 設計意圖反向**，無論 prompt 怎麼寫都會退化

### Layer 3 — 診斷 / 執行綁死

`analyze(check_type="quality")` 的實作對所有 saturated entity 同步跑 LLM consolidate proposal。52 條單一 entity 就 timeout，沒有「先列症狀、再選動作」的分階段介面。**診斷跑不出來，執行也做不到**。

## Entry 退化 Anti-pattern（今天實證的 10 條）

| Pattern | 例子（今日 archived ID） | 對策 |
|---|---|---|
| 純 code path trace | `39f160f5` — `SlotDistributionSection._get_slot_distribution()（:633）... Call path: get_plan_run → ...` | grep 5 秒可得，不記 |
| 實作細節 + 函式內行為 | `e39f7b2c` `_extract_types`、`82ad3f28` `hr_target_percent 覆蓋 pace_zone` | 讀函式即知，不記 |
| Fallback / 默認行為 | `b6d9d107` `_convert_stages_to_v2() 對未知 stage_id 默默 fallback` | code 可驗，不記 |
| 配置事實 | `413eff52` `complete_10k 沒有 LSD slot` | YAML 可查，不記 |
| Bug fix commit log | `32c1c3c3` 帶 commit SHA `4c35a30d`；`4233c47a` `easy_zone[0]` index bug | git log 範疇，不記 |
| Transient debug noise | `7a5c72fc` `V1 endpoint 404 P3 noise` | 短壽事件，不記 |
| 已被解決的 limitation | `351991e5` options 格式問題已被 `003ed7ad` decision 修掉 | 應 supersede 而非留 active |
| 重複主題未合併 | `49e53d7a` 與 `3cfacea5` 同講 plyometric 未啟用 | 應 consolidate |
| 已被更結構性 entry 涵蓋 | `1918b9c5` iOS app_contract vs `b6060b30` Pydantic/Swift 無同步機制 | 粒度低的該 archive |
| 短壽 supersede 鏈（≤3 天內多版本） | PlanExpander target_km: `df580c91` → `4afdfbfe` → `cb407680` | 代表記得太早，設計未收斂就下筆 |

## 結構性觀察：entity 粒度過大

53 條 entry 跨 8 個獨立主題（methodology YAML / LLM provider / PlanExpander / customization AC-CLP / iOS contract / 力量訓練注入 / HR·pace 計算 / quality gate）。這是 ADR-010 §治理規則明定的「拆分信號」。

## Skill 強化項（本次已執行）

- `skills/release/governance/capture-governance.md` — 兩關標準後加具體 anti-pattern 負面範例
- `skills/release/zenos-governance/SKILL.md` — 新增「Entry 飽和手動稽核 protocol」作為 `analyze(quality)` timeout 時的 fallback
- `skills/release/zenos-sync/SKILL.md` — 強化「不產 entries」理由（反向選擇原則）

## 未解的產品議題（給下次架構討論）

1. **Server-side quality gate**：要不要在 `write(entries)` 做 LLM 品質檢查（code-reachable / commit-log 檢測），reject 而非 warn
2. **Analyze 拆分診斷與執行**：新增 `analyze(check_type="entry_audit", entity_id=..., dry_run=True)` 只列症狀不跑 LLM，執行走獨立 `consolidate_entity(entity_id=...)` 單 entity 模式
3. **Entity 粒度偵測**：saturation 不只量（>20），也要質（entry 主題分群）→ 觸發拆分建議
4. **Sync 角色重定位**：sync 是否應完全放棄抽 entry，只維護 L3 document pointer + staleness
