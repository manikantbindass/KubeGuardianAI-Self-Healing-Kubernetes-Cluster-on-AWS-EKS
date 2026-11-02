import { cp, mkdir } from "node:fs/promises";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("../../", import.meta.url));
const dashboard = path.join(root, "apps", "dashboard");
const standalone = path.join(dashboard, ".next", "standalone", "apps", "dashboard");
await mkdir(path.join(standalone, ".next"), { recursive: true });
await cp(path.join(dashboard, ".next", "static"), path.join(standalone, ".next", "static"), { recursive: true });
const child = spawn(process.execPath, [path.join(standalone, "server.js")], {
  cwd: root,
  stdio: "inherit",
  env: { ...process.env, HOSTNAME: "127.0.0.1", PORT: process.env.PORT ?? "3000" },
});
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
child.on("exit", code => process.exit(code ?? 1));
child.on("error", error => { console.error(error.message); process.exit(1); });
