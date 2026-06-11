import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GovGuard™ — Grant Compliance Platform",
  description: "Federal grant compliance and fraud prevention",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
