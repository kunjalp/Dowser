# Repairing false candidates after CalGEM matching

Started 2026-10-24 in the Cursor checkout. User forwarded Ryann's report that
11 of the top 15 reviewed final candidates were false detections, mostly small
buildings/squares. This is a downstream candidate-quality failure, not a report
that most of all 3,116 raw detections are false.

## Reproduced diagnosis

Ryann used our original CSV unchanged, not a fresh best.pt inference. Its actual
confidence range is .7100135–.9240947, with the reviewed Cursor checkpoint SHA
`d417cf36430485eb534fd1197be6cf15b4cad11c967083654fc3388e5a226b2e`.
Different runtime confidence/resolution is ruled out for this incident.

Diagnostic reproduction of unchanged backend rules gives the same counts:
3,116 raw detections -> 1,657 chained 20 m clusters, 796 with both eras,
64 with nearest documented well farther than 100 m. The local buffered CalGEM
snapshot gives 96.14% matches after dedup and median 15.3 m, consistent with
Ryann's rounded 96% / 15 m. Actual OSM priority order was not reproduced.

Most true recorded well symbols leave the candidate list after CalGEM matching.
False buildings/text lack matching well records and remain. Thus detector
precision on the complete Val set does not measure precision among unmatched
candidates. The earlier random crop inspection was inadequate for this product
boundary; reviewing the post-matching candidate slice is required.

Existing human Val: P .92 / R .9388 at .71, IoU .50; 49 positive instances on
four overlapping Oildale 1954 strips. Oil Center 1954/1992 Val examples are
negative-only. These are Val/tuning figures, not final Test or candidate quality.
High CalGEM proximity does not certify correct detection or map accuracy.

## Actual review artifacts

Under `data/ml/rollout_diagnosis_v1/`:

- `candidate_review_queue.json`: all 64 reproduced candidates; sorted by
  confidence, explicitly not Ryann's priority rank.
- `candidate_review.html`, `candidates_01_32.png`, `candidates_33_64.png`:
  crop inspection of every unmatched candidate.
- `candidate_triage.csv` / `.json`: 54 assistant-proposed rejects and ten
  unresolved cases. Fifty proposed rejects come from Train, four from Val.
  These are assistant visual judgments, not the unseen human review CSV or
  field verification. No original rows/statuses were changed automatically.
- `train_error_sources.json`: 21 source Train frames requiring full-image
  review before creating YOLO labels. A false crop does not make its full
  source image empty. Val cases and all Test imagery are excluded from mining.
- `diagnosis.json`: forwarded human counts, exact reproduction and limitations.
- `runtime_comparison.json`: separate preventive configuration diagnostic;
  not the cause of this CSV incident. Same weights at 1024/.25 yield 48/75/1,
  at 1024/.71 yield 46/4/3; at 640/.71 yield 3/16/46 on Val. At 1024/.80,
  saved predictions yield 27/2/22. Raising cutoff alone sacrifices many wells.

The file was initially absent from accessible GitHub main. Emir subsequently
forwarded its expanded contents: **62 unique human-confirmed false candidates**,
58 from Train and four from Val. All IDs match our reproduced 64-candidate set.
Normalized IDs/reviewer/times/ranks are preserved in
`ryann_confirmed_false_reviews.json` / `.csv` (not a byte-identical copy of the
original text). The remaining two candidates were not marked false; they are
not thereby verified wells. `candidate_review_human.html` shows human decisions
and prototype outcomes side by side. All 54 prior assistant-proposed rejects
were among the subsequently supplied human-confirmed false IDs.

## Bounded controlled repair experiment

Two entire native Train frames were visually checked and added as explicit
assistant-reviewed negatives, `human_verified=false`:

- `usgs_293664_x04595_y05275`: urban buildings/squares, river/canal, roads and
  text; no recognizable target oil/gas symbols.
- `usgs_293664_x02138_y03637`: blue water Wells, oil tanks, highway shields and
  railway; no target oil/gas symbols. This correctly reviewed negative was also
  present in Cursor's unused additions, but no erroneous new positive was used.

Records: `data/ml/rollout_repair_labels_v1/annotations.json`, SHA
`054e3e10213542603e15bcd607523fc3d96c5fc746fddebe05b0acb379221fdf`.
`train_mix_rollout_repair_v1.json` builds `data/ml/train_rollout_repair_v1`:
10 images, 617 boxes (568 human + 49 assistant), three reviewed negatives.
Original human files, Val audit and manifest are unchanged. Preflight passes.

Two runs start from the same reviewed Cursor checkpoint, fresh AdamW lr .0002,
native 1024, translate .1, seed 42, batch=nbs=2, max 30 epochs/patience 8:

- `kern_rollout_repair_control_v1`: original eight Train images.
- `kern_rollout_repair_hardneg_v1`: ten images with the two new hard backgrounds.

Configs are `pipeline/config/train_rollout_repair_{control,hardneg}_v1.json`.
Runs/logs retain optimizer updates/time and code/config identities. Adding data
changes updates per epoch, so this is not an equal-compute causal study.
Training is local MPS; no new dependency or cloud compute is required.

### Completed detector runs: no replacement accepted

| Run | Epochs / actual updates | Seconds | Val-selected cutoff | TP / FP / FN | F1 |
| --- | --- | ---: | ---: | --- | ---: |
| Original translate reference | 34 / 136 | 80.904 | .71 | 46 / 4 / 3 | .9293 |
| Fine-tune control | 11 / 44 | 25.309 | .05 | 38 / 6 / 11 | .8172 |
| Fine-tune + two hard negatives | 9 / 45 | 22.795 | .25 | 41 / 16 / 8 | .7736 |
| Same original pretrained/translate recipe + two hard negatives | 20 / 100 | 48.869 | .24 | 34 / 17 / 15 | .6800 |

