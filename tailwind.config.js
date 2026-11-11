/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "paytm-navy": "#002E6E",
        "paytm-cyan": "#00BAF2",
        surface: "#FFFFFF",
        bg: "#F5F7FA",
        "text-primary": "#1A1A2E",
        "text-inverse": "#FFFFFF",
        "text-muted": "#6B7280",
        success: "#1DA466",
        warning: "#F5A623",
        danger: "#E23744",
        border: "#E5E9F0"
      },
      boxShadow: {
        soft: "0 14px 32px rgba(0, 46, 110, 0.08)"
      },
      fontFamily: {
        sans: [
          "Roboto",
          "Inter",
          "ui-rounded",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif"
        ]
      }
    }
  },
  plugins: []
};
