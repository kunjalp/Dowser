# Dowser

Finds candidate undocumented orphaned oil and gas wells on historical USGS maps, ranks them for plugging crews, and confirms leaks in the field with a handheld methane sensor. Cal Hacks 13.0, Climate track. The team's Master Plan is the single source of truth; this README restates the data contracts from its section 5 so everyone codes against the same thing.

> Detections are **candidates**, not verified wells. The sensor demo is **simulated**. The MQ-4 is a demo-grade indicator, not a calibrated instrument.

Layout: `/app` (Next.js) · `/convex` (backend) · `/pipeline` (Python) · `/firmware` (ESP32). Raw map sheets stay out of git.

## Team and ML documentation

Start with the [documentation index](docs/README.md) and
[ML status and next action](docs/ml/STATUS.md). The
[contribution guide](CONTRIBUTING.md) describes task branches and PR review;
[ML requirements](docs/ml/REQUIREMENTS.md) track Master Plan acceptance evidence.
The [ML/backend contract](docs/ml/CONTRACT.md) distinguishes the existing schema
from interface decisions that still need backend agreement. The full
[Master Plan](docs/master-plan/source.txt) is the current source of truth;
the [original PRD](docs/prd/source.txt) is retained as superseded history.

## Region (FR-1.1)

ML MVP selection: **Kern County, Oil Center + Oildale**, northeast Bakersfield.
WGS84 study bbox, ordered west/south/east/north:
`[-119.125, 35.375, -118.875, 35.500]` (about 314.82 km²).

Start with **USGS Oil Center 293661**, 1:24,000 GeoTIFF: date-on-map 1954,
photorevised 1968, printed 1970. Add **Oildale 293664 (1954)** and
**Oil Center 102321 (1992)**. The 1978 Oil Center edition is an orthophotomap
and is excluded from the initial symbol detector.

See the [research and comparison](docs/research/REGION_SELECTION.md) and
[exact files, URLs, bounds and SHA-256 hashes](pipeline/config/region.json).
The `kern` and `la_basin` presets in `pipeline/load_calgem.py` remain broad
approximate boxes; the config is not yet wired into that loader. Use the explicit
buffered bbox below so reference wells outside the study edge remain matchable.

Kern County, oil-producing quadrangles, 1947 to 1992 editions. Distances are computed in California Albers (EPSG:3310); lat/lon stored in WGS84.

## Offline ML preparation (Emir)

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r pipeline/requirements.txt
.venv/bin/python -m pipeline.download_sources
.venv/bin/python -m pipeline.prepare_dataset
.venv/bin/python -m unittest discover -s pipeline/tests -v
```

Original preparation output: `data/ml/kern_1024_v1/`. Native 1024 px tiles use 819 px stride
(about 20% overlap), per-tile CRS/affine and masked collars. The fixed geographic
split has 84 train / 13 val / 30 test images; 62 crossing windows are quarantined.
Preparation creates **unlabeled** images, not negative examples. The active split
is now `kern_1024_v2`, preserving human Train/Test while improving Val coverage;
the current human Train import has 5 images/568 boxes. Use
[ML status](docs/ml/STATUS.md) for active paths and the 15-image Validation task.
See the
[labeling handoff](docs/ml/ANNOTATION.md) before importing or training.
No paid services or cloud training are invoked. Preparation refuses to overwrite
an existing dataset; use `--output` with a new version for a deliberate rerun.

## Data contracts (Master Plan section 5)

**Status values** (exactly these): `candidate`, `queued`, `confirmed_leaking`, `confirmed_not_leaking`, `no_well`, `mislocated`.

**Candidate record** (pipeline to Convex to app): `id`, `lat`, `lon`, `score`, `scoreParts {confidence, undocumented, people, water, field}` (each 0..1), `editionsSeen` (list of map years, e.g. `[1947, 1962]`), `nearestDocumentedId`, `nearestDocumentedDistM`, `distToHomeM`, `distToSchoolM`, `distToWaterM`, `buildingsNear250m`, `status`, `brief`, `evidenceImages [{year, url}]`, `quadName`, `detectionId`, `source` (`model` or `ground_truth`). Only `id`, `lat`, `lon`, `score`, `scoreParts`, `editionsSeen`, `status`, `evidenceImages` and `quadName` are required; the rest can arrive later from enrichment.

**Reading record** (sensor to Convex): `deviceId`, `value` (relative, baseline-corrected), `raw`, `timestamp`, `candidateId` (attached by the phone), `lat`, `lon`, `locationSource` (`candidate`, `phone` or `none`), `isReplay`.

## Backend setup (Convex)

```bash
npm install
npx convex dev                                   # log in, create/select the project, push convex/
npx convex env set INGEST_TOKEN "<random token>" # share through the team's secure note, never git
npm test                                         # backend tests (needs the generated code from convex dev)
```

### Sensor endpoint

`POST https://<deployment>.convex.site/ingest/reading` (HTTP actions live on `.convex.site`, not `.convex.cloud`)

