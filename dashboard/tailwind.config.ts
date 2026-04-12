import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0a0a0f",
        surface: "#12121a",
        "surface-hover": "#1a1a2e",
        border: "#1e1e2e",
        "border-hover": "#2a2a3e",
        primary: "#3b82f6",
        "primary-hover": "#2563eb",
        accent: "#06b6d4",
        success: "#22c55e",
        warning: "#f59e0b",
        danger: "#ef4444",
        muted: "#64748b",
        "text-primary": "#f1f5f9",
        "text-secondary": "#94a3b8",
        "text-muted": "#64748b",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
