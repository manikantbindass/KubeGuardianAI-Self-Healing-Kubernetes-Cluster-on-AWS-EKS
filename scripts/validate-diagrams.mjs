import { readdir, readFile } from "node:fs/promises";
import { JSDOM } from "jsdom";
const dom = new JSDOM("<!doctype html><html><body></body></html>");
globalThis.window = dom.window;
globalThis.document = dom.window.document;
const { default: mermaid } = await import("mermaid");
mermaid.initialize({ startOnLoad: false, securityLevel: "strict" });
let count = 0;
for (const file of await readdir("docs/diagrams")) {
  if (!file.endsWith(".mmd")) continue;
  await mermaid.parse(await readFile(`docs/diagrams/${file}`, "utf8"));
  console.log(`PASS ${file}`);
  count++;
}
if (!count) throw new Error("No Mermaid sources found");
