import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#172033",
        river: "#176B87",
        jade: "#1B8A5A",
        wheat: "#F4B860",
      },
      boxShadow: {
        panel: "0 20px 50px rgba(23, 32, 51, 0.08)",
      },
    },
  },
  plugins: [],
};

export default config;
