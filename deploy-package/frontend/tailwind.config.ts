import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { navy: "#1F3864", blue: "#2E75B6", teal: "#1F6B75", amber: "#C55A11", red: "#C00000" },
      },
    },
  },
  plugins: [],
};
export default config;
