# Main branch review: 2026-10-23

Historical baseline below is `15f7c8f`, not current main. ML preparation now
includes `88c6522`: candidates/status/field-check/pairing functions were added,
sensor names changed, cropUrl/mapYear were added, and the loader moved to
`pipeline/`. Current contracts and scope are in [ML contract](ml/CONTRACT.md)
and [Master Plan](master-plan/source.txt). Old "not implemented" statements below
describe only the explicitly recorded historical snapshot.

This is a source snapshot, not a live deployment verification. Read the current
[ML status](ml/STATUS.md) for the next action and the
[contract](ml/CONTRACT.md) for ML integration decisions.

## Reviewed revision and coverage

- Repository: `kunjalp/Dowser`.
- Reviewed `origin/main`: `15f7c8f13896093935c7e3811e8b28ee10c97ccd`.
- Git tree: `03df5146cc89500a0ea6854cf4ed445a4163927a`.
- Coverage: all 97 tracked files, 310,751 bytes, 55 distinct Git blobs.
- The 41 files under `.agents/` and the corresponding 41 under `.claude/`
  have identical content hashes. Their unique content was read once, including
  all 33 skills, component references, agent metadata, and SVG source assets.
- `AGENTS.md` and `CLAUDE.md` in this main snapshot are also identical.
- The remaining 15 files were read in full, including both lockfiles.
- Both `git fetch origin` and the GitHub commits API confirmed the same main SHA.
- `origin/main` is an ancestor of the documentation branch. There were no
  incoming main commits to merge at review time.

Skills describe available contributor procedures; their presence does not mean
authentication, billing, AI agents, backup, or other features are implemented.

## Application and configuration files

| File | Actual role in reviewed main |
| --- | --- |
| [README.md](../README.md) | Backend setup, region TODO, sensor contract, CalGEM import commands, attribution TODOs |
| [AGENTS.md](../AGENTS.md), [CLAUDE.md](../CLAUDE.md) | Convex guidance entry points; main contains the managed Convex block only |
| [.env.example](../.env.example) | Local ingest-token placeholder and deployment-env instructions; no deployment identity |
| [.gitignore](../.gitignore) | Ignores generated Convex files, dependencies, local data/env, Python caches |
| [package.json](../package.json) | Convex dev/deploy and CalGEM load/test commands; no web or ML package |
| [package-lock.json](../package-lock.json) | Locked dependency tree |
| [skills-lock.json](../skills-lock.json) | Provenance and computed hashes for 33 installed Convex skills |
| [convex/schema.ts](../convex/schema.ts) | Six tables and their indexes |
| [convex/http.ts](../convex/http.ts) | Token-protected reading ingest and public health route |
| [convex/readings.ts](../convex/readings.ts) | Internal reading insert and public recent-readings query |
| [convex/tsconfig.json](../convex/tsconfig.json) | Strict TypeScript configuration for backend modules |
| [pipeline/load_calgem.py](../pipeline/load_calgem.py) | ArcGIS/CSV normalization and local JSONL/GeoJSON/log export |
| [scripts/post_reading.sh](../scripts/post_reading.sh) | Live HTTP smoke script; posts replay data and checks a bad token |
| [pipeline/test_load_calgem.py](../pipeline/test_load_calgem.py) | Five offline normalization/CSV tests |

Links resolve against the current branch. The immutable SHA above identifies the
exact source reviewed, including files later extended by the documentation PR.

## Data model and relationships

The six tables are `tiles`, `detections`, `documentedWells`, `candidates`,
`readings`, and `briefs`. Their intended graph is:

```text
tiles.tileId <- detections.tileId
detections.detectionId <- candidates.detectionId
candidates.candidateId <- readings.wellId (optional), briefs.candidateId
documentedWells: separate reference dataset for future spatial matching
```

These are application-level string identifiers, not `v.id(...)` foreign keys.
Indexes support lookups but do not by themselves enforce unique application IDs
or referential integrity. No writers for tiles, detections, candidates, or briefs
exist in this main snapshot. `agentRuns` and `agentSteps` tables are also absent.

Tiles carry rasterio-order affine coefficients and their own CRS. Detections
require `{x, y, w, h}`, `className`, numeric `confidence`, WGS84 `lat`/`lon`, and
explicit `model`/`ground_truth` provenance. See the contract for open conventions.

