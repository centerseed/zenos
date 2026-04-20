// Minimal type declaration for react-dom (react-dom v19 ships without bundled .d.ts)
// This declaration only exposes what is used by Zen primitives.
declare module "react-dom" {
  import type { ReactNode } from "react";
  export function createPortal(children: ReactNode, container: Element): ReactNode;
  export function flushSync(fn: () => void): void;
}
