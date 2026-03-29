import DealDetailClient from "./DealDetailClient";

export function generateStaticParams() { return [{ id: "_" }]; }

export default function Page() {
  return <DealDetailClient />;
}
