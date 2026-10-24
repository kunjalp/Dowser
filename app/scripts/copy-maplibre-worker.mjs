// MapLibre 6 locates its worker relative to its own script URL, which breaks once Next bundles it.
// We serve the worker file from /public/maplibre and call setWorkerUrl (see MapView).
import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(import.meta.url);
const dist = path.join(path.dirname(require.resolve("maplibre-gl/package.json")), "dist");
const out = path.join(process.cwd(), "public", "maplibre");
mkdirSync(out, { recursive: true });
for (const f of ["maplibre-gl-worker.mjs"]) copyFileSync(path.join(dist, f), path.join(out, f));
console.log("copied maplibre worker to public/maplibre");
