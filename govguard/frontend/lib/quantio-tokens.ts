/**
 * Quantio Global — Shared Design Tokens (TS)
 * Import: import { QT, QS, QSF } from '@/lib/quantio-tokens'
 *
 * QT  — token values (use in inline styles / style objects)
 * QS  — pre-built style objects (spread directly onto elements)
 * QSF — style factory functions that accept state (hover, active, etc.)
 */

import type { CSSProperties } from "react";

// ─── 1. COLOUR TOKENS ────────────────────────────────────────────────────────

export const COLORS = {
  gold:           "#6495ED",
  goldLight:      "#7FA6F0",
  goldDim:        "rgba(100,149,237,0.55)",
  goldTint1:      "rgba(100,149,237,0.18)",
  goldTint2:      "rgba(100,149,237,0.12)",
  goldTint3:      "rgba(100,149,237,0.08)",
  goldBorder:     "rgba(100,149,237,0.25)",
  goldBorderH:    "rgba(100,149,237,0.45)",

  bg:             "#F1EEEA",
  sidebar:        "#FFFFFF",
  surface:        "#FFFFFF",
  surface2:       "#E8E2D8",
  overlay:        "rgba(33,36,39,0.45)",

  border:         "rgba(33,36,39,0.08)",
  border2:        "rgba(33,36,39,0.13)",
  borderStrong:   "rgba(33,36,39,0.22)",

  text1:          "#212427",
  text2:          "rgba(33,36,39,0.78)",
  text3:          "rgba(33,36,39,0.50)",
  text4:          "rgba(33,36,39,0.32)",

  red:            "#EF4444", redBg:    "rgba(239,68,68,0.09)",   redBd:    "rgba(239,68,68,0.25)",
  orange:         "#F97316", orangeBg: "rgba(249,115,22,0.09)",  orangeBd: "rgba(249,115,22,0.25)",
  yellow:         "#EAB308", yellowBg: "rgba(234,179,8,0.09)",   yellowBd: "rgba(234,179,8,0.25)",
  green:          "#22C55E", greenBg:  "rgba(34,197,94,0.09)",   greenBd:  "rgba(34,197,94,0.25)",
  purple:         "#7C3AED", purpleBg: "rgba(124,58,237,0.09)", purpleBd: "rgba(124,58,237,0.25)",
  teal:           "#0D9488", tealBg:   "rgba(13,148,136,0.09)",  tealBd:   "rgba(13,148,136,0.25)",
};

// ─── 2. TYPOGRAPHY TOKENS ────────────────────────────────────────────────────

export const TYPE = {
  font:     '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  fontMono: '"JetBrains Mono", "Fira Code", "Cascadia Code", monospace',

  xs:   9,
  sm:   11,
  base: 13,
  md:   14,
  lg:   15,
  xl:   18,
  "2xl": 22,
  "3xl": 28,
  "4xl": 36,

  normal: 400,
  medium: 500,
  semi:   600,
  bold:   700,
  extra:  800,
  black:  900,

  tight:    1.25,
  lineBase: 1.5,
  loose:    1.8,
};

// ─── 3. SPACING TOKENS ───────────────────────────────────────────────────────

export const SPACE = { 1: 4, 2: 8, 3: 12, 4: 16, 5: 20, 6: 24, 8: 32, 10: 40, 12: 48, 16: 64 };

// ─── 4. SHAPE TOKENS ─────────────────────────────────────────────────────────

export const RADIUS = {
  sm:     "4px",
  md:     "8px",
  lg:     "12px",
  xl:     "14px",
  "2xl":  "20px",
  pill:   "100px",
  circle: "50%",
};

// ─── 5. SHADOW TOKENS ────────────────────────────────────────────────────────

export const SHADOW = {
  sm:   "0 1px 3px rgba(33,36,39,0.08), 0 1px 2px rgba(33,36,39,0.05)",
  md:   "0 4px 12px rgba(33,36,39,0.10), 0 2px 4px rgba(33,36,39,0.05)",
  lg:   "0 20px 48px rgba(33,36,39,0.14), 0 8px 16px rgba(33,36,39,0.07)",
  gold: "0 0 0 1px rgba(100,149,237,0.20), 0 8px 24px rgba(33,36,39,0.10)",
};

// ─── 6. MAIN TOKEN EXPORT (shorthand QT) ─────────────────────────────────────

export const QT = {
  ...COLORS,
  ...SHADOW,
  font:   TYPE.font,
  mono:   TYPE.fontMono,
  r:      RADIUS,
  sp:     SPACE,
};

// ─── 7. PRE-BUILT STYLE OBJECTS (QS) ─────────────────────────────────────────

