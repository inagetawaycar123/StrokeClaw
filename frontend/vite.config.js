import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendTarget = process.env.VITE_PROXY_TARGET || "http://127.0.0.1:5011";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../static/dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    host: "0.0.0.0",
    proxy: {
      "/api": {
        target: backendTarget,
        changeOrigin: true,
      },
      "/kb-pdfs": {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
});
