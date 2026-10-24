# Cursor independent improvement experiment — results

Date: 2026-10-24, America/Los_Angeles.
Branch: `ml/cursor-improvements`. Worktree: `/Users/emirtg/Desktop/dowser-cursor`.
Base commit at handoff: `4bc0bbec4b6f13b0565a1dbc0608fe68ea9dcebb`.
Frozen model/code reference: `8b44b8a76bf6b969b633871c23dc927745f58005`.
Training runs were recorded with `code_dirty=true` because new Cursor configs
existed before this results file was committed. No merge into `main`.
`pipeline/config/inference_selected.json` was not replaced.

## Problem and hypotheses

Reference `kern_yolo11n_data_v2` at Val-selected cutoff **.24** is
**TP44 / FP17 / FN5**, P=.7213114754, R=.8979591837, F1=.8000. Residual errors
are digits (`9`/`0`/`399`/`460`), hollow squares, tanks, and a few canal-edge
misses. Val has 49 positives on four overlapping 1954 Oildale strips; 1992 Val
is all-negative. Test was never read for labels, mining, thresholds, or
selection.

One-factor hypotheses, in order:

1. More diverse **Train positives** that mix real hollow wells with digits,
   tanks, and buildings will cut lookalike FP without collapsing recall.
2. Adding **targeted hard negatives** (water wells labeled Well, highway-shield
   digits, oil tanks) on top of (1) will further suppress those FP types.
   `train_mixed_v2` already showed that extra generic empties were slightly
   worse; these empties are different content, still recorded separately.
3. A single 1954 mixed lookalike-positive tile, without new 1992 images, tests
   whether 1992 additions in (1) were the recall regression.
4. Horizontal flip (`fliplr=0.5`) on the **same** `train_mixed_v1` data as the
   reference, architecture unchanged.
5. YOLO11s, same `train_mixed_v1` data and training recipe as the reference.

New labels are `annotation_source=assistant_visual_review`,
`human_verified=false`. Model/Hough boxes were review aids only. Uncertain
marks were excluded. Original 568 human Train boxes, 15 human Val images/labels,
and 30 Test IDs were not modified.

## Frozen identities that remained

| Artifact | SHA-256 |
| --- | --- |
| `data/ml/kern_1024_v2/manifest.jsonl` | `ebb2f8a4fdfefabf7dcdd9f3e4339f4c5912d4b2b2ecbb448b3f6da06c0ef572` |
| `data/ml/reviewed_validation_v1/audit.json` | `1a88c5c0d2d38e96c87ff7ad395e93d0c2cae52a80ccfa7437a39170201fcc2e` |
| `data/ml/reviewed_v2/audit.json` | `eee6fa445dd1b0ddd606ad18704f870e617c0156d310925425e8bde8a746d55b` |
| Reference `kern_yolo11n_data_v2` `best.pt` | `a409254df3769cb119b0b2396e44df5038a669dc748d22a28a4fdf173095f5df` |
| Pretrained YOLO11n | `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1` |

Human Train PNG/label bytes in every new mix equal `reviewed_v2` for all five
IDs. Test remains 30 unlabeled images and was unused. File identities vs
`/Users/emirtg/Desktop/dowser` are distinct inodes with matching reference
bytes.

## Implemented Train changes

Assistant visual review of native 1024 px Train tiles only. Record:
`data/ml/cursor_assistant_review_v1/annotations.json`
SHA `d98d4565615d700ba46831d33d3e77c165d2792344255494f562dca0df66ec29`.
Combined with unchanged `assistant_review_v1` as
`combined_with_v1.json`
SHA `592ac397107211355891cf965fbc5035f8d6942f48ed25be81ef70bf37356917`.
Tight 14 px boxes. Purple overlay plots are under
`data/ml/cursor_assistant_review_v1/overlays/`.

