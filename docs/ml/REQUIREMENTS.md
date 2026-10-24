# ML requirements and evidence

Authoritative baseline: [Master Plan](../master-plan/source.txt), sections 3–6.
It supersedes the original PRD. Legacy FR identifiers are cross-references only.

| Requirement | Owner / state | Evidence or remaining acceptance |
| --- | --- | --- |
| Kern, 1947–1992 editions; >=3 sheets and >=2 eras | Emir: acquired | Three editions in [region config](../../pipeline/config/region.json), native 1954/1992 eras |
| 1024 px tiles, about 20% overlap, own ID/year/transform | Emir: implemented | `pipeline.prepare_dataset`; 819 px stride, source hash, WKT, native offset |
| Corner reconstruction <=1 source pixel | Emir: numerically verified | Tests/summary; not absolute map-accuracy evidence |
| Test about 20%, >=30 tiles before training | Emir: partition implemented | Shared geography across years; crossing tiles quarantined; annotate protected tiles before evaluation |
| >=300 human-labeled symbols, lookalike negatives, multiple eras | Count/eras verified; quality pending | Export has 568 boxes on 5 Train images: 297 from 1954, 271 from 1992; 15 large boxes flagged, no reviewed empty negatives |
| Fine-tune pretrained YOLO, imgsz 1024 | Emir: pending | No training/weights; no replacement with published U-Net |
| Box, confidence, class, tile ID, year, crop | Emir: pending inference | Current contract documented; no fabricated detections |
| Pixel-to-WGS84 with native tile transform | Emir: unit checked | `pipeline.geo`, edge convention and rotated-affine checks |
| >=3 control points on actual maps | Emir: pending | Synthetic projection tests do not satisfy independent map-control acceptance |
| >=10 known CalGEM wells, median offset <50 m target | Emir + Ryann: pending | Needs reviewed symbols and reference matches |
| Precision/recall on untouched test; target >=0.60 | Emir: pending | Tune on separate validation; no quality claim |
| Model/manual-ground-truth fallback | Emir: pending export | Main now uses explicit ground_truth with numeric 1.0 and a hand-labeled UI tag; audit outputs remain label files, not candidate loads |
| Dedup 20 m across tiles and editions | Ryann | Master Plan supersedes original 15 m |
| Match 100 m, OSM homes/schools/water, scoring, load | Ryann | Existing backend loading API is not ML's task |
| Command Map and Field View | Kunjal | Ryann prepares overlay; ML supplies source/crops |
| Live upload, Droid, Claude vision | Could-have | Only after the core loop works |
| Resource costs | User constraint corrected | User withdrew the zero-cost ban on 2026-10-23; record actual usage/costs |

## Evaluation discipline

Freeze sources and geography before training. The same territory across years
and overlapping neighbors must not cross train/val/test. Buffer tiles are not
negatives or training samples. Splitting uses full tile envelopes conservatively.

At least 30 test tiles takes precedence when the fraction slightly exceeds 20%.
Report actual counts and per-era symbol counts after labeling. Preserve an
independent test by tuning on the additional validation partition instead of
the Master Plan's ambiguous reference to held-out threshold tuning.

Published/assistant predictions are not human labels. Never create an empty label
for an unreviewed tile. Human review covers the full tile, including negatives
and clipped symbols. See [annotation instructions](ANNOTATION.md).
