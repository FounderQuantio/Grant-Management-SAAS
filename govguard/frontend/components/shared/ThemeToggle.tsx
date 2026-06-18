"use client";
import { useEffect, useState } from "react";
import { Sun, Moon } from "lucide-react";

export function ThemeToggle() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const saved = localStorage.getItem("qg-theme") as "dark" | "light" | null;
    if (saved === "light") {
      setTheme("light");
      document.documentElement.setAttribute("data-theme", "light");
    }
  }, []);

  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    if (next === "light") {
      document.documentElement.setAttribute("data-theme", "light");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
    localStorage.setItem("qg-theme", next);
  };

  // Placeholder that matches button size to avoid layout shift during SSR
  if (!mounted) {
    return <div style={{ width: 32, height: 32, flexShrink: 0 }} />;
  }

  return (
    <button
      onClick={toggle}
      title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      style={{
        width: 32, height: 32, flexShrink: 0,
        display: "flex", alignItems: "center", justifyContent: "center",
        borderRadius: "var(--qg-radius-md)",
        border: "1px solid var(--qg-border-2)",
        background: theme === "light" ? "var(--qg-gold-tint-2)" : "var(--qg-hover-subtle)",
        color: theme === "light" ? "var(--qg-gold)" : "var(--qg-text-3)",
        cursor: "pointer",
        transition: "var(--qg-ease)",
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--qg-gold-border)";
        (e.currentTarget as HTMLButtonElement).style.color = "var(--qg-gold)";
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--qg-border-2)";
        (e.currentTarget as HTMLButtonElement).style.color = theme === "light" ? "var(--qg-gold)" : "var(--qg-text-3)";
      }}
    >
      {theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}
    </button>
  );
}
