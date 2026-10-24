# Dowser

Finds candidate undocumented orphaned oil and gas wells on historical USGS maps, ranks them for plugging crews, and confirms leaks in the field with a handheld methane sensor. Cal Hacks 13.0, Climate track. Product requirements live in the team PRD.

> Detections are **candidates**, not verified wells. The sensor demo is **simulated**. The MQ-4 is a demo-grade indicator, not a calibrated instrument.

## Team and ML documentation

Start with the [documentation index](docs/README.md) and
[ML status and next action](docs/ml/STATUS.md). The
[contribution guide](CONTRIBUTING.md) describes task branches and PR review;
[ML requirements](docs/ml/REQUIREMENTS.md) track PRD acceptance evidence.
The [ML/backend contract](docs/ml/CONTRACT.md) distinguishes the existing schema
from interface decisions that still need backend agreement. The full
[October 23 PRD](docs/prd/source.txt) is preserved as supplied.

## Region (FR-1.1)

ML MVP selection: **Kern County, Oil Center + Oildale**, northeast Bakersfield.
WGS84 study bbox, ordered west/south/east/north:
`[-119.125, 35.375, -118.875, 35.500]` (about 314.82 km²).

Start with **USGS Oil Center 293661**, 1:24,000 GeoTIFF: date-on-map 1954,
photorevised 1968, printed 1970. Add **Oildale 293664 (1954)** and
**Oil Center 102321 (1992)**. The 1978 Oil Center edition is an orthophotomap
and is excluded from the initial symbol detector.

See the [research and comparison](docs/research/REGION_SELECTION.md) and
[exact files, URLs, bounds and SHA-256 hashes](ml/config/region.json).
The `kern` and `la_basin` presets in `scripts/load_calgem.py` remain broad
approximate boxes; the config is not yet wired into that loader. Use the explicit
buffered bbox below so reference wells outside the study edge remain matchable.

## Setup: backend (Convex)

```bash
npm install
npx convex dev                                   # log in, create the project, push convex/
npx convex env set INGEST_TOKEN "$(openssl rand -hex 24)"
```

Share the token with the hardware lead through the team's secure note, not git (NFR-5).

### Ingest endpoint (FR-7.3)

`POST https://<deployment>.convex.site/ingest/reading` (the HTTP-actions host ends in `.convex.site`, not `.convex.cloud`)

| Header | Value |
| --- | --- |
| `X-Dowser-Token` | the `INGEST_TOKEN` |
| `Content-Type` | `application/json` |

```json
{ "deviceId": "esp32-1", "raw": 512, "corrected": 12,
  "ts": 1792800000000, "wellId": "cand-001", "isReplay": false }
```

Required: `deviceId`, `raw`, `corrected`. Optional: `ts` (the server falls back to its own clock if absent or off by more than a day), `wellId` or `lat`+`lon`, `locationSource`, `isReplay`. Returns `201 {ok, readingId, receivedAt}`. `GET /health` is a no-auth reachability check; hit it from the phone hotspot first. Smoke test: `scripts/post_reading.sh`.

Firmware note: use an HTTPS client on the ESP32 and write down any certificate shortcut you take for the demo.

## Records cross-check data (FR-4.1)

```bash
pip install requests
python3 scripts/load_calgem.py --region kern --bbox -119.131 35.370 -118.869 35.505 --inspect
python3 scripts/load_calgem.py --region kern --bbox -119.131 35.370 -118.869 35.505
npx convex import --table documentedWells --replace data/calgem/calgem_wells.jsonl
```

Offline option: download the "WellSTAR: Oil and Gas Wells" CSV from data.ca.gov and pass `--csv path/to/file.csv`.
Output also includes `calgem_wells.geojson` (good coordinates only) and `bad_rows.log`. Wells with missing, zero, out-of-state or low-precision coordinates are kept as `locationQuality: "uncertain"` and excluded from matching (FR-4.5). Tests: `python3 scripts/test_load_calgem.py`.

## Data sources and licenses

- CalGEM WellSTAR well records, California Department of Conservation (state open data).
- USGS TopoView historical maps (public domain, credit USGS).
- OpenStreetMap (c) OpenStreetMap contributors, ODbL.
- TODO: confirm each source's terms before submission.

## Where Droid is used (FR-D8)

TODO Saturday: trigger, task, permissions and an example run.