export const QS: Record<string, CSSProperties> = {
  page: {
    minHeight: "100vh",
    background: COLORS.bg,
    fontFamily: TYPE.font,
    color: COLORS.text1,
    WebkitFontSmoothing: "antialiased",
  },

  nav: {
    height: 60,
    background: "rgba(33,36,39,0.96)",
    borderBottom: `1px solid ${COLORS.border}`,
    display: "flex",
    alignItems: "center",
    padding: "0 24px",
    gap: 16,
    position: "sticky",
    top: 0,
    zIndex: 100,
    backdropFilter: "blur(12px)",
    WebkitBackdropFilter: "blur(12px)",
  },

  navLinkInactive: {
    color: "rgba(33,36,39,0.70)",
    fontSize: 13,
    fontWeight: TYPE.medium,
    textDecoration: "none",
    padding: "7px 16px",
    borderRadius: RADIUS.pill,
    background: "rgba(33,36,39,0.04)",
    border: "1px solid rgba(33,36,39,0.07)",
    transition: "all 0.18s",
    cursor: "pointer",
  },

  navLinkActive: {
    color: COLORS.gold,
    background: COLORS.goldTint2,
    border: `1px solid ${COLORS.goldBorder}`,
  },

  sidebar: {
    width: 208,
    background: COLORS.sidebar,
    borderRight: `1px solid ${COLORS.border}`,
    display: "flex",
    flexDirection: "column",
    height: "100vh",
    flexShrink: 0,
    overflow: "hidden",
  },

  sidebarHeader: {
    padding: "16px 14px 12px",
    borderBottom: `1px solid ${COLORS.border}`,
  },

  sidebarItemInactive: {
    display: "flex",
    alignItems: "center",
    gap: 9,
    width: "100%",
    padding: "8px 10px",
    marginBottom: 1,
    border: "none",
    borderRadius: RADIUS.md,
    cursor: "pointer",
    background: "transparent",
    color: "rgba(33,36,39,0.50)",
    fontSize: 12,
    fontWeight: TYPE.normal,
    textAlign: "left",
    transition: "all 0.15s",
  },

  sidebarItemActive: {
    background: COLORS.goldTint1,
    color: COLORS.gold,
    fontWeight: TYPE.bold,
  },

  card: {
    background: COLORS.surface,
    border: `1px solid ${COLORS.border}`,
    borderRadius: RADIUS.xl,
    padding: 24,
    transition: "all 0.25s",
  },

  cardHover: {
    background: COLORS.surface2,
    borderColor: "rgba(100,149,237,0.20)",
    boxShadow: SHADOW.gold,
    transform: "translateY(-4px)",
  },

  cardIcon: {
    width: 44,
    height: 44,
    borderRadius: RADIUS.lg,
    background: COLORS.goldTint2,
    border: `1px solid rgba(100,149,237,0.22)`,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 12,
    fontWeight: TYPE.extra,
    color: COLORS.gold,
    flexShrink: 0,
    transition: "all 0.2s",
  },

  cardIconHover: {
    background: COLORS.goldTint1,
    borderColor: COLORS.goldBorderH,
  },

  cardArrow: {
    width: 34,
    height: 34,
    borderRadius: RADIUS.circle,
    background: "rgba(33,36,39,0.05)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 15,
    color: "rgba(33,36,39,0.22)",
    flexShrink: 0,
    transition: "all 0.22s",
  },

  cardArrowHover: {
    background: COLORS.gold,
    color: "#FFFFFF",
  },

  btnBase: {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    padding: "9px 22px",
    borderRadius: RADIUS.pill,
    border: "none",
    cursor: "pointer",
    fontFamily: TYPE.font,
    fontSize: 13,
    fontWeight: TYPE.bold,
    letterSpacing: "0.2px",
    transition: "all 0.18s",
    whiteSpace: "nowrap",
    textDecoration: "none",
  },

  btnPrimary: {
    background: COLORS.gold,
    color: "#FFFFFF",
  },

  btnSecondary: {
    background: "rgba(33,36,39,0.06)",
    color: COLORS.text2,
    border: `1px solid ${COLORS.border2}`,
  },

  btnGhost: {
    background: "transparent",
    color: COLORS.text3,
    border: "none",
  },

  btnDanger: {
    background: COLORS.redBg,
    color: COLORS.red,
    border: `1px solid ${COLORS.redBd}`,
  },

  btnHome: {
    background: COLORS.goldTint2,
    color: COLORS.gold,
    border: `1px solid ${COLORS.goldBorder}`,
    padding: "5px 12px",
    borderRadius: RADIUS.md,
    fontSize: 12,
    fontWeight: TYPE.bold,
    cursor: "pointer",
    transition: "all 0.15s",
    display: "inline-flex",
    alignItems: "center",
    gap: 5,
    textDecoration: "none",
  },

  pillInactive: {
    padding: "3px 10px",
    borderRadius: RADIUS.pill,
    border: `1px solid ${COLORS.border2}`,
    background: "rgba(33,36,39,0.06)",
    color: "rgba(33,36,39,0.65)",
    fontSize: 9,
    fontWeight: TYPE.bold,
    cursor: "pointer",
    transition: "all 0.15s",
  },

  pillActive: {
    background: COLORS.gold,
    color: "#FFFFFF",
    borderColor: "transparent",
  },

  input: {
    width: "100%",
    padding: "9px 14px",
    background: COLORS.surface,
    border: `1px solid ${COLORS.border2}`,
    borderRadius: RADIUS.md,
    color: COLORS.text1,
    fontFamily: TYPE.font,
    fontSize: 13,
    outline: "none",
    transition: "all 0.18s",
    appearance: "none",
    colorScheme: "light",
  } as CSSProperties,

  inputFocus: {
    borderColor: COLORS.goldBorder,
    boxShadow: `0 0 0 3px ${COLORS.goldTint3}`,
  },

  tableHead: {
    padding: "10px 14px",
    textAlign: "left",
    fontSize: 9,
    fontWeight: TYPE.bold,
    color: COLORS.text3,
    letterSpacing: "0.8px",
    textTransform: "uppercase",
    background: COLORS.surface2,
    borderBottom: `1px solid ${COLORS.border2}`,
    whiteSpace: "nowrap",
  },

  tableCell: {
    padding: "10px 14px",
    borderBottom: `1px solid ${COLORS.border}`,
    color: COLORS.text2,
    verticalAlign: "middle",
    fontSize: 13,
  },

  badge: {
    display: "inline-flex",
    alignItems: "center",
    gap: 4,
    padding: "2px 8px",
    borderRadius: RADIUS.pill,
    fontSize: 9,
    fontWeight: TYPE.bold,
    whiteSpace: "nowrap",
  },

  badgeCritical: { background: COLORS.redBg,    color: COLORS.red,    border: `1px solid ${COLORS.redBd}` },
  badgeHigh:     { background: COLORS.orangeBg,  color: COLORS.orange, border: `1px solid ${COLORS.orangeBd}` },
  badgeMedium:   { background: COLORS.yellowBg,  color: COLORS.yellow, border: `1px solid ${COLORS.yellowBd}` },
  badgeLow:      { background: COLORS.greenBg,   color: COLORS.green,  border: `1px solid ${COLORS.greenBd}` },
  badgeGold:     { background: COLORS.goldTint2, color: COLORS.gold,   border: `1px solid ${COLORS.goldBorder}` },
  badgeMuted:    { background: "rgba(33,36,39,0.06)", color: COLORS.text3, border: `1px solid ${COLORS.border}` },
};

