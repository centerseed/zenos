import type { Metadata } from "next";
import { AuthProvider } from "@/lib/auth";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./globals.css";
import { Geist } from "next/font/google";
import { cn } from "@/lib/utils";
import { ToastProvider } from "@/components/ui/toast";
import { APP_COPY } from "@/lib/i18n";

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: APP_COPY.title,
  description: APP_COPY.description,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-TW" className={cn("dark font-sans", geist.variable)}>
      <body className="bg-background text-foreground antialiased">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[100] rounded bg-card px-3 py-2 text-sm text-foreground ring-1 ring-border"
        >
          {APP_COPY.skipToContent}
        </a>
        <AuthProvider>
          <ToastProvider>
            <TooltipProvider>{children}</TooltipProvider>
          </ToastProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
