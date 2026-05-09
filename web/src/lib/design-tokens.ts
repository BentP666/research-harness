/**
 * Design tokens — brand colors, font stacks, spacing scales.
 *
 * Kept as a code module (not CSS vars) so TS + server components can
 * reference them. Mirrors what Tailwind config expects.
 */

export const BRAND = {
  name: "Atlas",
  tagline: {
    en: "Your AI research partner",
    zh: "你的 AI 研究伙伴",
  },
  // Deep-ink primary for academic seriousness; warm accent for human touch.
  color: {
    // Primary — deep indigo, feels like a fountain pen
    primary: {
      50: "#f5f6fb",
      100: "#e9ebf7",
      200: "#ccd1ec",
      300: "#9aa3d5",
      400: "#6771b8",
      500: "#464e9c",
      600: "#363b7d",
      700: "#2c2f62",  // primary brand color
      800: "#232650",
      900: "#191b3a",
    },
    // Accent — warm amber for celebration / recommendations
    accent: {
      500: "#e89b3c",
      600: "#cf822a",
      700: "#a66520",
    },
    // Semantic
    success: "#10a676",
    warning: "#d98c1f",
    danger: "#c24b4b",
    info: "#4a7ca8",
  },
  font: {
    sans: "var(--font-sans, Geist, ui-sans-serif, system-ui, sans-serif)",
    // Serif for academic gravitas on major headings / long reading
    serif:
      "var(--font-serif, 'Fraunces', 'Iowan Old Style', 'Palatino', Georgia, serif)",
    mono: "var(--font-mono, Geist_Mono, ui-monospace, monospace)",
  },
  radius: {
    sm: "0.375rem",
    md: "0.5rem",
    lg: "0.75rem",
    xl: "1rem",
  },
  shadow: {
    card: "0 1px 2px 0 rgb(0 0 0 / 0.03), 0 1px 6px -2px rgb(0 0 0 / 0.06)",
    cardHover:
      "0 4px 12px -2px rgb(44 47 98 / 0.1), 0 2px 6px -1px rgb(44 47 98 / 0.08)",
    elevated: "0 12px 32px -6px rgb(44 47 98 / 0.15)",
  },
} as const;

/** Voice guidelines — three personas used across the UI. */
export const VOICE = {
  system: {
    description: "Terse, neutral status updates. Toasts, badges, timestamps.",
    sample: "Outline generated · 8 sections",
  },
  assistant: {
    description: "Warm, suggestion-oriented. Empty states, next-action cards.",
    sample:
      "I'd start with gap #1 — it's the highest-confidence one and 3 recent papers hint at it.",
  },
  critic: {
    description: "Direct, evidence-demanding. Adversarial review output.",
    sample:
      "This paragraph lacks an ablation table. Without it, the 12% gain is not attributable to your method alone.",
  },
} as const;