// ─── 8. STYLE FACTORIES (QSF) ─────────────────────────────────────────────────

export const QSF = {
  card:       (hover: boolean): CSSProperties => ({ ...QS.card,       ...(hover ? QS.cardHover       : {}) }),
  cardIcon:   (hover: boolean): CSSProperties => ({ ...QS.cardIcon,   ...(hover ? QS.cardIconHover   : {}) }),
  cardArrow:  (hover: boolean): CSSProperties => ({ ...QS.cardArrow,  ...(hover ? QS.cardArrowHover  : {}) }),
  navLink:    (active: boolean): CSSProperties => ({ ...QS.navLinkInactive, ...(active ? QS.navLinkActive : {}) }),
  sidebarItem:(active: boolean): CSSProperties => ({ ...QS.sidebarItemInactive, ...(active ? QS.sidebarItemActive : {}) }),
  pill:       (active: boolean, extra: CSSProperties = {}): CSSProperties => ({ ...QS.pillInactive, ...(active ? { ...QS.pillActive, ...extra } : {}) }),
  input:      (focused: boolean): CSSProperties => ({ ...QS.input, ...(focused ? QS.inputFocus : {}) }),
  btn:        (variant: "Primary" | "Secondary" | "Ghost" | "Danger" | "Home" = "Primary"): CSSProperties => ({
    ...QS.btnBase, ...(QS[`btn${variant}`] || QS.btnPrimary),
  }),
  btnHome:    (hover: boolean): CSSProperties => ({
    ...QS.btnHome, ...(hover ? { background: COLORS.goldTint1, borderColor: COLORS.goldBorderH } : {}),
  }),
};
