import CompanyDetailClient from "./CompanyDetailClient";

export function generateStaticParams() { return [{ id: "_" }]; }

export default function Page() {
  return <CompanyDetailClient />;
}
