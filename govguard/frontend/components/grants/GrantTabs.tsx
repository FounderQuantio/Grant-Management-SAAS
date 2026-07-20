"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

export function GrantTabs({ grantId }: { grantId: string }) {
  const pathname = usePathname();
  const tabs = [
    { label: "Overview",             href: `/grants/${grantId}` },
    { label: "Compliance",           href: `/grants/${grantId}/compliance` },
    { label: "Reporting",            href: `/grants/${grantId}/reporting` },
    { label: "Budget Modifications", href: `/grants/${grantId}/budget-modifications` },
  ];

  return (
    <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
      {tabs.map((tab) => (
        <Link
          key={tab.href}
          href={tab.href}
          className={`qg-pill${pathname === tab.href ? " active" : ""}`}
          style={{ textDecoration: "none" }}
        >
          {tab.label}
        </Link>
      ))}
    </div>
  );
}
