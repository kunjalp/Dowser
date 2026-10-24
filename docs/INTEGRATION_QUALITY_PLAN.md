# Integration review and measurable quality plan

Review date: 2026-10-24, America/Los_Angeles. Planning and read-only source/data
inspection; no deployment, model promotion, dataset reload or merge was made.
Original `/Users/emirtg/Desktop/dowser` was not modified. Claude's active MPS
training/product-export process was left running.

## Revisions and review scope

- GitHub main: `00f4deea97deefc38d90d0c7fec2a00c3ae49adb` (PR #13, rounded UI).
- ML: `e939785aea560c4380157e0eb74b641f5c1ad0ce`, `ml/cursor-improvements`.
- Common ancestor: `2b4678a2b458b5a1997fe462ddf29e53b820e0cb`.
- Main has 25 exclusive commits; ML has 46. Main changed 80 paths; ML 135.
  No paths changed on both sides since the common ancestor. An isolated bare
  repository's `git merge-tree --write-tree main ml-review` succeeded, tree
  `893dfe60fdc1a54350b0f37580e35f872766995e`. This establishes a clean source
  merge, not working integration or data quality. Shared worktree refs were not
  fetched/changed. Recheck main before integration; it moved during this audit.
- Source snapshot first downloaded at `19285a0`; the only subsequent main
  change through `00f4dee` was `app/src/app/ux.css`, also inspected.
- Existing draft PR #3 targets main from `ml/tile-georeferencing` at `4bc0bbe`.
  It is not the current Claude branch/head; merging it does not deliver the
  latest ML work. Remote refs may lag local ML commits/ignored artifacts.

Read Master Plan, contributor/agent instructions, current ML status/experiments,
repair/evaluation code and artifacts; main candidates/schema/scoring, readings,
pairing/HTTP, brief generation, dedup/match/enrich/score/load/overlay/export code;
Command Map, Field View, detail/map/sidebar/filter/types and backend tests.
Used the `convex-reviewer` skill for backend inspection. This is not a live-site,
database, firmware or physical-sensor verification. No firmware source was found
in the main snapshot. Node dependencies were absent in this checkout; backend
Vitest, frontend build and browser acceptance were not run in this review.

## Verified current ML state

- New annotation JSON contains 20 Train frames, 156 boxes on six frames and 14
  empty decisions. Provenance is assistant review, not human ground truth.
  Counts/policy were checked; this audit did not independently approve every
  symbol or empty decision. Check blue/black marks, dotted circles, faint and
  clipped targets and box geometry in a second semantic review before reuse.
- `kern_repair_v2_mixed_s42` pin: .67, weights SHA
  `58cdff9f484ccd87c20f134cfc7c2ce780d3967acedbbb9141c4669ecfdc1697`.
  Saved Val sweep gives TP43/FP0/FN6, P1/R.87755/F1.93478. Its product regression
  gives 3,414 raw / 1,722 groups / 1,695 CalGEM-matched / 27 candidates,
  including 17 groups overlapping known false feedback. It is not ready for
  an automatic 95%-precision candidate-list claim.
- The reference is 46/4/3 at .71; product 1,593 matched / 64 unmatched / 62
  known false. More CalGEM-matched groups is a diagnostic proxy, not measured
  detector recall or proof of real wells.
- E4 is in progress. At the inspection point eight of nine training run records
  were completed and the ninth was training; product regressions were still
  being produced. E4 mixed Val F1 for seeds 42/43/7: .93478/.90722/.90526.
  Improved full-schedule seed results support a stopping-effect contribution;
  they do not prove all instability has been solved. Do not select on partial
  E4 outputs or on repeated Test observations.
- Coverage-only final-Test command reproduced 27/30 human imports, 725 boxes,
  three explicit empty images, no duplicate conflicts. Missing IDs:
  `usgs_293661_x02149_y01182`, `usgs_293661_x04606_y00363`,
  `usgs_293664_x04595_y00361`. No Test inference was run. Audits explicitly
  retain `structurally_valid_semantic_review_required`.
- `.venv/bin/python -m unittest discover -s pipeline/tests -q`: **73 passed**.
  These are software checks, not 73 independently evaluated maps or model Test
  performance. Existing reference pins and delivery archives are unchanged.

## Concrete integration findings

| Priority | Finding in reviewed main | Consequence / next change |
| --- | --- | --- |
| P0 | `convex/schema.ts` and candidate APIs have field statuses but no separate symbol-review decision; pipeline has no persisted false-detection exclusion stage | Introduce a review ledger and publishing eligibility independent of field findings. `false_detection` must not be represented as `no_well`. |
| P0 | `app/public/evidence/` contains the original 64 crops; 62 filenames match Ryann's confirmed-false IDs | Old evidence is present in source. Live candidate contents were not inspected, so visibility is unknown. Reconcile active database/list with the review ledger before claiming it is clean; retain raw evidence/history. |
| P0 | `cand-<detectionId>` includes the model-run prefix and highest-confidence dedup representative | A new model/representative changes identity. Existing upsert preserves field decisions only for identical IDs; absent old rows are not retired. Add stable identities, explicit crosswalk/review reconciliation and versioned active releases. |
| P0 | Loader accepts missing evidence with a warning and drops missing images; HTTP evidence URLs are retained without checking; backend preserves an old brief if incoming brief is missing | Publishing can leave empty/broken evidence or a stale narrative after facts change. Gate release on complete assets and input fingerprints; regenerate/invalidate changed briefs. |
| P0 | Sidebar and map use active `rankScore`; DetailPanel displays stored `score` | Moving priority sliders can show different scores for the same selected point. Show one active ranking score consistently and label saved/default score only if needed. |
| P0 | Command Map's global simulated banner is driven by `fake-` IDs; replay can attach to real IDs, and replay readings participate in auto-confirm | Demo confirmation can resemble a real finding. Carry explicit replay/demo provenance through the active session, status event, both screens and score; exercise the real-ID replay path. |
| P1 | Historical layer code exists, but `app/public/historical/manifest.json` and overlay assets are absent from tracked main | Generate and publish the three pinned editions, then verify overlay registration/attribution on the deployed artifact. Absence from Git does not establish live-site absence. |
| P1 | Map click handler selects candidates; documented-well layers are separate static GeoJSON | Define a documented-well inspection path, its own source/status details and the relationship to a nearby candidate. Do not label a documented point as a model discovery. |
| P1 | Ranked query takes first 2,000 rows before sorting/filtering, and client requests 1,000 | Larger releases can silently omit relevant rows/high scores. Bound release scope explicitly or implement indexed retrieval/pagination with totals. |
| P1 | Python regression and actual backend duplicate spatial rules/constants | Golden integration fixtures must prove identical memberships, centres, 20 m dedup and 100 m matching decisions. Keep a shared versioned rules manifest. |

Backend scope note: status/pairing mutations are public without identity checks,
as expected for the Master Plan's account-free demo. Any public-production claim
needs controlled write access so arbitrary clients cannot change findings.
Do not add an accounts/auth product to this sprint; coordinate the intended demo
access boundary with Ryann. Readings ingest already checks its token.

## What the 95% target means

Proposed primary target: **at least 95% of published candidate points are
correct historical oil/gas-well symbols**, measured on a separately reviewed
candidate population. A correct symbol does not prove a surviving physical well,
an undocumented well, or a leak. Model confidence and priority score are not
probabilities of any of those events.

Separate acceptance gates:

| Layer | Gate and measurement |
| --- | --- |
| Automatic detector | Frozen independent Test P target >=.95; report recall/F1 and per-era counts. Proposed recall guard >=.90 is stricter than the Master Plan's .60 goal and must be reported as an extra product target. Do not claim it is already met. |
| Published candidate set | At least .95 glyph precision on an independent audit; for the small demo release review every point and retain all rejects/uncertainties. All published points pass documented review and technical checks. Review-assisted quality and automatic quality get separate reports. |
| Point/card integrity | 100% of active cards resolve to their own candidate, version, coordinates, source sheet/year, actual evidence, matching facts, score and review record; zero known broken links, contradictory scores or invented facts. |
| Coordinates | Per-tile numeric reconstruction <=1 source pixel; >=3 actual-map control points; >=10 manually identified CalGEM correspondences, median <50 m per Master Plan. Also report per-sheet residuals/p95 and investigate outliers/boundary cases. Nearest-well proximity alone is not correspondence truth. |
| Interactions | Every active candidate clicked on desktop/mobile; filters/selection/re-ranking stable; 3/3 full-loop rehearsals succeed; ingest <2 s and map update <5 s, with measured timestamps. |

Publish denominators, coverage and uncertainty. With only 27 candidates, two
false points already give 25/27=.9259, so an audited demo set must have at most
one error to achieve a .95 point estimate. This does not establish future-map
accuracy or a tight statistical lower bound. Report confidence intervals with
tile/geographic clustering; overlapping boxes are not independent observations.
Small handpicked sets cannot establish general 95% model performance.

## Ordered implementation plan

### 1. Fix integration inputs and preserve work

Owner: Emir/ML agent, coordinated with Kunjal/Ryann. Complete the existing E4
batch and product reports; do not start another unbounded sweep. Record all
seeds under the predeclared rule, and distinguish qualifying for a comparison
from passing the new product publishing gate. Preserve all old pins/archives.

Create an isolated integration branch from freshly checked main, e.g.
`integration/data-quality`, and integrate the reviewed ML code there. Do not
switch branches in Claude's active checkout or merge draft #3 expecting it to
include the current head. Preserve main's UI, haptics and sensor changes.
Re-run the source merge check and relevant ML/backend checks on the combination.

Output: pinned source revisions, reviewed diff, artifact manifest and an
integration checklist. No production data switch is implied by a code merge.

### 2. Establish the publishing gate and review ledger

Owner: Emir + Ryann, with Kunjal consuming the agreed fields. First reconcile
the 62 confirmed errors against current groups/IDs, including representative
changes. Review every proposed demo candidate using the crop plus the native
map context, legend, edition and colour; retain uncertain cases for review.
The other two old candidates are not verified positives merely because they
were not in the reject CSV. The new model's 27 candidates need fresh review.

Proposed review states: `pending`, `accepted`, `false_detection`, `uncertain`,
separate from existing candidate/queued/field finding statuses. Record reviewer
type/name, time, reason, evidence hash and affected detections/cluster version.
Human acceptance means the historical target symbol was checked. A classifier
output cannot silently become human acceptance.

Raw detections and rejects remain available in an audit view/export; only
eligible reviewed points enter the default trusted candidate layer. Display
total detected/reviewed/accepted/rejected/uncertain counts and covered region.
If nothing qualifies, show an honest empty candidate set. The already allowed
ground-truth fallback can use checked Train/Val annotations with
`source=ground_truth`; it must not become reported automatic performance or a
reason to consume Test labels for training.

Output: a fully reviewed small release and its audit ledger before spending
another training cycle. This addresses every displayed point immediately.

### 3. Improve the automatic detector against remaining error types

Owner: Emir. Independently recheck the six positive and fourteen empty assistant
frames; inspect faint/adjacent/clipped symbols and consistent box geometry.
Padding calibrated on Train is acceptable if it encloses the symbol; forcing
every box to 18x18 regardless of the actual ink is not a completeness check.

Add balanced complete Train examples of actual wells beside blue water wells,
dotted landmarks, buildings, diamonds and text. Use all frozen Train provenance;
never mine Val or Test for new supervision. Keep negative sampling/loss weighting
controlled so extra background does not erase recall. Evaluate one recorded
data/recipe change at a time with the same seeds and matched compute where
possible, preserving failed runs.

The current Val has no positive 1992 targets. Prepare a separately versioned
development evaluation set with era/map/error coverage from disjoint geography,
excluding protected Test/Val footprints and overlapping editions. Keep the old
Val for comparison; do not silently relabel it or move Test into development.
Test remains blind. If considering a context classifier/Claude-vision second
pass, follow the Master Plan's could-have gate: prove the core live loop first,
train/select without Test and freeze the complete pipeline before evaluation.
Current final-Test evaluator explicitly does not support verifier protocols.

Output: model/config/data hashes, raw and post-match previews, real seed spread,
TP/FP/FN, per-era coverage and candidate-type errors. CalGEM group counts and
removal of feedback cases remain regression diagnostics, not new accuracy.

### 4. Make the backend release reproducible

Owner: Ryann, ML supplies artifacts. Use a versioned release manifest binding
model/config/threshold, geographic coverage, input CSV/crops, review ledger,
CalGEM/OSM snapshots, source sheets, scoring rules and brief inputs. Validate
every candidate before publishing: finite coordinates within coverage, native
box/crop alignment, source/year, matching radius, dedup members and live assets.
Review ambiguous nearby-well matches and chained clusters that can bridge
distinct symbols; keep the existing rule version until a justified change.

Introduce stable candidate identity and explicit old/new detection crosswalk.
Do not copy field findings to a different nearby object automatically. Retire
superseded rows from the active release without deleting readings, decisions or
evidence; preserve review decisions across reruns only with justified linkage.
Build a dry-run diff, publish assets first, validate all URLs/hashes, then switch
one active release atomically with rollback. Repeated load must be idempotent.
Recompute/invalidate briefs whenever their facts change; unsupported distances
remain unknown, not zero or guessed values. Python/TS score results must agree.

Output: golden pipeline fixtures, import diff, release ledger, rollback and
re-run tests. Account/schema/interface changes need the consuming owners' review.

### 5. Make every UI point traceable

Owner: Kunjal, with Ryann's query/contract changes. Default to the accepted
active release, label model/hand-label/review provenance, and provide a separate
pending/rejected audit view. Keep documented CalGEM points distinct and inspectable.
Selected point, list, mobile page and sensor pairing must resolve the same
stable ID. Show the same active score throughout when sliders change; a score
of .95 must not be presented as a 95% chance of a real well/leak.

Each card must show its own evidence and context, source years/map IDs,
coordinates with uncertainty, nearest record/distance, reviewed state and
supported brief. Publish historical overlays for the pinned sheets and check
alignment against the actual points. Unknown/failed assets must be explicit;
the publishing gate prevents them in the accepted release. Preserve source
attribution. Query/list totals and map coverage must not silently truncate.

Output: automatic click-through of all accepted points, screenshot/error report,
no broken evidence URLs or mismatched cards, mobile and desktop checked on the
actual demo devices/network. A static map rendering alone is not acceptance.

### 6. Finish independent evaluation and the live loop

Owner: Emir (Test), Ryann/Kunjal/Murad (integration). Obtain the three missing
human Test tiles. Independently review annotation completeness without model
predictions; preserve original imports and document corrections. The auditor
only establishes structure. Before inference, validate actual image/label/audit
consistency and freeze chosen weights, all preprocessing/postprocessing, cutoffs
and protocol in a new file. Preserve the old protocol unchanged.

Run the complete 30-tile Test once under that protocol, reporting P/R/F1,
per-era/source counts, errors, inference time and uncertainty. No threshold
sweeps or selecting a winner using Test. If results guide a later repair,
preserve that failure and require a fresh independent holdout for a new claim.
A manual review-assisted candidate release does not change detector Test metrics.
Full-sheet production inference that includes protected Test footprints waits
until this evaluation is frozen/performed.

Test the complete live/replay loop in an isolated demo dataset: device pairing,
candidate switch, GPS denied, bad clock, reconnect, duplicate readings, replay
on a real candidate ID, and three hot readings. Keep simulation provenance
visible after automatic status changes; do not mix it into real field findings.
Confirm real ADC/relative units and the configured 1200 threshold with Murad;
no calibrated methane/ppm claim. Measure ingest/UI latency and preserve event
logs. Verify three rehearsals including a second window, then record backup video.

## Small PR sequence and exit decisions

1. ML tools/evaluation + main compatibility, without changing active data/pins.
2. Review ledger, stable identities, release loader and backend contract
   (Ryann review); shared frontend types updated with consumers.
3. Frontend evidence/review/score/replay consistency and end-to-end tests
   (Kunjal review).
4. Reviewed data/model release with manifest, independent metrics, actual
   geographic checks and rehearsal evidence; publish only when gates pass.

Code can be integrated before a model meets the 95% goal. Model promotion and
production dataset replacement are separate decisions with concrete evidence.
Existing public field mutations and the missing firmware/live environment must
not be represented as production-certified merely because source tests pass.
Timebox work to the hackathon's core loop and feature freeze. A truthful reviewed
small region can ship while automatic performance remains below target; a
guarantee for arbitrary maps or physical wells cannot be manufactured by tuning.

Immediate next action: finish E4/product results, perform the accepted-point
review and define the ledger/release contract with Ryann/Kunjal; in parallel
Emir/teammate supply the three missing human Test annotations. Do not deploy the
27 raw candidates as a trusted list or start another unconstrained training sweep.
