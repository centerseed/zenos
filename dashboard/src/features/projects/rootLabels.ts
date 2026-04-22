export const ROOT_SURFACE_LABEL_ZH = "工作台";
export const ROOT_SURFACE_LABEL_EN = "Workspaces";
export const ROOT_PROGRESS_CONSOLE_LABEL = "Root Progress Console";

export function formatRootScopeLabel(name: string): string {
  return `${name} / ${ROOT_PROGRESS_CONSOLE_LABEL}`;
}

export function formatRootFallbackReview(name: string): string {
  return `Review current progress for ${name}`;
}

export function formatRootEntityLabel(name: string): string {
  return `${name} · ${ROOT_SURFACE_LABEL_ZH}`;
}
