import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import "./quantio-theme.css";
import SiteHeader from "@/components/shared/SiteHeader";
import SiteFooter from "@/components/shared/SiteFooter";

const inter = Inter({ subsets: ["latin"], variable: "--qg-font-loaded" });

export const metadata: Metadata = {
  title: "GovGuard™ — Grant Compliance Platform",
  description: "Federal grant compliance and fraud prevention",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body style={{ fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" }}>
        <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden" }}>
          <SiteHeader />
          <div style={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
            {children}
          </div>
          <SiteFooter />
        </div>
      </body>
    </html>
  );
}
