import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#EEF2FF",
          100: "#E0E7FF",
          400: "#7F8CFF",
          500: "#5B6CFF",
          600: "#4754E8",
          700: "#4338CA",
        },
        violet: {
          400: "#9F7AEA",
        },
        surface: {
          0: "#FFFFFF",
          50: "#fafbff",
          100: "#f4f5fb",
          200: "#E5E7EB",
          300: "#D1D5DB",
        },
        ink: {
          900: "#0c1030",
          800: "rgba(12,16,48,0.82)",
          700: "rgba(12,16,48,0.62)",
          500: "rgba(12,16,48,0.45)",
          400: "rgba(12,16,48,0.30)",
          300: "#D1D5DB",
        },
        panel: {
          bg: "rgba(255,255,255,0.04)",
          border: "rgba(15,18,40,0.08)",
          border2: "rgba(15,18,40,0.14)",
          divider: "rgba(15,18,40,0.06)",
        },
        stage: {
          watching: "#4d8ef5",
          applied: "#a78bfa",
          interview: "#22c55e",
          offer: "#fbbf24",
          rejected: "#ef4444",
        },
        trigger: {
          funding: "#22c55e",
          leadership: "#4d8ef5",
          expansion: "#fbbf24",
          hiring: "#a78bfa",
          product: "#ec4899",
          velocity: "#fb923c",
          distress: "#ef4444",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
