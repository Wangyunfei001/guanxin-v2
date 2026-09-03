import path from "node:path"
import { defineConfig, devices } from "@playwright/test"

const backendDirectory = path.resolve(__dirname, "../backend")
const reuseExistingServer = !process.env.CI
const e2eRoot = process.env.GUANXIN_E2E_ROOT
if (!e2eRoot) throw new Error("Run Playwright through npm run test:e2e")

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
      reuseExistingServer,
      env: {
        ...process.env,
        APP_ENV: "test",
        DATABASE_PATH: path.join(e2eRoot, "guanxin.db"),
        CHECKPOINT_DATABASE_PATH: path.join(e2eRoot, "checkpoints.db"),
        CHROMA_PERSIST_DIR: path.join(e2eRoot, "chroma"),
        UPLOAD_DIR: path.join(e2eRoot, "uploads"),
        USER_DATA_PATH: path.join(e2eRoot, "users.json"),
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
      reuseExistingServer,
    },
  ],
})
