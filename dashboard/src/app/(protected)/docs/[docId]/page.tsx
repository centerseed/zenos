import DocReaderClient from "./DocReaderClient";

// Required for Next.js output: export — client-side routing handles actual docId at runtime
export function generateStaticParams() { return [{ docId: "_" }]; }

export default function Page() {
  return <DocReaderClient />;
}
