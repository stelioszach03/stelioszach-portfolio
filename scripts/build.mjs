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
// Version documents and previews along with CSS/JS. Every CV entry point must
// resolve to the same Jobright export when a new PDF replaces the previous one.
const versions = new Map();
for (const relative of ["assets/site.css", "assets/site.js", "Stelios_Zacharioudakis_CV.pdf", "assets/cv-preview-jobright.jpg"]) {
  const version = createHash("sha256")
    .update(await readFile(new URL(relative, destination)))
    .digest("hex")
    .slice(0, 12);
  versions.set(relative, version);
}
for (const page of ["index.html", "cv/index.html"]) {
  const htmlFile = new URL(page, destination);
  let builtHtml = await readFile(htmlFile, "utf8");
  for (const [relative, version] of versions) {
    for (const prefix of ["/", "https://stelioszach.com/"]) {
      builtHtml = builtHtml.replaceAll(`"${prefix}${relative}"`, `"${prefix}${relative}?v=${version}"`);
    }
  }
  await writeFile(htmlFile, builtHtml);
}

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
