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

## First session in the browser

1. Sign in at <https://app.roboflow.com/>. Use a workspace with a $0 plan;
   the current pricing page calls it Free Tier. Do not activate a paid plan,
   link a payment card, buy credits, or start paid labeling/training jobs.
2. Create a project named `dowser-kern-well-symbols` with type **Object Detection**
   (axis-aligned bounding boxes). A class field is not required at project
   creation: create our single class `well_symbol` when drawing the first box.
3. Upload `data/ml/kern_1024_v1/annotation_import/train.zip` (84 PNGs) via
   **Upload Data**. Alternatively select PNGs from `images/train/`. Keep original
   tile filenames and name the batch `kern_1024_v1_train`. Do not upload full TIFF
   sheets, manifests, or the preliminary `labeling_v1` directory.
4. Open an image in the annotation interface (from Assign/Annotate or Dataset).
   A useful first training example is `usgs_293661_x00511_y02820.png`.
   Choose the rectangle **Bounding Box** tool (`B`), zoom in, draw one tight box
   per confirmed symbol. For the first box, type `well_symbol` into the class
   selector and create/save that class; select the same class for later boxes.
   The screenshot's **Classes & Tags** sidebar entry is for class management;
   **Tags** on the upload page describes images and is not the object class.
   Use ordinary manual boxes;
   do not invoke AI labeling, Smart Polygon, or cloud training.
5. Fully review 3–5 training images first and compare decisions with another
   annotator before dividing the larger batch. Save changes and confirm that
   reopening an image retains its boxes. Do not mark partial work complete.

When reviewed images are added to Dataset, keep this entire batch in **Train**.
Do not randomly repartition it. Later import `val.zip` and `test.zip` as separate
batches and retain Validation/Valid and Test respectively. Validation is for
tuning; protected test labels are for final evaluation. Images are still 1024 px;
do not generate a resized/augmented version during the first annotation session.

Our target is at least 300 human-reviewed **symbol instances**, not 300 images.
One image can contain many instances. Helpers can annotate different images,
but everyone uses the same class, box policy, and full-image review rule.

