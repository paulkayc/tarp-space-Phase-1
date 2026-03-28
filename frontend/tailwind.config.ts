import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        base:     "#0d0f14",
        surface:  "#141720",
        card:     "#1c2030",
        "card-alt": "#1a1e2e",
        "user-msg": "#1a2440",
        "border-dark": "#252836",
        "border-subtle": "#1e2235",
        muted:    "#5a6480",
        dim:      "#3a4060",
        primary:  "#e8eaf0",
        "accent-blue":   "#60a5fa",
        "accent-green":  "#22c55e",
        "accent-orange": "#f59e0b",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Monaco", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
