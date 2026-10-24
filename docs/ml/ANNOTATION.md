# Labeling handoff: Kern symbol detector

Owner: Emir. Labeling helpers: Ryann and Kunjal, per Master Plan. Scripts do not
trigger paid labeling jobs or upload anything externally.

## Prepare locally

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r pipeline/requirements.txt
.venv/bin/python -m pipeline.download_sources
.venv/bin/python -m pipeline.prepare_dataset
.venv/bin/python -m unittest discover -s pipeline/tests -v
```

Preparation refuses to overwrite output. For a deliberate rerun use a new
`--output data/ml/kern_1024_v2` and preserve prior manifests. Downloads use
public USGS/PROJ URLs; tiling is offline.

Active package: `data/ml/kern_1024_v1/`:

| Artifact | Meaning |
| --- | --- |
| `images/train/` | 84 native images for training after labeling |
| `images/val/` | 13 images for model/threshold selection |
| `images/test/` | 30 protected test images, never for fitting/tuning |
| `annotation_import/{train,val,test}.zip` | Images packaged separately for import |
| `manifest.jsonl` | Frozen IDs, split, offsets, WKT, affine, dates, valid fraction |
| `tiles_for_backend.jsonl` | Current tiles-schema fields; no database write performed |
| `dataset.template.yaml` | Template only, not a ready training dataset |
| `summary.json` | Counts, versions, hashes, geographic boundaries, limitations |

The 62 buffer entries have no exported image. Do not add them to training:
they cross geographic split boundaries. Collars are masked; white padding is
not an object or evidence of a negative sample.

## Import and split rules

Master Plan specifies Roboflow. Use an existing no-cost workspace only; no paid
training/credits/labeling service is authorized. Local annotation is possible if
access is unavailable, but record that workflow deviation.

Import each partition with its assigned split and preserve tile IDs. Disable
automatic random reassignment. If export changes filenames or partitions,
reconcile original IDs against the manifest before training. Repeated territory
from another year must stay in the same partition.

## What to label

Single class: `well_symbol`, YOLO ID `0`. Mark the map symbol, not a physical
wellhead, tank farm, or words "Oil Wells". Draw tight boxes with consistent
small padding in original pixels.

- Positives: recognizable oil/gas well circles verified in map context. Purple
  revision symbols need the same context check; not every purple loop is a well.
- Hard negatives: zero/o, survey marks, contour loops, circular roads, water
  features, buildings, and tanks.
- For recognizable edge-clipped symbols, box their visible portion. If unsure,
  flag the tile for review instead of forcing a label.
- Review the whole tile. A few example boxes do not make a complete annotation.

A negative sample requires someone to verify no well symbols exist. Do not
create empty label files for unknown images. Published U-Net points are proposals
only; never automatically promote them to ground truth.

YOLO rows are `0 center_x center_y width height`, normalized to 1024. They contain
no confidence score. Keep full exports outside Git, recording actual counts
per split/era and the source/split manifest identity.

## Completion

- >=300 human-reviewed symbols overall; report the training count separately.
- All included train/val images reviewed, including negatives.
- >=30 test images labeled without tuning against them.
- No geography/year leakage or automatic random repartitioning.
- Ambiguous decisions consistent across annotators.
- Actual-map control points and ten-known-well offsets still checked; affine
  arithmetic alone does not prove location accuracy.

Only after labeling/review should the YAML template become an active training
configuration. Use `imgsz=1024`; no paid GPU or cloud training is authorized.
