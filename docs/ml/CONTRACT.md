# ML/backend contract

Source of truth: [Master Plan sections 4–6](../master-plan/source.txt).
Backend/schema inspected at `f7e5eeb`, incorporated into the ML preparation branch.
The original PRD and the old `15f7c8f` schema are superseded.

## Ownership and delivery

Emir owns tiling, symbol labels, YOLO, inference, pixel-to-geo conversion, crops,
and detector metrics. Ryann owns 20 m dedup across tiles/editions, CalGEM matching,
OSM enrichment, scoring, loading candidates, and publishing evidence crops.
Kunjal owns Command Map and Field View; Ryann prepares historical overlays.

MVP uses preprocessed tiles. A live upload/detection service is could-have and
must not block the offline handoff. ML delivers local detection JSONL, tile
manifests, crop files, source provenance, and metrics. A local crop path becomes
`cropUrl` only after Ryann publishes it; never invent an accessible URL.

## Existing backend tiles and detections

Tile fields in [schema](../../convex/schema.ts): `tileId`, `sheetName`, `mapYear`,
`transform`, `crs`, `widthPx`, `heightPx`, and `bounds`
(`minLon`, `minLat`, `maxLon`, `maxLat`). `transform` is rasterio order
`[a,b,c,d,e,f]`: `X=a*x+b*y+c`, `Y=d*x+e*y+f`. Preserve custom source CRS WKT.

| Detection field | Meaning |
| --- | --- |
| detectionId | Stable application string ID |
| tileId | Source tile ID |
| mapYear | Date-on-map, required in current backend |
| box | `{x,y,w,h}` in original tile pixels; top-left origin, edge convention |
| className | Proposed single class `well_symbol` |
| confidence | Numeric model score; not a calibrated probability |
| lat, lon | WGS84 center coordinates |
| cropUrl | Optional published crop URL/path |
| source | `model` or `ground_truth` |

For an xywh box the center is `(x+w/2, y+h/2)`; do not add another half pixel.
Undo inference resize/letterboxing before conversion. `pipeline.geo` implements
the native pixel-edge convention, finite-value checks, and per-tile transforms.

Ground-truth annotation files naturally have no model confidence. Backend still
requires a number: fallback confidence/ranking semantics remain an explicit
coordination item. Current preparation creates no fake confidence, detections,
or unreviewed ground truth.

## Candidate and reading contracts

Ryann's final candidate uses `id`, `score`,
`scoreParts {confidence, undocumented, people, water, field}`, `editionsSeen`,
`status`, `evidenceImages [{year,url}]`, `quadName`, coordinates, and optional
matching/enrichment/provenance fields. See the current schema for full fields.
`candidates:upsertBatch` and bulk import are implemented; the old statement that
no candidate loading path exists is obsolete.

Exact statuses: `candidate`, `queued`, `confirmed_leaking`,
`confirmed_not_leaking`, `no_well`, `mislocated`. Manual field logging is P0;
three-reading auto-confirmation is P1 and is now implemented in main (three
readings >=1000 within 30 s for a candidate/queued item; threshold still needs
hardware calibration). Readings use `value`, `timestamp`, and
`candidateId`, replacing `corrected`, `ts`, and `wellId`.

Application IDs are strings. Indexes alone enforce neither uniqueness nor
referential integrity; consumers must preserve idempotent loading behavior.

## Dates, artifacts, and checks

The [region config](../../pipeline/config/region.json) records base, revision,
and imprint dates separately. Oil Center 293661 is base 1954 with 1968 revision,
not an unchanged 1954 snapshot. Overlapping years share geographic partitions.
Full source hashes live in the tile manifest.

Deduplication (20 m), matching (100 m), and proximity (250 m) remain backend
configuration. Distances use EPSG:3310. Coordinate-operation accuracy and
map/survey accuracy are separate; report known-well offsets after those checks.

No deployment, schema change, paid API, or paid resource was invoked for ML
preparation. Backend code remains exactly as received from main.
Main also contains Command Map/Field View and `pipeline/geotiff_to_overlay.py`;
these are team implementations, not additional ML scope. Source integration
does not establish deployed behavior or verify the UI end to end.
