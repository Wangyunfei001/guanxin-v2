import path from "node:path"

import { defineConfig } from "vitest/config"

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    // Only pure logic is unit tested — no DOM, no component rendering.
    // Browser behaviour is covered by the Playwright suite.
    environment: "node",
    include: ["src/**/*.test.ts"],
    reporters: "default",
  },
})
