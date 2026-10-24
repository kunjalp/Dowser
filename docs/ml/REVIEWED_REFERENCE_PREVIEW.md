# Coherent map-reference preview

Prepared 2026-10-24 at Emir's request to show actual well rings with matching
images/descriptions and retain one or two error examples. Runtime implementation
is in `/Users/emirtg/Desktop/dowser-preview`; no production rows were replaced.

Open http://127.0.0.1:3000/reviewed. The existing team map remains at `/` and
on Vercel with its existing backend data.

## Dataset and meaning

- 62 distinct, human-annotated historical rings selected from `reviewed_v2`
  Train images, with an assistant visual check of the evidence contact sheet.
- Two actual Ryann-rejected model detections retained with explicit rejection
  labels; their original detection IDs and model confidence are preserved.
- Every point has its own original-source crop, larger map context with the
  native box marked, per-tile WGS84 centre, sheet/year, nearest usable CalGEM
  record/distance, record status and deterministic description.
- The 62 references are at least 20 m apart, with unique crop hashes. Sources
  cover 1954/1992. No protected Test labels/images or training runs were used.
- All 568 original human Train boxes were checked against the pinned CalGEM
  snapshot: each had a record within 100 m. The selected 62 therefore remain
  **record-matched historical reference examples**, not undocumented discoveries.
  Proximity is not proof of exact well identity, present condition or a leak.
- Unrecomputed home/school/water facts remain unknown. No old distances,
  briefs, field findings or model scores were copied to different coordinates.
- `source=ground_truth` identifies the human annotation origin. The page labels
  manual reference selection; 62/64 is not detector precision or a new Test result.

## Files and checks

Preview-only implementation:

- `pipeline/build_reviewed_demo.py`: reproducible builder, needs the existing
  ML preparation environment and source checkout; source hashes/split checks.
- `app/src/app/reviewed/page.tsx` and `reviewed.css`: a separate, read-only
  review page with all/accepted/rejected filters and matched detail cards.
- `app/src/components/MapView.tsx`: optional review legend/initial fit; normal
  Command Map defaults preserved. Selection handles map-ready timing.
- `app/public/reviewed-demo/`: release.json, 128 evidence/context PNGs and contact
  sheet. Input hashes and evidence hashes are recorded in the release JSON.
- `data/research/proj` links to the source checkout's offline projection grids
  so georeferencing reproduces the established source operation.

Build/TypeScript checks passed. Final browser check clicks all 64 records,
verifies selected identity/crop/CalGEM facts, accepted/rejected filter counts,
image availability and sidebar layout; captures desktop/error/mobile screenshots.
First browser checks exposed stale Next development/build caches and a sidebar
grid overlap; both were corrected before the final run. Final evidence is in
`dowser-preview/reviewed-final-check/`. No production Convex POST is required.
All 128 final evidence hashes and 62 unique accepted crop hashes were checked.

The local page is isolated from candidate mutations/readings/pairing. It is not
the full Field View/live sensor workflow. Publishing it is a separate frontend
release; do not replace the shared candidates table with these record-matched
examples or reassign existing field decisions to them.

## Rebuild

From the integrated preview clone, preserve any existing output first:

```sh
/Users/emirtg/Desktop/dowser-cursor/.venv/bin/python -m pipeline.build_reviewed_demo \
  --source-root /Users/emirtg/Desktop/dowser-cursor \
  --out app/public/reviewed-demo
```

Builder refuses an existing output folder. Keep historical model archives and
reference pins unchanged. This preview addresses coherent reference evidence;
the automatic detector and review-ledger release remain governed by
[the integration plan](../INTEGRATION_QUALITY_PLAN.md).