| Tile | Era | Decision | Boxes | Why |
| --- | --- | ---: | ---: | --- |
| `usgs_102321_x03707_y05289` | 1992 | mixed positive | 27 | Open-circle wells among 785/760/889/860/800, filled tanks, buildings |
| `usgs_102321_x04526_y04470` | 1992 | mixed positive | 13 | Open-circle wells among filled tanks, squares, 800/744; one missed open circle added as H2 |
| `usgs_293664_x03776_y02818` | 1954 | mixed positive | 3 | Hollow wells next to 566/549/584/629, water tanks, pumping-station tanks/squares |
| `usgs_293664_x01319_y03637` | 1954 | empty | 0 | Blue labeled water Well + elevation 419/410; no oil/gas well_symbol |
| `usgs_293664_x02138_y03637` | 1954 | empty | 0 | Two blue Wells, OIL TANKS, highway 99/466/65; no oil/gas well_symbol |

Rejected: filled tanks, building squares, contour loops, elevation digits,
section numbers, highway shields, blue water wells. The pumping-station filled
dots were treated as tanks, matching prior assistant policy on
`usgs_293664_x02138_y05275`.

Mixes (builder `pipeline.build_train_mix`, original human files copied
byte-for-byte):

| Mix | Config | Images | Human boxes | Assistant boxes | Empty | Audit SHA |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `train_mixed_cursor_v1` | `pipeline/config/train_mix_cursor_v1.json` | 11 | 568 | 92 | 1 | `31cb34bd47f021e36cf9d5b6aea60f2fc8ab8d0781c5253f2b8817979f15024e` |
| `train_mixed_cursor_v2` | `pipeline/config/train_mix_cursor_v2.json` | 13 | 568 | 92 | 3 | `870bfb70cab6ac562780e562da27f734bbf7942adfc8cbd4f9f7396ed7a925c9` |
| `train_mixed_cursor_v3` | `pipeline/config/train_mix_cursor_v3.json` | 9 | 568 | 52 | 1 | `a04d66e6cd113e5435a2b693b4fc17ce4982222add506daf44cbc2b9723afbe3` |

cursor_v1 = previous mix_v1 IDs plus the three new mixed positives.
cursor_v2 = cursor_v1 plus the two new targeted empties (not the old v3 empties).
cursor_v3 = previous mix_v1 IDs plus only the 1954 mixed-positive tile.

## Training environment

All comparable candidates: Python 3.12.14, torch 2.14.1, torchvision 0.29.1,
ultralytics 8.4.185, numpy 2.5.4, Apple M5 MPS, 24 GiB, seed 42, AdamW lr0
0.001, warmup 3, native 1024, batch=nbs=2, amp false, mosaic/mixup/hsv/scale
off unless the named factor, max 50 epochs / patience 10, NMS IoU .7,
max_det=1000. Lock: `pipeline/requirements-train.lock.txt`.
No cloud compute. YOLO11s weights fetched from the public Ultralytics v8.3.0
release, SHA `85a76fe86dd8afe384648546b56a7a78580c7cb7b404fc595f97969322d502d5`.

A first `cursor_data_v1` fit ran on **CPU** because the sandbox hid MPS. It is
preserved and **not** used for selection. Comparable runs use `*_mps` names.

Exact train command pattern:

```sh
pipeline/.venv/bin/python -u -m pipeline.train_detector \
  --config pipeline/config/train_cursor_data_v1.json --name cursor_data_v1_mps
```

Preview / sweep / compare (same native protocol as the reference: IoU .50,
confidence-first one-to-one per tile, Val F1 grid .05..95 step .01, ties →
higher cutoff):

```sh
pipeline/.venv/bin/python -m pipeline.preview_detector data/ml/runs/cursor_data_v1_mps
pipeline/.venv/bin/python -m pipeline.evaluate_preview \
  data/ml/runs/cursor_data_v1_mps/preview/predictions.json --sweep
pipeline/.venv/bin/python -m pipeline.evaluate_preview \
  data/ml/runs/cursor_data_v1_mps/preview/predictions.json --confidence 0.70
pipeline/.venv/bin/python -m pipeline.compare_previews \
  data/ml/runs/kern_yolo11n_data_v2/preview/predictions.json \
  data/ml/runs/cursor_data_v1_mps/preview/predictions.json \
  --output data/ml/runs/cursor_data_v1_mps/comparison_to_data_v2
```

