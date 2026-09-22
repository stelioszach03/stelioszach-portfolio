// Syntax validation only; no browser scripts, network or model code are executed.
import { readFile } from "node:fs/promises";
import { Script } from "node:vm";
const root = new URL("../", import.meta.url);
let count = 0;
for (const service of ["deid", "fraud-graph", "mta-scan", "smt-verify"]) {
  const html = await readFile(new URL(`${service}/static/index.html`, root), "utf8");
  for (const [, attributes, source] of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)) {
    if (/\bsrc\s*=/.test(attributes)) continue;
    if (/type=["']application\/(?:ld\+)?json["']/.test(attributes)) JSON.parse(source);
    else new Script(source, { filename: `${service}/static/index.html` });
    count += 1;
  }
}
new Script(await readFile(new URL("mta-scan/static/vendor/leaflet.js", root), "utf8"), { filename: "leaflet.js" });
if (count < 4) throw new Error("Expected an inline application script in each demo");
console.log(`Parsed ${count} inline application scripts and Leaflet without executing them.`);
