import { fileURLToPath, URL } from "node:url"

import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react()], // Tailwind runs through PostCSS (postcss.config.js)
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  // Keep the existing REACT_APP_API_URL variable working (Docker + Render docs).
  envPrefix: ["VITE_", "REACT_APP_"],
  server: {
    host: true,
    port: 3000,
    // File-change events don't cross Docker bind mounts on Windows/macOS; poll there.
    watch: { usePolling: process.env.CHOKIDAR_USEPOLLING === "true" },
  },
  preview: { host: true, port: 3000 },
  // Same output folder as Create React App, so `serve -s build` keeps working.
  build: { outDir: "build" },
})
