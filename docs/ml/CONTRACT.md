# ML to backend contract: schema baseline and open decisions

Baseline inspected: `convex/schema.ts` at `15f7c8f`. The stored fields below
already exist. Pixel conventions and extensions are proposals requiring backend
agreement. This document does not change the schema or add an ingest endpoint.

## Boundary

ML delivers tile metadata and detections with geographic coordinates and evidence.
Backend performs CalGEM matching, proximity calculations, ranking, and persistence.
Upload orchestration and storage IDs must be agreed jointly. Keep model score
separate from backend map confidence, risk score, and record-match distance.

## Transport and persistence: not implemented yet

The current backend exposes reading ingest and a recent-readings query only.
There is no upload/ingest function for tiles or detections. ML should first
produce local manifest/JSON fixtures matching the stored shape; backend must
implement and agree their ingestion path before claiming an integrated pipeline.
The full [main review](../MAIN_REVIEW.md) describes the available source surface.

Application IDs are strings rather than Convex document IDs. Their indexes do
not enforce uniqueness or referenced-row existence. Agree idempotent writes,
tile-before-detection behavior, and duplicate IDs at the ingestion boundary.

## Tile manifest

The current table requires `tileId`, `sheetName`, `mapYear`, `transform`, `crs`,
`widthPx`, `heightPx`, and `bounds` (`minLon`, `minLat`, `maxLon`, `maxLat`).
`transform` uses rasterio order `[a, b, c, d, e, f]` in the sheet's CRS:
`worldX = a * col + b * row + c`; `worldY = d * col + e * row + f`.
The array validator does not enforce length; ML must validate six finite values.

ML's versioned manifest should additionally preserve source URI/checksum, tile
offset, and split/source group outside the current Convex row. Do not send extra
fields to the table without an agreed schema change. Agree pixel-center and
edge conventions before implementation. Do not discard rotation/shear or infer
georeferencing from a filename.

Region research selected the maps in `ml/config/region.json`. Keep `mapYear`
consistent with their date-on-map while preserving photo revision and imprint
dates separately in the external manifest. Oil Center 293661 is labeled 1954 but
photorevised 1968; treating it as an unchanged 1954 snapshot would be misleading.

## Detection record

| Existing field | Stored form and intended interpretation |
| --- | --- |
| detectionId | Stable identity for an inference/annotation record; agree retry/dedup policy |
| tileId | Reference to the manifest |
| box | Object `{x, y, w, h}`; proposed convention: top-left origin, original tile pixel units, edge coordinates |
| className | String; proposed single class value `well_symbol` |
| confidence | Required number; model score in [0, 1]; ground-truth semantics unresolved |
| lat, lon | WGS84 box-center coordinates; explicitly named fields avoid axis ambiguity |
| source | `model` or `ground_truth` |

For the proposed edge convention, the center is `(x + w/2, y + h/2)`.
Convert internal YOLO labels/xyxy arrays into this object at the export boundary.
`cropUri` and `runId` are useful proposed extensions but are absent from the
current schema. Keep evidence/provenance in an external manifest until backend
agrees where it will be stored and how the UI will retrieve it.

Coordinate conversion must undo inference resize/letterboxing before using the
tile transform. Validate finite values, image bounds, coordinate range, and the
region footprint. A successful run with no detections returns an empty list; a
failed run returns an explicit failure, never a fabricated empty success.

Ground-truth fallback must not masquerade as model output or assign confidence
1.0 as if it were a model probability. The current schema rejects `null`, so the
earlier null-confidence proposal is not compatible. Backend/UI must agree either
an explicit nullable/type extension or documented annotation-score semantics
that keep ranking and display honest. This remains an open interface decision.

Deduplication should preserve contributing tile/crop references. Repeated runs,
overlap deduplication, and cross-era agreement have different meanings; define
their IDs and aggregation rules before writing persistent data.

## Approval checklist

- Field names/types and bbox/coordinate conventions agreed with backend.
- Ground-truth representation and rank/UI behavior agreed.
- Tile manifests, crop storage, delivery, retry behavior, and errors agreed.
- Backend provides an agreed ingestion function; its existence is verified in code.
- One small versioned fixture consumed by the backend before model training.
- Breaking changes include a consumer update or explicit migration plan.

Reference: [current schema](../../convex/schema.ts). Recheck against the current
branch before implementation; this baseline can evolve while teammates work.
