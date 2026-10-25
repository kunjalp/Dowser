# Hackathon log

- **Project:** Dowser
- **Event:** Cal Hacks 13.0
- **What it does:** Finds oil and gas well symbols on historical USGS maps that have no California state well record nearby, ranks them by closeness to homes, schools and water, and lets field crews check them with a handheld that streams readings to a live map.
- **Live app:** https://dowser-ten.vercel.app
- **Repo:** https://github.com/kunjalp/Dowser
- **Frontend:** Vercel
- **Convex deployment:** https://earnest-otter-112.convex.cloud
- **Components:** none
- **Convex features:** schema, indexes, queries, mutations, actions, HTTP actions, file storage, realtime useQuery
- **Auth:** none
- **AI models:** claude-sonnet-5-5
- **Started:** 2026-10-24T00:08:41Z
- **Last updated:** 2026-10-25T17:06:48Z

## How we use Convex

- **Handheld readings:** the ESP32 posts to an HTTP action at `/ingest/reading`, which stores each reading through an internal mutation. `convex/http.ts`, `convex/readings.ts`
- **Auto-confirm:** in the same mutation, 8 readings of 1000 or more within 10 s mark the paired well `confirmed_leaking`, using the `by_candidate_receivedAt` index. `convex/readings.ts`, `convex/schema.ts`
- **Live screens:** the Command Map and Field View read candidates, readings and pairings with `useQuery`, so both update without a refresh when a reading or field decision lands. `app/src/app/page.tsx`, `app/src/app/field/page.tsx`
- **Pairing and decisions:** mutations pair a handheld to one well and record crew decisions (leaking, not leaking, no well, mislocated). `convex/pairing.ts`, `convex/candidates.ts`
- **Field photos:** Field View uploads photos through a file storage upload URL. `convex/fieldChecks.ts`
- **Briefs:** an internal action calls the Anthropic API and saves each brief with an internal mutation. `convex/briefs.ts`, `convex/briefPrompt.ts`

## Log

All times UTC.

- 10-24 `15f7c8f` Convex schema, ingest endpoint, readings (`convex/schema.ts`, `http.ts`, `readings.ts`)
- 10-24 `88c6522` Candidates, pairing, field checks (`convex/candidates.ts`, `pairing.ts`, `fieldChecks.ts`)
- 10-24 `49df1f4` Command Map app, CalGEM loader (`app/`)
- 10-24 `f7e5eeb` Field View, auto-confirm, priority sliders (`app/src/app/field/page.tsx`, `convex/readings.ts`)
- 10-24 `5a7670f` Well matching and enrichment (`pipeline/match_wells.py`, `enrich.py`)
- 10-24 `8317506` Scoring (`pipeline/score.py`)
- 10-24 `2a2947e` Candidate loader (`pipeline/load_candidates.py`)
- 10-24 `a6a9162` Brief generator with grounding checks (`convex/briefs.ts`, `briefPrompt.ts`, `tests/backend.test.ts`)
- 10-24 `588249c` Documented wells layer, activity timeline (`app/src/components/MapView.tsx`)
- 10-24 `2edeed6` Impact numbers, replay fallback (`pipeline/impact.py`, `replay.py`)
- 10-24 `8e98e7a` iOS app with Capacitor and Codemagic (`app/capacitor.config.ts`, `codemagic.yaml`)
- 10-24 `01fbe4b` Field View: distance sort, live gauge, undo (`app/src/app/field/page.tsx`)
- 10-24 `2e497c9` Evidence crops for real candidates (`app/public/evidence/`)
- 10-24 `9764f5e` Field View evidence, Command Map filters (`app/src/components/MapFilters.tsx`)
- 10-24 `47399c9` ESP32 firmware and serial bridge (`firmware/`)
- 10-24 `30d0ae3` Auto-confirm: 8 readings in 10 s (`convex/readings.ts`)
- 10-24 `2f88680` Idle-wells list (`convex/candidates.ts`, `convex/schema.ts`, `app/src/app/page.tsx`)
- 10-25 `ffe3a9b` Review status: 2 verified, 62 rejected (`app/src/components/Sidebar.tsx`)
- 10-25 `a81bde3` Field View: two lists (`app/src/app/field/page.tsx`)
- 10-25 `fcf76ed` README rewrite (`README.md`)
- 10-25 `8519fe9` Backend test: threshold 1000, 8 in 10 s (`tests/backend.test.ts`)
- 10-25 `705c96a` MIT license (`LICENSE`)
