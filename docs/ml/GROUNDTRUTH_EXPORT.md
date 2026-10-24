# Human-labeled detections handoff

Exported 2026-10-24 from the laptop's human labels, independently of model
predictions. Source label/image/manifest files stayed byte-for-byte unchanged.
Master Plan section 6: explicit ground-truth fallback with traceable georeferencing.

## Download and unpack

[GitHub artifact release](https://github.com/kunjalp/Dowser/releases/tag/groundtruth-human-v1-2026-10-24):

- `dowser_groundtruth.zip`: CSV plus 617 original-derived evidence crops.
- `dowser_groundtruth_report.txt`: commands, checks, environment changes,
  coordinate ranges, spot checks and source identities from the export run.

Extract the ZIP at the teammate repository root. Its 618 files are
`pipeline/data/detections_groundtruth.csv` and
`pipeline/data/gt_crops/*.png`. This preserves the crop paths in the CSV.
No model weights, original label TXT files or Test labels are in the archive.

ZIP: 25,507,011 bytes, SHA-256
`c9bf375dbf59346cd8ce43c053385169cf9a1335d369ae20a5cc28e03055bc7f`.
CSV SHA-256:
`293dbb762729c2a21415b53e1531337328d4b12c5091d78447ce31c3dca50f80`.

## Contents and validation

617 box instances = 568 human Train + 49 human Val; zero skipped boxes.
11 explicitly empty Val label files correctly produce no rows.

| Sheet | 1954 | 1992 | Total |
| --- | ---: | ---: | ---: |
| Oil Center | 297 | 271 | 568 |
| Oildale | 49 | 0 | 49 |
| Total | 346 | 271 | 617 |

Latitude: 35.3751438..35.4398897. Longitude: -119.0906046..-118.9035192.
Zero rows outside the requested Kern range (34.79..35.80, -120.19..-117.63).
This is a coarse sanity check, not independent absolute positional verification.
All rows have `source=ground_truth`, `confidence=1.0`, `labelSource=human`.
The 1.0 value is the agreed manual-label convention, not detector accuracy.

All 617 crops were checked for existence/readability/160x160 dimensions.
One output crop from each map edition was visually opened; the target hollow
circle is at/near the crop centre. ZIP CRC and every member's source hash match.
SHA-256 snapshots confirmed all 140 protected input files unchanged.

## Reproduce on the original ML laptop

Human labels are local and ignored by Git:
`data/ml/reviewed_v2/labels/train/` and
`data/ml/reviewed_validation_v1/labels/val/`. Tile images are recursively under
`data/ml/kern_1024_v2/images/`. Use the frozen v2 manifest:
SHA `ebb2f8a4fdfefabf7dcdd9f3e4339f4c5912d4b2b2ecbb448b3f6da06c0ef572`.
Preserve existing outputs before rerunning: the current converter overwrites its
output CSV/crops. Do not modify or redistribute source split assignments.

```sh
.venv/bin/python -m pytest -q pipeline/test_annotations_to_detections.py
.venv/bin/python pipeline/annotations_to_detections.py \
  --manifest data/ml/kern_1024_v2/manifest.jsonl \
  --labels data/ml/reviewed_v2/labels \
  --labels data/ml/reviewed_validation_v1/labels \
  --images data/ml/kern_1024_v2/images \
  --crops pipeline/data/gt_crops
```

Four tests passed. Root Python 3.9.6 already had the geospatial/image libraries;
pytest 8.4.2 and missing dependencies were installed as authorized. A three-line
direct-script import-path fix was shown before application; conversion math and
labels were not changed. The export itself performed no commit/push. Subsequent
GitHub publication was separately requested by Emir.

The output is not deduplicated and is not a list of verified undocumented wells.
Ryann's later dedup/matching determines candidates. No database reload, Vercel
deployment or model promotion is part of this artifact upload.
