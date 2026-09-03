import { spawnSync } from "node:child_process"
import fs from "node:fs"
import os from "node:os"
import path from "node:path"

const root = fs.mkdtempSync(path.join(os.tmpdir(), "guanxin-e2e-"))
const executable = process.platform === "win32" ? "npx.cmd" : "npx"

try {
  const result = spawnSync(executable, ["playwright", "test", ...process.argv.slice(2)], {
    env: { ...process.env, GUANXIN_E2E_ROOT: root },
    stdio: "inherit",
  })
  if (result.error) throw result.error
  process.exitCode = result.status ?? 1
} finally {
  const resolved = path.resolve(root)
  const tempRoot = `${path.resolve(os.tmpdir())}${path.sep}`
  if (!resolved.startsWith(tempRoot) || !path.basename(resolved).startsWith("guanxin-e2e-")) {
    throw new Error(`Refusing to remove unexpected E2E directory: ${resolved}`)
  }
  fs.rmSync(resolved, { recursive: true, force: true })
}
