import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:17396",
        changeOrigin: false,
      },
    },
  },
  // Tauri 开发模式下需要
  clearScreen: false,
  envPrefix: ["VITE_", "TAURI_"],
});
