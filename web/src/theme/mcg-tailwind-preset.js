/**
 * MCG platform design tokens (extracted from the production bundle of
 * https://mcg-sms.austere.biz on 10-Sep-2026). Keep in sync with the platform's
 * tailwind.config.js; if the IT team exposes their preset, replace this file with an
 * import of it and nothing else changes.
 */
export default {
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#f9f5f7", 100: "#f2e7ed", 200: "#ddbee2", 300: "#c892d0", 400: "#a55cb4",
          500: "#782669", 600: "#6a1f5b", 700: "#5a1a4d", 800: "#4a153f", 900: "#3a1032", 950: "#2a0b24",
        },
        accent: {
          50: "#edfffe", 100: "#d1faf8", 200: "#a7f3f0", 300: "#6ee7e2", 400: "#2dd4cc",
          500: "#0d9488", 600: "#0f766e", 700: "#115e59", 800: "#134e4a", 900: "#134e4a",
        },
        secondary: {
          50: "#fffbeb", 100: "#fef3c7", 200: "#fde68a", 300: "#fcd34d", 400: "#f4b740",
          500: "#f59e0b", 600: "#d97706", 700: "#b45309", 800: "#92400e", 900: "#78350f",
        },
        warning: { 50: "#fffbeb", 100: "#fef3c7", 500: "#f59e0b", 600: "#d97706" },
        danger: { 50: "#fef2f2", 100: "#fee2e2", 500: "#d32f2f", 600: "#dc2626", 700: "#b91c1c" },
        success: { 50: "#f0fdf4", 100: "#dcfce7", 500: "#2e7d32", 600: "#16a34a", 700: "#15803d" },
        light: {
          background: "#f7f7fb", surface: "#ffffff", border: "#e5e7eb",
          text: "#1f2937", "text-muted": "#6b7280",
        },
        dark: {
          background: "#121212", surface: "#1e1e24", border: "#343434",
          text: "#f3f4f6", "text-muted": "#a3a7b3",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
      },
      borderRadius: { DEFAULT: "6px" },
      boxShadow: {
        card: "0 1px 2px 0 rgb(0 0 0 / 0.05)",
        panel: "0 4px 4px rgba(0,0,0,.12), 0 0 10px rgba(0,0,0,.06)",
      },
    },
  },
};
