/// <reference types="vitest/config" />
import { resolve } from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// The build lands in dashboard/static/dist, which Flask already serves at
// /static/dist. It is committed, so the lab PCs need Python only, not Node.
export default defineConfig({
  base: "/static/dist/",
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": resolve(import.meta.dirname, "./src"),
    },
  },
  build: {
    outDir: resolve(import.meta.dirname, "../static/dist"),
    emptyOutDir: true,
  },
  server: {
    // `npm run dev` talks to the running `python run_demo.py`.
    proxy: { "/api": "http://127.0.0.1:5000" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
})
