# Dowser

Finds candidate undocumented orphaned oil and gas wells on historical USGS maps, ranks them for plugging crews, and confirms leaks in the field with a handheld methane sensor. Cal Hacks 13.0, Climate track. Product requirements live in the team PRD.

> Detections are **candidates**, not verified wells. The sensor demo is **simulated**. The MQ-4 is a demo-grade indicator, not a calibrated instrument.

## Region (FR-1.1)

TODO at check-in: pick `kern` or `la_basin` and record the final bounding box here.
Starting boxes are in `scripts/load_calgem.py` (approximate, WGS84).

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
python3 scripts/load_calgem.py --region kern --inspect     # check the real field names first
python3 scripts/load_calgem.py --region kern               # query CalGEM's WellSTAR layer
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
