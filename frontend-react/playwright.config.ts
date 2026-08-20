import path from "node:path"
import { defineConfig, devices } from "@playwright/test"

const runId = `${process.pid}-${Date.now()}`
const backendDirectory = path.resolve(__dirname, "../backend")

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./output/playwright/results",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:3000",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: [
    {
      command: "./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000",
      cwd: backendDirectory,
      url: "http://127.0.0.1:8000/health",
      timeout: 120_000,
      reuseExistingServer: false,
      env: {
        ...process.env,
        APP_ENV: "test",
        DATABASE_PATH: `./data/playwright-${runId}.db`,
        CHECKPOINT_DATABASE_PATH: `./data/playwright-checkpoints-${runId}.db`,
        CHROMA_PERSIST_DIR: `./data/playwright-chroma-${runId}`,
        UPLOAD_DIR: `./data/playwright-uploads-${runId}`,
        OPENAI_API_KEY: "",
        EMBEDDING_PROVIDER: "openai",
        EMBEDDING_API_KEY: "",
      },
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1",
      cwd: __dirname,
      url: "http://127.0.0.1:3000/login",
      timeout: 120_000,
      reuseExistingServer: false,
    },
  ],
})