SDK P/R/mAP remain distinct from these native counts.

## Native Validation comparison

Reference stays `kern_yolo11n_data_v2`. Scores are not calibrated; always state
cutoff. Common cutoff .70 is reported even when a model emits no boxes.

| Run | Factor | Epochs / updates | Time s | Selected cutoff | TP / FP / FN | P / R / F1 | 1992 FP | .70 TP/FP/FN |
| --- | --- | --- | ---: | ---: | --- | --- | ---: | --- |
| **data_v2 (reference)** | frozen | 24 / 96 | 52.689 | **.24** | **44 / 17 / 5** | **.7213 / .8980 / .8000** | 3 | 0 / 0 / 49 |
| cursor_data_v1_mps | +3 mixed Train positives | 33 / 198 | 108.884 | .47 | 41 / 16 / 8 | .7193 / .8367 / .7736 | 1 | 8 / 2 / 41 |
| cursor_data_v2_mps | v1 mix +2 targeted empties | 13 / 91 | 40.767 | .91 | 37 / 20 / 12 | .6491 / .7551 / .6981 | 3 | 47 / 222 / 2 |
| cursor_data_v3_mps | +1 1954 mixed positive only | 22 / 110 | 59.743 | .40 | 38 / 17 / 11 | .6909 / .7755 / .7308 | 0 | 5 / 1 / 44 |
| cursor_fliplr_mps | fliplr=0.5, same mix_v1 | 26 / 104 | 64.873 | .25 | 27 / 8 / 22 | .7714 / .5510 / .6429 | 2 | 0 / 0 / 49 |
| cursor_yolo11s_mps | YOLO11s, same mix_v1 | 12 / 48 | 48.957 | .95 | 49 / 3023 / 0 | .0160 / 1.000 / .0314 | 1087 | 49 / 7950 / 0 |
| cursor_data_v1 CPU | same data as v1_mps, **CPU** | 36 / 216 | 178.97 | not selected | — | SDK only; not comparable | — | — |

More Train images change optimizer-update counts. This is not an equal-compute
causal study. Val F1 on this repeatedly used 15-image slice is tuning, not Test.

### Decision (round 1)

Round-1 data/architecture/flip runs did **not** beat F1 .8000. Closest mixed
positives were .7736. Flip raised precision by collapsing recall. YOLO11s failed.
`inference_selected.json` was left on data_v2.

## Round 2 — other methods, same mix_v1

Same frozen human Train/Val/Test, same pretrained YOLO11n unless noted, seed 42,
MPS. One major factor each. Native protocol unchanged.

| Run | Factor | Epochs / updates | Time s | Selected cutoff | TP / FP / FN | P / R / F1 | 1992 FP | .70 TP/FP/FN |
| --- | --- | --- | ---: | ---: | --- | --- | ---: | --- |
| **data_v2 (reference)** | frozen | 24 / 96 | 52.689 | .24 | 44 / 17 / 5 | .7213 / .8980 / .8000 | 3 | 0 / 0 / 49 |
| **cursor_translate_mps** | **translate=0.1** | **34 / 136** | **80.904** | **.71** | **46 / 4 / 3** | **.9200 / .9388 / .9293** | **0** | **46 / 5 / 3** |
| cursor_ft_datav2_mps | fine-tune data_v2, lr0=2e-4 | 12 / 48 | 30.136 | .17 | 42 / 10 / 7 | .8077 / .8571 / .8317 | 3 | 5 / 0 / 44 |
| cursor_cls15_mps | cls=1.5 | 21 / 84 | 52.222 | .48 | 35 / 13 / 14 | .7292 / .7143 / .7216 | 1 | 9 / 1 / 40 |
| cursor_erasing0_mps | erasing=0 | 24 / 96 | 59.929 | .24 | 44 / 17 / 5 | .7213 / .8980 / .8000 | 3 | 0 / 0 / 49 |
| cursor_copypaste_mps | copy_paste=0.3 | 24 / 96 | 58.275 | .24 | 44 / 17 / 5 | .7213 / .8980 / .8000 | 3 | 0 / 0 / 49 |

