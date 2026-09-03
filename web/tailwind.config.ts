import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        myntra: {
          pink: "#FF3F6C",
          "pink-dark": "#E03560",
          ink: "#282C3F",
          muted: "#535766",
          line: "#E9E9EB",
          wash: "#F5F5F6",
          gold: "#FFC107",
        },
      },
      boxShadow: {
        card: "0 1px 4px 0 rgba(40, 44, 63, 0.08)",
        lift: "0 4px 16px rgba(40, 44, 63, 0.12)",
      },
    },
  },
  plugins: [],
};

export default config;
