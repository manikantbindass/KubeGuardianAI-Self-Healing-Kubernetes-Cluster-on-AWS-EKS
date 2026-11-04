import { readFile } from "node:fs/promises";

const { packages } = JSON.parse(await readFile("package-lock.json", "utf8"));
let checked = 0;
for (const [owner, entry] of Object.entries(packages)) {
  for (const [name, version] of Object.entries(entry.optionalDependencies ?? {})) {
    if (!/^(?:@next\/swc-|@rolldown\/binding-|@tailwindcss\/oxide-|lightningcss-|@esbuild\/)/.test(name)) continue;
    const present = Object.entries(packages).some(([key, value]) =>
      (key.endsWith(`/node_modules/${name}`) || key === `node_modules/${name}`) && value.version === version);
    if (!present) throw new Error(`${owner}: missing optional native package ${name}@${version}; regenerate lock without node_modules`);
    checked++;
  }
}
if (!checked) throw new Error("No native dependency declarations checked");
console.log(`PASS: ${checked} optional native dependency declarations have locked packages`);
