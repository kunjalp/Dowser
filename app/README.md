# Dowser Command Map (Next.js)

Desktop Command Map: Esri satellite basemap, live ranked list (left), candidate dots colored by score or status, a detail panel that slides in on click, and a placeholder for the historical-map overlay (Saturday). Everything is live from Convex.

## Run it

```powershell
# 1. At the repo root, keep `npx convex dev` running (it generates convex/_generated, which this app imports).
cd app
npm install
Copy-Item .env.local.example .env.local      # then edit NEXT_PUBLIC_CONVEX_URL (the .convex.cloud URL)
npm run dev                                  # http://localhost:3000
```

No candidates showing? `npx convex run seed:seedFakeCandidates` at the repo root.

## Where things are

| File | What it does |
| --- | --- |
| `src/app/page.tsx` | Page: the live `candidates:ranked` query, selection and status filter |
| `src/components/MapView.tsx` | MapLibre map, candidate layer, selection ring, legend, historical toggle placeholder |
| `src/components/Sidebar.tsx` | Ranked list and status filter chips |
| `src/components/DetailPanel.tsx` | Score bars, nearby distances, evidence, brief, readings sparkline, status buttons |
| `src/lib/types.ts` | Candidate type, status colors, score color ramp. Keep in sync with `convex/schema.ts` |

## Notes

- **Basemap:** Esri World Imagery, no key. Swap with `NEXT_PUBLIC_BASEMAP_URL` (and `NEXT_PUBLIC_BASEMAP_ATTRIBUTION`) if a sponsor offers tiles. Keep the attribution.
- **MapLibre worker:** MapLibre 6 finds its worker relative to its own script, which breaks under Next's bundler. `scripts/copy-maplibre-worker.mjs` copies it to `public/maplibre/` (runs on install, dev and build) and `MapView` calls `setWorkerUrl`. If the map is blank and the console says "Worker failed to load", run `node scripts/copy-maplibre-worker.mjs`.
- **Status buttons** call `candidates:setStatus` with source `analyst`, which logs a status event and moves a confirmed leak to rank 1.
- Not built yet (Master Plan): historical overlay, documented-wells layer, priority sliders, rank-change animation, demo-mode banner.
