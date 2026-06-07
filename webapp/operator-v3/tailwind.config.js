/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"DM Sans"', "system-ui", "sans-serif"],
      },
      colors: {
        surface: {
          DEFAULT: "#F5F7FA",
          card: "#FFFFFF",
          muted: "#E8EDF3",
        },
        brand: {
          DEFAULT: "#0B6E99",
          light: "#38BDF8",
          dark: "#0C4A6E",
        },
      },
      boxShadow: {
        card: "0 1px 3px rgba(15, 23, 42, 0.06), 0 4px 16px rgba(15, 23, 42, 0.04)",
      },
    },
  },
  plugins: [],
};
