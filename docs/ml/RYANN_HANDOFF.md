# Geographic model handoff for Ryann

Completed 2026-10-24 in `/Users/emirtg/Desktop/dowser-cursor`, branch
`ml/cursor-improvements`. Original checkout and canonical selected-model pin
were left unchanged. This local package has not been sent, loaded or merged.
Master Plan sections 3, 5 and 6: detection boxes/confidence/year/crops,
per-tile WGS84 conversion, source provenance and backend delivery.

## Minimal Desktop delivery requested by Emir

`/Users/emirtg/Desktop/Dowser_Ryann.zip` contains exactly three root items:
`detections.csv`, `crops/` (3,116 PNGs), and `best.pt` (the reviewed Cursor
translate checkpoint, confidence .71). No README/metrics/manifests or other
metadata files are included. Size 64,963,152 bytes; archive SHA-256
`7e19116ea3485973e0d043eacbfe495dde78fec27e1924abdfa4dc3bb93d7006`.
All ZIP CRCs, CSV/weight byte identities and crop references were verified.
Receipt: `data/ml/handoffs/desktop_minimal_ryann_receipt.json`.

Send sanity output and the qualified Validation metrics as message text. The
request's “saves a crop image ... writes the CSV” describes the two outputs,
not an additional file; best.pt was explicitly included in Emir's final list.
Ryann should place the extracted CSV and crops directory in `pipeline/data/`;
CSV crop references remain relative to the receiving repository root. She may
store the weights separately. The previous detailed archive below is retained
as an auditable local reference; it is not necessary for this minimal delivery.

## Ready to send

Combined archive: `data/ml/handoffs/dowser_ryann_cursor_translate_v1.zip`,
61,033,363 bytes, SHA-256
`3985236d4f1822a8adf3be8cacedc80ed55ddfebcbe74e6f322c5daf13c0703e`.
Extract into the receiving repository root. Back up existing destination files.

- `pipeline/data/detections.csv`
- `pipeline/data/crops/` (3,116 PNGs)
- `pipeline/data/sanity_check.txt` and `.json`
- `pipeline/data/validation_metrics.json`, `export_receipt.json`,
  `calgem_reference.json`, `tiles.jsonl`, `detections.jsonl`, `SHA256SUMS`
- `ML_HANDOFF_README.md` with scope and receiving commands.

Standalone files: `pipeline/data/ryann_cursor_translate_v1/detections.csv`,
`crops.zip`, `sanity_check.txt`, and the metadata files. The standalone crops
ZIP extracts to `crops/`; place it beside the CSV under `pipeline/data/`.
CSV crop paths are relative to the receiving repository root.

## Actual model and coverage

Explicit pin: `pipeline/config/inference_cursor_translate.json`,
run `cursor_translate_mps`, confidence .71 / NMS .70 / max_det 1000 / native 1024.
Checkpoint SHA: `d417cf36430485eb534fd1197be6cf15b4cad11c967083654fc3388e5a226b2e`.
It uses the original Train mix, not the erroneous new Cursor label additions.

There are **3,116 raw model detections**, each with one evidence crop. Overlap
duplicates remain for Ryann's 20 m deduplication. Every row carries the actual
model confidence and `source=model`.

| Source edition | Dates | Raw detections |
| --- | --- | ---: |
| Oil Center 293661 | base 1954 / revised 1968 / imprint 1970 | 1,339 |
| Oildale 293664 | base 1954 / imprint 1956 | 577 |
| Oil Center 102321 | base 1992 / edit and imprint 1995 | 1,200 |

Inference covers all **87 Train/Val tiles** (72/15), frozen IDs, masked collars
and 819 px stride. **30 Test and 72 buffer tiles are excluded.** This is partial
regional coverage across three editions/two quadrangles, not three full sheets
or a regional well census. Training images are included for product integration;
the export is not an accuracy evaluation. Counts are not distinct/undocumented wells.

## Coordinate checks and actual sanity result

Every tile's source GeoTIFF SHA, CRS, offsets and affine were checked. Prepared
RGB pixels were reconstructed from the source and neatline mask and compared
exactly. Four-corner residual is at most `2.3283064365386963e-10` source pixels.
Native box centers use pixel edges, with no extra half pixel. Coordinates are
WGS84; matching distances use EPSG:3310.

