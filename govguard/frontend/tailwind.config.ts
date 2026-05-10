import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          navy:  "#1F3864",
          blue:  "#2E75B6",
          teal:  "#1F6B75",
          amber: "#C55A11",
          red:   "#C00000",
          green: "#375623",
        },
      },
    },
  },
  plugins: [],
};

export default config;
