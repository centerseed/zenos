import { describe, it } from "vitest";

describe("SPEC-task-surface-reset acceptance stubs", () => {
  it.fails("AC-TSR-01: Given 使用者進入 /tasks When 第一屏載入完成 Then 畫面必須先呈現全產品的 milestone / plan recap 與可下鑽入口", () => {
    throw new Error("NOT IMPLEMENTED");
  });

  it.fails("AC-TSR-02: Given 使用者打開一張 task 的 detail When drawer 開啟 Then 第一屏必須先看到單卡狀態、風險與操作", () => {
    throw new Error("NOT IMPLEMENTED");
  });

  it.fails("AC-TSR-03: Given 使用者需要看 task 結構 When 進入 structure 模式 Then 系統必須提供正式入口，但該模式不得是預設 landing state", () => {
    throw new Error("NOT IMPLEMENTED");
  });

  it.fails("AC-TSR-04: Given 系統有多個 active products When 使用者進入 /tasks Then 第一屏必須可直接看到各產品的 milestone / plan 進度概況", () => {
    throw new Error("NOT IMPLEMENTED");
  });

  it.fails("AC-TSR-05: Given 某 product 底下有 blocked plan 或 overdue open work When 使用者查看 /tasks Then 該 product 必須直接顯示風險訊號", () => {
    throw new Error("NOT IMPLEMENTED");
  });

  it.fails("AC-TSR-06: Given 使用者點擊某個 milestone 或 plan When 系統完成導頁 Then 必須進入對應的 /projects?id=<product_id>&focus=... 狀態", () => {
    throw new Error("NOT IMPLEMENTED");
  });

  it.fails("AC-TSR-07: Given 使用者開啟任一 task detail When 不做任何切換 Then 第一屏必須看得到 status / priority / owner / due / blocked / next action / handoff controls", () => {
    throw new Error("NOT IMPLEMENTED");
  });

  it.fails("AC-TSR-08: Given 該 task 有 parent / siblings / subtasks / plan When 使用者尚未切到 Structure Then 這些資訊最多以一行 summary 呈現", () => {
    throw new Error("NOT IMPLEMENTED");
  });

  it.fails("AC-TSR-09: Given 使用者切到 Structure When 畫面顯示完成 Then 必須可辨識 current task、parent、subtasks 與 plan outline 的相對位置", () => {
    throw new Error("NOT IMPLEMENTED");
  });

  it.fails("AC-TSR-10: Given 使用者從 structure 中點選相鄰 task When 導航成功 Then 必須能切到新 task，而不丟失目前的 screen context", () => {
    throw new Error("NOT IMPLEMENTED");
  });

  it.fails("AC-TSR-11: Given desktop viewport When 使用者向下捲動主內容 Then 右側 Task Copilot 必須固定在 viewport 內", () => {
    throw new Error("NOT IMPLEMENTED");
  });

  it.fails("AC-TSR-12: Given 任一 task-related screen When 查看 copilot rail Then rail 的 scope label、placeholder、empty state 必須對應當前 screen 的主問題", () => {
    throw new Error("NOT IMPLEMENTED");
  });

  it.fails("AC-TSR-13: Given /tasks 或 TaskDetailDrawer When 使用者第一次掃視畫面 Then 最先被看見的資訊必須是 task 狀態、風險與可執行操作", () => {
    throw new Error("NOT IMPLEMENTED");
  });

  it.fails("AC-TSR-14: Given /tasks When 畫面載入完成 Then 該頁只能有一個主操作焦點", () => {
    throw new Error("NOT IMPLEMENTED");
  });

  it.fails("AC-TSR-15: Given TaskDetailDrawer When 畫面載入完成 Then 主操作必須跟 task 當前狀態一致", () => {
    throw new Error("NOT IMPLEMENTED");
  });

  it.fails("AC-TSR-16: Given 使用者從 /tasks 點進某個 product / milestone / plan When 在產品頁完成查看後返回 Then 必須保留原本 /tasks 的 scroll / filter / recap context", () => {
    throw new Error("NOT IMPLEMENTED");
  });
});