CalGEM was downloaded with the inspected existing loader for buffered bbox
`[-119.131,35.370,-118.869,35.505]`: 28,072 rows, 28,060 usable locations,
12 uncertain excluded from sanity. All statuses, including plugged/canceled,
are retained. Local snapshot: `data/ml/ryann_calgem_v1/`. Reference JSONL SHA:
`7297ed5eafff35e937f3709c29b189c1e8db15f165657a676c5207aaf37dc767`.

Actual final message:

> Sanity check PLAUSIBLE: 97.6% within 100 m of a documented CalGEM well; median nearest distance 15.4 m. Proximity diagnostic only; map accuracy not independently verified.

No sanity WARNING was triggered. Dense-field proximity is not independent
geographic accuracy. External actual-map controls and 10+ reviewed CalGEM
matches remain pending. Coordinate-operation/grid notices are preserved in
the receipt: the available non-ballpark operation states 5 m operation accuracy,
but best-grid availability is false. This is not historical-map accuracy.

## Accuracy statement

Human Validation at .71 / match IoU .50: TP46 / FP4 / FN3,
precision .9200 / recall .9387755 / F1 .9292929. Positive instances are on four
overlapping Oildale 1954 strips. All four 1992 Val images are negative, so 1992
recall is unmeasured. Repeatedly tuned Val is not independent Test performance.
Recipe seeds 43 and 7 gave F1 .8113 and .3028; training stability is unproven.
The delivered checkpoint's native counts were independently reproduced:
[CODEX_REVIEW.md](CODEX_REVIEW.md).

## Attached scripts and reproduction

Both supplied files were fully read and retained unchanged in
`data/ml/ryann_sources_v1/`. Original hashes:

- detect_sheet.py: `3d0d4611f53981b237e77147c4ff2717415521226659f1d0c4d3cd6e67154cf4`
- labels_to_detections.py: `936680f0ef1d0336df68efc77462ecd456418522a0ccc09c612cbdca16ef600f`

Adapted implementations now use those names under `pipeline/`; the CLI differs.
The originals retiled collar/Test areas, used default .4 and SDK limits rather
than the pin, expected a different CSV manifest, left fallback confidence blank,
and silently skipped sanity when references were missing. The adaptations use
the frozen JSONL manifest and explicit pin, preserve native boxes/years, verify
source geometry, and report missing checks explicitly. They export model data
only; a human-ground-truth fallback command remains future work.

No dependencies were added. Keep the existing two environments separate:

```sh
pipeline/.venv/bin/python -m pipeline.detect_sheet \
  --config pipeline/config/inference_cursor_translate.json \
  --out data/ml/ryann_inference_cursor_translate_v1/predictions.json

.venv/bin/python -m pipeline.labels_to_detections \
  --predictions data/ml/ryann_inference_cursor_translate_v1/predictions.json \
  --out pipeline/data/ryann_cursor_translate_v1 \
  --wells data/ml/ryann_calgem_v1/calgem_wells.jsonl
```

Those names already exist: use new output names to repeat. Missing reference
data gives `SKIPPED`, never a fabricated pass. SciPy nearest neighbors use the
same EPSG:3310 / 100 m definition as Ryann's matcher, excluding uncertain rows.

## Checks and next action

61 ML tests pass, including source GeoTIFF-to-CSV/crop export, native box-center
convention, invalid geometry/scores, crop padding, Test exclusion and explicit
sanity states. The synthetic export fixture initially lacked the source file
needed for receipt hashing; adding that fixture file fixed the test. All actual
CSV IDs/scores/coordinates/crops and ZIP CRC/layout were checked. Thirty-two
random crops were visually inspected, not counted as accuracy evidence.
Receiver dedup/matching code was inspected for column compatibility; it was not
executed here because its Pandas/GeoPandas dependencies are not installed.

Send the archive and qualified Val metrics. Ryann starts at `dedup.py`, then
matching, enrichment, scoring, loading and evidence publication. No Convex
candidate load or external message was sent here. `detections.jsonl` has local
`cropPath` metadata and is not a direct Convex import. Preserve final Test and
complete independent coordinate controls before claiming geographic accuracy.