| Header | Value |
| --- | --- |
| `X-Dowser-Token` | the `INGEST_TOKEN` |
| `Content-Type` | `application/json` |

```json
{ "deviceId": "esp32-1", "value": 12.5, "raw": 512, "timestamp": 1792800000000, "isReplay": false }
```

Required: `deviceId`, `value`. Everything else is optional. The device normally does **not** send `candidateId`, `lat` or `lon`: the phone sets a pairing and the server attaches it (see below). `timestamp` may be omitted (no wall clock on the ESP32) or wrong; the server stores its own `receivedAt` and falls back to it if the device time is more than a day off. Returns `201 {ok, id, receivedAt, candidateId}`; `candidateId` is `null` if nothing was paired. `GET /health` needs no token: hit it from the phone hotspot first. Smoke tests: `scripts/post_reading.ps1` (Windows) or `scripts/post_reading.sh`.

Firmware note: the demo uses an insecure HTTPS client setting. Keep this note.

### Functions the frontend calls

| Function | What it does |
| --- | --- |
| `candidates:ranked {statuses?, weights?, limit?}` | Live ranked list. A confirmed leak always ranks first. Pass `weights` (the five scoreParts keys) for live slider re-ranking; nothing is written. Returns `rankScore` and `rank`. Caps at 2000 candidates. |
| `candidates:get {id}` | One candidate. |
| `candidates:setStatus {id, status, source?, note?}` | Changes status and logs a `statusEvent`. Entering `confirmed_leaking` sets `scoreParts.field` to 1. No-op if unchanged. |
| `candidates:eventsFor {id}` | Status history, newest first. |
| `fieldChecks:generateUploadUrl` | Upload URL for a finding photo. |
| `fieldChecks:logFinding {candidateId, outcome, note?, photoId?, deviceId?, lat?, lon?}` | One tap from the Field View: stores the check and sets the status. |
| `pairing:set {candidateId, deviceId?, lat?, lon?}` | The phone says which candidate the handheld is at and where the phone is. Without a `deviceId` it pairs whichever device posts next. Expires after 30 minutes. |
| `pairing:clear`, `pairing:current` | Clear or read the pairing. |
| `readings:recent {candidateId?, limit?}` | Live readings feed, newest first. |

Pipeline and demo helpers are internal and run from the CLI:

```bash
npx convex run seed:seedFakeCandidates               # 50 fake candidates (ids start "fake-"), safe to re-run
npx convex run seed:clearFake                        # remove them when real candidates are in
npx convex run candidates:upsertBatch '{"candidates":[...]}'
npx convex import --table candidates --replace data/candidates.jsonl   # bulk load from the pipeline
```

## Records cross-check data

```bash
pip install requests
python3 pipeline/load_calgem.py --region kern --bbox -119.131 35.370 -118.869 35.505 --inspect
python3 pipeline/load_calgem.py --region kern --bbox -119.131 35.370 -118.869 35.505 --api-pad 10
npx convex import --table documentedWells --replace data/calgem/calgem_wells.jsonl
```

Offline option: download the "WellSTAR: Oil and Gas Wells" CSV from data.ca.gov and pass `--csv path/to/file.csv`. Outputs `calgem_wells.jsonl`, `calgem_wells.geojson` (good coordinates only) and `bad_rows.log`. Wells with missing, zero, out-of-state or low-precision coordinates are kept as `locationQuality: "uncertain"` and excluded from matching, with a count. API numbers are 10-digit strings.

Note on statuses: CalGEM's `WellStatus` includes `Canceled` (permit canceled, usually never drilled). Decide before the cross-check whether canceled wells count as "documented". Tests: `python pipeline/test_load_calgem.py`.

## Data sources and licenses

- CalGEM WellSTAR well records, California Department of Conservation (state open data).
- USGS TopoView historical maps (public domain, credit USGS).
- OpenStreetMap (c) OpenStreetMap contributors, ODbL.
- TODO: confirm each source's terms before submission. Credit the Berkeley Lab research.

## Where Claude, Convex, Droid and Apify are used

TODO: fill in as each ships. Droid and Apify are could-haves; if they are not working by Saturday 9 PM they are cut and the track is not claimed.