`erasing=0` and `copy_paste=0.3` matched data_v2 native counts exactly;
copy-paste is a no-op while mosaic=0, and random-erasing did not change this
fit. Higher `cls` hurt recall. Fine-tuning the selected checkpoint improved
F1 to .8317 (fewer FP, slightly more FN).

### Translate stability (same recipe, other seeds)

| Seed | Run | Selected cutoff | TP / FP / FN | F1 vs .8000 |
| ---: | --- | ---: | --- | --- |
| 42 | cursor_translate_mps | .71 | 46 / 4 / 3 | **.9293 beat** |
| 43 | cursor_translate_s43_mps | .58 | 43 / 14 / 6 | **.8113 beat** |
| 7 | cursor_translate_s7_mps | .95 | 38 / 164 / 11 | .3028 collapse (best epoch 2) |

Two of three seeds beat the reference. Seed 7 stopped immediately and is not
usable. Tiny-data MPS runs remain seed-sensitive; do not treat .9293 as a
stable population estimate.

### Decision (round 2)

**Best Cursor candidate: `cursor_translate_mps` (seed 42, translate=0.1).**
Same Train as data_v2. Val-selected .71: TP+2, FP 17→4, FN 5→3, 1992 FP 3→0.
F1 .8000→.9293. At common .70 it still has TP46/FP5/FN3, while data_v2 emits
no boxes. Remaining errors: 4 squares/structures and 3 canal-edge FN; digit
`399`/`460` fires are gone on this Val slice.

Candidate pin (does **not** replace `inference_selected.json`):
`pipeline/config/inference_cursor_translate.json`.
Paired HTML:
`data/ml/runs/cursor_translate_mps/comparison_to_data_v2/comparison.html`.
Unmatched crops:
`data/ml/runs/cursor_translate_mps/preview/remaining_unmatched.png`.

This is still human-Val tuning on 15 overlapping 1954 tiles, not Test.

## Checkpoints, reports, and errors