UI references checked 2026-10-23:
[uploading images/ZIPs](https://docs.roboflow.com/adding-data/object-detection),
[box tool, class selection, null labels](https://docs.roboflow.com/annotate/use-roboflow-annotate),
[current plan names and credit features](https://roboflow.com/pricing).
Button placement can vary; preserving our existing split is required regardless
of the UI layout. No workspace/project or external upload was performed by this
documentation update.

## Assisted alternative: review proposals instead of drawing every box

Drawing every box from scratch is not mandatory. Automatically proposed boxes
may be corrected and completed by humans, with their origin preserved. Only
fully reviewed images may enter supervised training. Four images is an initial
review batch, not a requirement to label all 84 train images before a baseline.
Use only the explicitly selected, fully reviewed subset for training; exclude
unreviewed images instead of creating empty labels. Keep original split IDs.

An offline pilot now reuses **published point predictions**, with attribution,
for the exact pinned Oil Center 293661 raster. It does not run the external
U-Net or replace the planned YOLO detector. These proposals cover 1954 only;
reviewed examples from 1992, hard negatives, validation, and test remain needed.

```sh
# If the small attributed EDX files are absent in a fresh clone:
.venv/bin/python pipeline/research/region_sources.py edx
# Local conversion only; refuses existing output:
.venv/bin/python -m pipeline.propose_annotations
```

Active output is separate: `data/ml/proposals_pilot_v2/`. The earlier local v1
pilot lacks the import label map; retain it as preliminary and use v2.

- Open `preview.html` in a browser to toggle proposed boxes over unchanged
  original images. This is a preview, not an annotation editor.
- `proposals.json` retains published IDs, unreviewed status, and nearest-record
  distance. That distance is never treated as confidence.
- `roboflow_proposals_train.zip` contains four images and YOLO text proposals
  with `darknet.labels` mapping class 0 to `well_symbol`. There is no active
  training YAML. See the [Roboflow Darknet format](https://roboflow.com/formats/yolo-darknet-txt).
- Import for editing into a separate Object Detection review project, for
  example `dowser-kern-proposals-review`, retaining Train for all four images.
  Do not replace existing annotations in the original project. Imported boxes
  must still be reviewed even if the platform immediately adds them to Dataset.
- Inspect the whole image: delete false boxes, add missing symbols, adjust box
  centers and sizes, and record the reviewed tile IDs/reviewer. Export reviewed
  results and reconcile original tile IDs before creating any training subset.

Pilot box dimensions are a fixed 16 px heuristic, not measured symbol outlines.
There may be systematic coordinate/box-size errors and false predictions. No
accuracy or labeling-time saving has been measured. The four images overlap:
proposal counts are not counts of independent wells or reviewed symbols.
Published proposals are rejected for validation/test/buffer tiles in code.
Keep the final test annotation independent of this prelabeling source.

## What to label

Single class: `well_symbol`, YOLO ID `0`. Mark the map symbol, not a physical
wellhead, tank farm, or words "Oil Wells". Draw tight boxes with consistent
small padding in original pixels.

The common historic symbol is a small hollow black circle, often repeated in
oil-field clusters. USGS historical instructions explicitly specify a small
black circle for oil/gas wells; context and the sheet legend still matter.
See [USGS historical cartographic instructions](https://pubs.usgs.gov/bul/0788e/report.pdf).
Each symbol gets its own rectangle, never one rectangle around an entire cluster.

- Positives: recognizable oil/gas well circles verified in map context. Purple
  revision symbols need the same context check; not every purple loop is a well.
- Hard negatives: zero/o, survey marks, contour loops, circular roads, water
  features, buildings, and tanks.
- For recognizable edge-clipped symbols, box their visible portion. If unsure,
  flag the tile for review instead of forcing a label.
- Boxes for separate nearby symbols may overlap; use one tight box per symbol,
  never a combined box around a distinguishable group. Unresolvable merged or
  faint signs require review rather than guessing or silently treating as absent.
- Review the whole tile. A few example boxes do not make a complete annotation.

A negative sample requires someone to verify no well symbols exist. Do not
create empty label files for unknown images. Published U-Net points are proposals
only; never automatically promote them to ground truth.
In Roboflow, use **Mark Null** only after reviewing the full image and finding
no target symbols. Do not create a `background` class or boxes for lookalikes.
Leave an ambiguous image unfinished for review instead of marking it empty.

YOLO rows are `0 center_x center_y width height`, normalized to 1024. They contain
no confidence score. Keep full exports outside Git, recording actual counts
per split/era and the source/split manifest identity.

## Preserve and export reviewed work

Emir's screenshot shows 271 `well_symbol` boxes on
`usgs_102321_x01250_y03651.png`, which our manifest assigns to Train / 1992.
He reports this image complete. Preserve that manual work; it is distinct from
the 1954 published proposals, and must not be replaced by their import archive.
The screenshot count alone does not verify correctness, completeness or export.

For the next handoff, save/reopen the image to confirm annotations persist,
then add only fully reviewed images to Dataset, keeping their original Train
membership. Leave unfinished images out; do not mark them empty for export.
Export reviewed work as a YOLO ZIP through Versions/Export, with original 1024 px
geometry and no augmentations, resize, cropping, or split rebalancing. Export
does not require starting cloud training. Do not activate any paid resource.
See [Roboflow's export procedure](https://docs.roboflow.com/datasets/exporting-data).

Save the ZIP under ignored `data/ml/reviewed_exports/`; preserve the downloaded
archive unchanged. Before building a training dataset, verify exported class
names, label rows, normalized bounds, image dimensions, filename-to-manifest
mapping (Roboflow may add filename suffixes), and full-image annotation quality.
Use original PNGs if version export recompresses images but preserves geometry.
Record verified counts separately from screenshot/user-reported counts.

271 boxes on one image is progress toward the symbol-count requirement, not
evidence of coverage across eras or unseen geography. More varied reviewed
training examples, negatives, validation and test labels are still required.

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
