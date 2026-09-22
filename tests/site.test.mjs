import test from "node:test";
import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";
import vm from "node:vm";
import { createHash } from "node:crypto";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
const publicRoot = new URL("../public/", import.meta.url);
const html = (
  await readFile(new URL("index.html", publicRoot), "utf8")
).replace(/\s+/g, " ");
const css = await readFile(new URL("assets/site.css", publicRoot), "utf8");
const script = await readFile(new URL("assets/site.js", publicRoot), "utf8");

test("semantic static page delivers the author and every section before JavaScript", () => {
  assert.equal((html.match(/<h1\b/g) || []).length, 1);
  assert.match(html, /<html lang="en">/);
  assert.match(html, /<h1[^>]*aria-label="Hi, I’m Stelios Zacharioudakis"/);
  for (const title of [
    "Selected work",
    "Live demos",
    "BSc thesis",
    "Ongoing · Unpublished",
    "Head Engineer",
    "Completed June 2026",
  ])
    assert.ok(html.includes(title), title);
  assert.doesNotMatch(html, /<noscript>.*enable javascript/i);
});

test("every same-page destination exists and IDs are unique", () => {
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]);
  assert.equal(new Set(ids).size, ids.length);
  for (const [, hash] of html.matchAll(/href="#([^"]+)"/g))
    assert.ok(ids.includes(hash), hash);
});

test("all local assets resolve, preserving the historical CV URL and four demo routes", async () => {
  const local = [...html.matchAll(/(?:href|src)="(\/[^"#?]+)[^"]*"/g)].map(
    (m) => m[1],
  );
  const demoLinks = new Set(local.filter((href) => href.startsWith("/demos/")));
  assert.deepEqual([...demoLinks].sort(), [
    "/demos/deid/",
    "/demos/fraud-graph/",
    "/demos/mta-scan/",
    "/demos/smt-verify/",
  ]);
  for (const asset of new Set(
    local.filter((href) => !href.startsWith("/demos/")),
  ))
    assert.ok((await stat(new URL(`.${asset}`, publicRoot))).size > 0, asset);
  for (const asset of [
    "Stelios_Zacharioudakis_CV.pdf",
    "documents/zacharioudakis-bsc-thesis-2026.pdf",
  ])
    assert.equal(
      (await readFile(new URL(asset, publicRoot))).subarray(0, 5).toString(),
      "%PDF-",
    );
});

test("research and product claims retain their scope instead of publication or safety claims", () => {
  assert.match(html, /ongoing, unpublished research/);
  assert.match(html, /no prospective scanner study or clinical validation/i);
  assert.match(html, /rule-derived training labels/);
  assert.match(
    html,
    /single-VPS deployment is not a highly available infrastructure/,
  );
  assert.doesNotMatch(
    html,
    /expected June|fourth.year|four years|SOTA|revolutionary|\/papers\/|480.doctor|Stripe|iOS client/i,
  );
});

test("assets are self-hosted and interactions do not send analytics or contact data", () => {
  assert.doesNotMatch(html, /<script[^>]*src="https?:/);
  assert.doesNotMatch(
    html,
    /<link[^>]*rel="(?:stylesheet|preload)"[^>]*href="https?:/,
  );
  assert.doesNotMatch(
    script,
    /\bfetch\s*\(|XMLHttpRequest|sendBeacon|localStorage|sessionStorage|document\.cookie/,
  );
  assert.doesNotMatch(html, /<form\b/);
  assert.match(css, /prefers-reduced-motion:\s*reduce/);
  assert.match(css, /--navy:\s*#0a192f/);
  assert.match(css, /--accent:\s*#64ffda/);
  assert.match(html, /class="skip-link" href="#content"/);
});

function menuFixture() {
  const handlers = new Map();
  const state = {
    expanded: "false",
    open: false,
    focused: false,
    enhanced: false,
    breakpoint: null,
  };
  const menu = {
    hidden: true,
    setAttribute: (key, value) => {
      if (key === "aria-expanded") state.expanded = value;
    },
    getAttribute: () => state.expanded,
    addEventListener: (type, callback) =>
      handlers.set(`menu:${type}`, callback),
    focus: () => {
      state.focused = true;
    },
  };
  const nav = {
    toggleAttribute: (_, open) => {
      state.open = open;
    },
    addEventListener: (type, callback) => handlers.set(`nav:${type}`, callback),
  };
  const document = {
    querySelector: () => menu,
    getElementById: () => nav,
    documentElement: {
      classList: {
        add: () => {
          state.enhanced = true;
        },
      },
    },
    addEventListener: (type, callback) =>
      handlers.set(`document:${type}`, callback),
  };
  vm.runInNewContext(script, {
    document,
    matchMedia: () => ({
      addEventListener: (_, callback) => {
        state.breakpoint = callback;
      },
    }),
  });
  return { menu, state, handlers };
}
test("mobile menu expands, Escape closes and restores focus, navigation closes it", () => {
  const { menu, state, handlers } = menuFixture();
  assert.equal(menu.hidden, false);
  assert.equal(state.enhanced, true);
  handlers.get("menu:click")();
  assert.equal(state.expanded, "true");
  assert.equal(state.open, true);
  handlers.get("document:keydown")({ key: "Escape" });
  assert.equal(state.open, false);
  assert.equal(state.focused, true);
  handlers.get("menu:click")();
  handlers.get("nav:click")({ target: { closest: () => ({}) } });
  assert.equal(state.expanded, "false");
});
test("crossing the desktop breakpoint clears stale mobile menu state", () => {
  const { state, handlers } = menuFixture();
  handlers.get("menu:click")();
  state.breakpoint();
  assert.equal(state.expanded, "false");
  assert.equal(state.open, false);
});
test("missing enhancement targets fail open and do not hide static navigation", () => {
  let hidden = false;
  vm.runInNewContext(script, {
    document: {
      querySelector: () => null,
      getElementById: () => null,
      documentElement: {
        classList: {
          add: () => {
            hidden = true;
          },
        },
      },
    },
  });
  assert.equal(hidden, false);
});

test("build versions CSS/JS by content and hashes the final HTML without changing source", async () => {
  const root = new URL("../", import.meta.url);
  const original = await readFile(new URL("index.html", publicRoot), "utf8");
  await promisify(execFile)(process.execPath, [
    fileURLToPath(new URL("scripts/build.mjs", root)),
  ]);
  const built = await readFile(new URL("dist/index.html", root), "utf8");
  for (const relative of ["assets/site.css", "assets/site.js"]) {
    const bytes = await readFile(new URL(`dist/${relative}`, root));
    const version = createHash("sha256")
      .update(bytes)
      .digest("hex")
      .slice(0, 12);
    assert.ok(
      built.includes(`"/${relative}?v=${version}"`),
      `${relative} requires content version`,
    );
  }
  const manifest = JSON.parse(
    await readFile(new URL("build-manifest.json", root), "utf8"),
  );
  assert.equal(
    manifest["index.html"],
    createHash("sha256").update(built).digest("hex"),
  );
  assert.equal(
    await readFile(new URL("index.html", publicRoot), "utf8"),
    original,
  );
});