The last run uses `train_rollout_repair_pretrained_v1.json`; its sole training
factor change from the original recipe is the two reviewed backgrounds. At the
old .71 cutoff all three new runs have TP0/FP0/FN49. Changing scores/cutoff does
not rescue their inferior Val counts. Their named weights/logs are preserved;
none replaces the baseline. Adding a few empty images did not solve this case.

### Crop verifier prototypes: partial improvement, still not production-ready

`pipeline/train_symbol_verifier.py` implements an optional second-stage RGB48
classifier. It learns from target crops on frozen Train and the 58 human-reviewed
false Train crops. It does NOT train on the four human false Val cases or Test.
Only a crop's centered object is labeled negative; the whole source frame is
not automatically assigned an empty YOLO label.

- v1 used 617 GT-box positives (568 human / 49 assistant). At fixed verifier .5,
  the balanced-Val-BCE-selected epoch gave TP22/FP4/FN27: rejected.
- v2 used 568 YOLO Train boxes matched one-to-one to reviewed GT at IoU>=.3 and
  detector score>=.5: 520 derive from human GT and 48 from assistant GT. This
  matches runtime crop framing more closely. Context-size jitter broadened to
  .65..1.35. At fixed .5 it gave 31/2/18: rejected. Val-calibrating that checkpoint
  to .365 gave 45/3/4 and left 46 known false candidate groups: insufficient.
- v3 retains v2 training data/architecture/seed, but selects epoch and verifier
  cutoff by Val F1 subject to TP>=45/49. This is explicit further Val tuning,
  not independent validation. Epoch 13 / verifier cutoff **.059** (YOLO still .71)
  gives **TP46/FP2/FN3**, P=.9583/R=.9388/F1=.94845. The cutoff .059 is a separate
  classifier score, not a replacement YOLO confidence or a calibrated probability.

Each verifier fit ran 15 local MPS epochs in approximately 2–3 seconds. v3 has
540 completed optimizer iterations, derived from the completed loop (not a
separate optimizer-hook instrument). Run records retain exact versions, data/
code/checkpoint hashes and the complete selection history. Matching source
snapshots are preserved as `data/ml/runs/kern_symbol_verifier_v*/source.py`.

v3 checkpoint SHA:
`32e93ccf0ef478255cfae4e53f679e43f25efd9134432ba7e005e668793badba`.
Explicit experimental config: `pipeline/config/inference_symbol_verifier_v3.json`.
`pipeline/filter_symbol_detections.py` applies the classifier to the pinned
Train/Val CSV and writes separate accepted/rejected files with `verifier_score`.
Original detector confidence and coordinate/evidence fields are byte-equivalent
as parsed CSV strings; no production status is automatically changed.

Actual v3 output in `verifier_v3_filtered/`:

- 3,116 -> 2,952 raw rows (164 rejected), 1,547 dedup groups, 24 unmatched groups.
- **40/62 confirmed false representatives rejected, 22 known false groups remain.**
- Two original candidates not marked false also remain; neither is a verified well.
- Re-evaluation from the actual accepted CSV reproduces Val TP46/FP2/FN3.

This is a useful prototype, **not an accepted production fix**: 22 known errors
among the 24 remaining unmatched groups are still unacceptable. The 58 negative
Train feedback examples were used during fitting, so removing these known
examples is not independent generalization evidence. Better Val F1 does not
override the downstream failure. The base best.pt alone does not include this
verifier; fresh two-stage inference would require both models and its crop rules.

Artifacts: `repair_validation.json`, `verifier_calibration.json`,
`verifier_v3_filtered/product_comparison.json`, and `repair_outcome.json`.
All three YOLO failures and verifier failures are retained. No archive, canonical
model pin, frozen Test protocol or live candidate store was replaced.

## Acceptance and next action

Compare fixed-cutoff native Val counts and the same Val-only F1 sweep, then
review the complete post-CalGEM candidate slice and known human-confirmed errors.
Do not call training feedback cases independent accuracy. Keep source/confidence
and all raw detections; proposed false candidates need explicit review status,
not silent deletion or automatic well verification. A lower candidate count by
itself is not evidence of better detection: check lost real symbols too.

If the bounded repair fails, record that and expand full-image annotations for
the high-impact Train contexts, including mixed true-well/building images;
do not keep increasing epochs or discarding every rectangular detector box.
Circle and square objects both have rectangular bounding boxes.

The expanded human-feedback queue is now
`train_error_sources_human_confirmed.json`: **24 Train frames**, of which two
already have full original labels, two are the newly reviewed negatives, and
**20 still require complete-image annotation**. Preserve existing positive
labels and explicitly resolve water wells, landmark/radio circles, squares and
text. The high-impact `usgs_293664_x03776_y05275` frame mixes many true hollow
symbols with 14 false-candidate structures; it cannot be marked empty.

Immediate product mitigation is to apply Ryann's human false-detection review
to candidate eligibility, retaining review provenance. A wrong map symbol is
not a field-confirmed absence of a physical well: do not automatically turn
these crop judgments into a field `no_well` finding. No backend changes were made.

67 software tests pass, including the crop boundary/Train-only guards and
calibration recall constraint. Test annotation should continue independently;
no Test inference or Test-driven tuning was performed. If a later replacement
is accepted, freeze a new complete pipeline protocol before final Test inference,
including any verifier checkpoint/cutoff. The earlier frozen protocol is retained.

Primary references: [Ultralytics inference settings](https://docs.ultralytics.com/modes/predict/)
and [dataset variety, consistent labels and reviewed backgrounds](https://docs.ultralytics.com/yolov5/tutorials/tips-for-best-training-results/).
The latter is general YOLOv5 advice, not a guaranteed result for our YOLO11 model.
