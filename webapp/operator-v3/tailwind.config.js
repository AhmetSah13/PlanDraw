/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Space Grotesk"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      colors: {
        command: {
          bg: "#050816",
          surface: "#07111F",
          panel: "rgba(11, 16, 32, 0.72)",
          border: "rgba(34, 211, 238, 0.18)",
          glow: "#22D3EE",
          accent: "#38BDF8",
          violet: "#6366F1",
        },
      },
      boxShadow: {
        glow: "0 0 24px rgba(34, 211, 238, 0.15), 0 0 48px rgba(99, 102, 241, 0.08)",
        "glow-sm": "0 0 12px rgba(34, 211, 238, 0.2)",
        panel: "inset 0 1px 0 rgba(255,255,255,0.04), 0 8px 32px rgba(0,0,0,0.4)",
      },
      backgroundImage: {
        "grid-pattern":
          "linear-gradient(rgba(34,211,238,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(34,211,238,0.04) 1px, transparent 1px)",
      },
      backgroundSize: {
        grid: "32px 32px",
      },
    },
  },
  plugins: [],
};