## Public and internal function surface

| Surface | Visibility | Actual behavior |
| --- | --- | --- |
| `POST /ingest/reading` | HTTP, shared `X-Dowser-Token` required | Checks configured `INGEST_TOKEN`, parses/validates fields, calls the internal insert, returns 201 with `readingId` and `receivedAt` |
| `GET /health` | Public HTTP | Returns `ok` and server time |
| `readings:ingest` | Internal mutation | Inserts one reading; returns identifiers; does not update candidates |
| `readings:recent` | Public query | Newest-first readings, optional well filter; defaults to 100 and caps requested limit at 500 |

The app has no user-auth foundation, user ownership model, or user accounts in
this snapshot. Sensor ingest uses one shared deployment token, not a device
registry. The public reading query performs no identity check. This describes
the source boundary; it is not a separate authorization audit.

No Convex components, crons, Claude actions, Droid runs, Apify integration, or
external API calls from backend actions are implemented. The CalGEM Python
script makes external requests only when its online source is selected.

## Existing flows

Sensor: HTTP request -> token/field validation -> timestamp normalization ->
`internal.readings.ingest` -> `readings` table -> `readings:recent` query.
`ts` falls back to server time when absent or outside a 24-hour window;
`isReplay` defaults to false. No map client is present to subscribe yet.

Records: CalGEM ArcGIS envelope query or local CSV -> field normalization ->
coordinate-quality flags -> API deduplication -> JSONL + usable-coordinate
GeoJSON + bad-row log -> manual Convex import, if a contributor runs it.
The review did not execute that deployment import or the live sensor script.

## Integration gaps and assumptions

| Area | What still needs implementation or agreement |
| --- | --- |
| ML transport | No tile upload/detection ingestion endpoint or mutation exists; schema compatibility alone is not an executable API |
| Fallback | Required numeric confidence has no defined annotation-score semantics; null is rejected |
| Evidence | Crop/run provenance and multi-tile evidence are absent from stored detection fields |
| Triage | No spatial match, candidate creation, proximity, priority scoring, or dedup implementation |
| Sensor ranking | Three-readings/30-second confirmation and candidate rank changes are TODO comments, not runtime behavior |
| UI | No Next.js/MapLibre client, historical overlay, satellite toggle, or evidence panel |
| Briefs/agents | Tables alone do not generate Claude briefs; Droid/Apify are unimplemented |
| Region | Kern/LA boxes in the loader are approximate options, not a final team selection |
| CalGEM source | Column aliases and default 8-digit API padding are explicitly unverified assumptions in the loader |
| Regional counts | CSV rows without usable coordinates are retained as uncertain and cannot be filtered to a region by location; distinguish them from region-located wells |
| Location quality | Loader flags uncertain coordinates and omits them from GeoJSON; future matching must explicitly filter `locationQuality == good` |
| Latency | `receivedAt` measures server receipt; server-to-render timing alone does not prove the full device-to-map target |

## Toolchain and verification limits

Locked versions: Convex 1.48.0, TypeScript 5.9.3, `@types/node` 24.19.2,
esbuild 0.27.0, prettier 3.9.10, ws 8.21.0, undici-types 7.24.6. The lockfile's
Convex package declares Node >=20. Use `npm ci` for lockfile-based installation.
Use Python 3.10+ for the loader's modern annotations; the online loader imports `requests`
but its offline tests use the standard library. No ML dependencies are selected.

Verified locally: all five CalGEM tests passed; `bash -n` accepted the sensor
smoke script; documentation links and whitespace were checked. CalGEM tests use
synthetic data and do not validate the current live API mapping.

Generated `convex/_generated/` files, including the referenced AI guidelines,
are absent/ignored. No deployment was inspected, provisioned, or modified; no
TypeScript build, HTTP live test, real dataset ingest, or ML evaluation is claimed.

To extend the backend, use its `convex-expert` guidance after generated guidelines
are available; a separate audit belongs to `convex-reviewer`/`convex-authz`.

## Repeating synchronization

Follow [the contribution guide](../CONTRIBUTING.md#synchronizing-with-main).
Treat this review as evidence for the recorded SHA, not a claim that future main
commits are already reviewed. Re-read changed files and their consumers before
updating the snapshot; preserve explicit open decisions until jointly resolved.
