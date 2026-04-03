export const APP_COPY = {
  title: "ZenOS 控制台",
  description: "讓所有 AI agent 共用同一套公司知識脈絡",
  skipToContent: "跳到主要內容",
  signOut: "登出",
  team: "成員",
  setup: "設定",
} as const;

export const NODE_TYPE_COPY: Record<string, string> = {
  product: "專案",
  module: "模組",
  goal: "目標",
  role: "角色",
  document: "文件",
  project: "計畫",
  task: "任務",
};

export const TASK_STATUS_COPY: Record<string, string> = {
  todo: "待處理",
  in_progress: "進行中",
  review: "審查中",
  done: "已完成",
};
