# Team update compared with implementation — 2026-10-24

Historical snapshot before the first training run. Subsequent Val import,
training, real metrics and preview are recorded in [STATUS.md](STATUS.md) and
[EXPERIMENTS.md](EXPERIMENTS.md); the zero-epoch statements below describe that
earlier review and must not override current status.

Scope: review of Emir's pasted team update against Master Plan sections 3, 5,
6, 8 and 12, current code/artifacts, and draft PR #3. The update is coordination
context; the original Master Plan remains preserved verbatim.

## Findings

| Update claim or instruction | Verified situation and action |
| --- | --- |
| Emir is on model version 11; send v11 validation metrics | YOLO11n is the architecture name. Zero detector epochs/optimizer steps have run; there are no measured precision/recall or trained best.pt to send. The GPU probe is compatibility only. |
| Pixel boxes need real coordinates | Correct; explicitly required by Master Plan sections 5–6. `pipeline.prepare_dataset` preserves native per-tile CRS/affine, source ID/hash/year and offsets. `pipeline.geo.box_center_to_wgs84` already performs the conversion. |
| The detector must run directly on GeoTIFF at the end | Direct GeoTIFF inference is one valid workflow. Native PNG tiles are also valid when joined to their retained manifest transform/CRS; all five human-labeled PNGs have this provenance. A filename/image alone is insufficient. |
| Download maps from Taft/Fellows/McKittrick/Oildale | No new download/region selection is necessary for the current MVP. Three pinned GeoTIFF editions already exist: Oil Center 1954, Oildale 1954, Oil Center 1992, across two quadrangles/two eras. Do not describe these as three distinct quadrangles. |
| Add detect_sheet.py and labels_to_detections.py | Only names/descriptions were supplied in the chat. Neither script exists in the checkout or main through 2b4678a; implementation, dependencies, CSV compatibility and claimed checks cannot yet be audited. Obtain the actual files before integrating/running them. |
| pip install an unpinned dependency bundle | Preserve the two existing environments and pinned requirements. Review new scripts first and add necessary dependencies deliberately; the training environment does not currently include the full geospatial stack. |
| Use runs/detect/train11/weights/best.pt | That is an example from another workspace, not a local artifact. Our future runner writes under data/ml/runs/<name>/training/weights/; record the actual successful checkpoint and checksum. |
| Fake-map test landed on real Taft wells | This can demonstrate arithmetic in that fixture; it does not validate native historical GeoTIFF georeferencing, datum accuracy or actual symbol locations. Real-map controls and 10+ verified documented-well spot checks remain pending. |
| Confidence starts around 0.4 and may be adjusted | Consistent with the Master Plan starting value. Select/report thresholds on independent Validation, not final Test or subjective changes to get the desired candidate count. |
| Send CSV/crops and validation P/R for pitch | Planned ML handoff is compatible in principle with Ryann's pipeline; exact columns/paths/provenance still need script review. State maps/eras/counts, threshold and metric protocol; Val tuning scores are not untouched Test performance. |
| Everything downstream is tested | This is the teammate's statement. Current ML checks do not independently establish end-to-end detection loading, published crop URLs, record matching or deployed UI behavior. |

## Integration checks for the incoming scripts

Before execution, reconcile tiling/neatline masks, native 1024 px resolution,
20% overlap, ROI and stable IDs with existing preparation. Preserve each sheet's
full native CRS (including NAD27 custom projection), transform order, year and
pixel offsets; undo any inference resizing/letterboxing before conversion.
Preserve max_det suitable for dense tiles and the selected device/config.

Confirm explicit model confidence/source and downstream CSV columns. Ground-truth
fallback must retain source=ground_truth and the existing numeric-1.0/UI convention,
not masquerade as model probability. Crops must be published before becoming URLs.
Nearest-record checks on all detections are not a replacement for 10+ manually
verified documented-well offsets: undocumented candidates legitimately lack matches.
Run one selected sheet after training; full-sheet fitting/tuning must not consume
protected Test labels. Keep final metric evaluation independent.

## PR and immediate next action

PR #3 contains completed preparation, georeferencing primitives, split/audit
guards, training setup and documentation. These can be integrated without waiting
for final detector accuracy. Recommend reviewing/merging that bounded increment,
then making inference and evaluation separate PRs. This does not mark the whole
ML milestone complete. Team review should include shared root instructions/README
and Ryann's detection interface, since PR #3 is larger than only Python changes.

At review: 33 local ML tests passed; GitHub showed successful Vercel contexts,
draft status, no submitted reviews and a clean merge computation for its recorded
head/base. Vercel success is not ML CI. Newer main 2b4678a only changes a mobile
publishing flag; inspected and merged into the ML branch via bc3c0ae. No PR was
merged into main and no mobile build/signing/publishing was invoked by ML.

Emir's immediate work remains independent full-image review of all **15 Val
images** in the new ZIP, single class well_symbol. Draw boxes only for real
targets; Mark Null only for verified empty images; leave uncertain work for review.
This is a checking set, not 15 additional mandatory dense Train images. Then
audit/export, run five diagnostic epochs and inspect predictions before a baseline.
No redraw of the five existing Train images or new map downloads is requested.

Evidence: [Master Plan](../master-plan/source.txt), [status](STATUS.md),
[contract](CONTRACT.md), [training plan](TRAINING_PLAN.md),
[region config](../../pipeline/config/region.json),
[geo conversion](../../pipeline/geo.py), [preparation](../../pipeline/prepare_dataset.py),
[PR #3](https://github.com/kunjalp/Dowser/pull/3).