| Run | `best.pt` SHA | Predictions SHA | run.json SHA | Paired HTML |
| --- | --- | --- | --- | --- |
| cursor_data_v1_mps | `45fd7c389a3a6e934309a78d83c8a9a4c72271ed369cce261874f6b1cffd5416` | `88e28fb3534474772228b5d0330aa5057826f90b4d970220f9c8d91a5c498fd4` | `6545d314c4788d65b11e02bc038b17344f232f9f99fe6e107313b2f42e1e7ae0` | `data/ml/runs/cursor_data_v1_mps/comparison_to_data_v2/comparison.html` |
| cursor_data_v2_mps | `69c5bffd7e150efddea038d01445eb0bfd11740402d75ebaa7e70cd5539e594c` | `45839db8e034a7e2cc726581d9290503c5b65b039783ef0227f1c36957345a67` | `b11d153c33d6a157ca28ee25276fc636861a34a90a0258a1bded6061deea174e` | `data/ml/runs/cursor_data_v2_mps/comparison_to_data_v2/comparison.html` |
| cursor_data_v3_mps | `afe7906bc7808928efee16061fc3c3cdac9ad8356a8071abbd6f37e0bd38d168` | `47131eda061d9a121f864b31b233bd2656782ac78d6f61f54db432485efb25a5` | `1cc737f1a69db624f1096061f1e3585204b4dcaae1e03d5db8444af8160466f2` | `data/ml/runs/cursor_data_v3_mps/comparison_to_data_v2/comparison.html` |
| cursor_fliplr_mps | `14f7b65b76af3971825ab6e53ccbc22c4a6c3828916e90a0e8c87bc402a5fee4` | `e55cc571a7586870e11f8b1a842d3861829a0cdb30e8172871cca1dfca03fda2` | `dff37994f6696c07c9d8fbabeb9180a4d3e0a37c3d44001921e521abb41d2969` | `data/ml/runs/cursor_fliplr_mps/comparison_to_data_v2/comparison.html` |
| cursor_yolo11s_mps | `1eb2e948204afba90d41345f309a9af0a09b94c027338089e8f4706525c8dd71` | `cb046d9536c864f660cbff524a1c55ca02a949c0ca387112b4b99d1eff5b54f2` | `33692dac1013166e2a89928bfa1c115a055020d67f0d8ff6160c520f103b9e23` | `data/ml/runs/cursor_yolo11s_mps/comparison_to_data_v2/comparison.html` |
| cursor_translate_mps | `d417cf36430485eb534fd1197be6cf15b4cad11c967083654fc3388e5a226b2e` | `3fd32bda4d5186314ea06320e115c1d620c2110796e5f3e0e7274442d4afbeb6` | `88a4347b465e66ac9ade22c26bc577efc42a040c5d0c34f8e5c7480f6f409958` | `data/ml/runs/cursor_translate_mps/comparison_to_data_v2/comparison.html` |
| cursor_ft_datav2_mps | `693d40f9a9e2a0ffc12ecd48abb86069a0668dac18853da17817916299e1159f` | `650f94d6575ed8d4e6860b97e390479f45e79e4cf2554f5d84b01eb3f857dd26` | `40f6f9343f0a21d44a09dc648c0af1dea4c0292c21ec8d8bcc0f259595b6c0c7` | `data/ml/runs/cursor_ft_datav2_mps/comparison_to_data_v2/comparison.html` |
| cursor_cls15_mps | `f107a663ad56d317ebe578d3ce90d6079313e8a390b015e61912cd23946c1a39` | `c7795269454b7f2353d71fcf5016b19f0bd776c31626f19f7b6da78aa953f179` | `4bc97d6cbd4fd646957a5a3cf1449782e194ab62b09a70ea924a89e1f4512a9d` | `data/ml/runs/cursor_cls15_mps/comparison_to_data_v2/comparison.html` |
| cursor_translate_s43_mps | `66afa6a0a20649c4cbeaa9d1009a4e2e46bf39eaeac6b98fd9900a652ca51165` | `f2be5f629e8974e638db8a5f88b78792072b6bcd6d39817490404868c7d798a3` | see run.json | `data/ml/runs/cursor_translate_s43_mps/comparison_to_data_v2/comparison.html` |
| cursor_translate_s7_mps | `a26f516e8b56dea41eb9c4e313bc82865dfe66724a19db2ff436b760a164ee99` | `7a7bc961799e576bf9d7bd1745665b1d16e4639d7ec4a083d179f30ea13e1110` | see run.json | `data/ml/runs/cursor_translate_s7_mps/comparison_to_data_v2/comparison.html` |

Per-run selected preview: `data/ml/runs/<name>/preview/preview_selected.html`.
Threshold grids: `preview/threshold_selection.json`.

Round-1 mixed-data remaining unmatched:
`data/ml/runs/cursor_data_v1_mps/preview/remaining_unmatched.png`.
Best-candidate remaining unmatched (4 FP squares + 3 canal FN):
`data/ml/runs/cursor_translate_mps/preview/remaining_unmatched.png`.

## Tests, limitations, next action

- `pipeline.train_detector --check-only` passed on each Cursor train config.
- `.venv/bin/python -m unittest discover -s pipeline/tests -q`: **54 tests OK**.
- MPS was required for comparable runs; the CPU `cursor_data_v1` directory is a
  sandbox artifact, not a challenger.
- Reference preview artifacts were restored byte-for-byte after an earlier
  helper overwrite.
- Limitations: Val has 49 positives on four overlapping 1954 strips; no 1992
  positive Val recall; translate is seed-sensitive (s7 collapsed); assistant
  labels are not human GT; this is not Test.
- **Exact next action:** reviewer inspects translate vs data_v2 HTML and
  remaining crops. Candidate pin is
  `pipeline/config/inference_cursor_translate.json`. Do not merge to main.
  Adopt into `inference_selected.json` only after review. Independent 30-image
  Test labeling remains the accuracy gate.
