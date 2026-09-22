import {
  cp,
  mkdir,
  readFile,
  readdir,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";
const root = new URL("../", import.meta.url);
for (const relative of [
  "Stelios_Zacharioudakis_CV.pdf",
  "documents/zacharioudakis-bsc-thesis-2026.pdf",
]) {
  const bytes = await readFile(new URL(`public/${relative}`, root));
  if (bytes.subarray(0, 5).toString() !== "%PDF-")
    throw new Error(`Missing or invalid linked PDF: ${relative}`);
}
const destination = new URL("dist/", root);
await rm(destination, { recursive: true, force: true });
await mkdir(destination, { recursive: true });
await cp(new URL("public/", root), destination, { recursive: true });
const manifest = {};
async function walk(directory, prefix = "") {
  for (const entry of (await readdir(directory)).sort()) {
    const target = new URL(entry, directory);
    const name = path.posix.join(prefix, entry);
    if ((await stat(target)).isDirectory())
      await walk(new URL(`${entry}/`, directory), name);
    else
      manifest[name] = createHash("sha256")
        .update(await readFile(target))
        .digest("hex");
  }
}
await walk(destination);
await writeFile(
  new URL("build-manifest.json", root),
  `${JSON.stringify(manifest, null, 2)}\n`,
);
console.log(
  `Built ${Object.keys(manifest).length} static files in dist; no runtime dependencies.`,
);
