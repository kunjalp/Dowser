#!/usr/bin/env python3
"""
One command for the undocumented lane: model detections + hand labels -> scored.csv.

Runs, in order, with the defaults of each step:
  dedup.py --detections <model> <hand labels>   one row per physical well symbol
  match_wells.py --detections deduped.csv        nearest CalGEM record; candidate if none within 100 m
  enrich.py                                      distances to homes, schools, water; buildings nearby
  score.py                                       scoreParts + score -> pipeline/data/scored.csv
then prints the human-review summary (pipeline/review/*.csv) for the candidates.

Run from the repo root:
  python pipeline/run_undocumented.py
  python pipeline/run_undocumented.py --model other.csv --hand-labels other_gt.csv
Next: python pipeline/briefs.py, then python pipeline/load_candidates.py (see its --reset-status, --prune).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join("pipeline", "data")
sys.path.insert(0, HERE)
from review import resolve  # noqa: E402


def step(script: str, *args: str) -> None:
    print(f"\n== {script} {' '.join(args)}", flush=True)
    subprocess.run([sys.executable, os.path.join(HERE, script), *args], check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.path.join(DATA, "detections.csv"), help="model detections")
    ap.add_argument("--hand-labels", default=os.path.join(DATA, "detections_groundtruth.csv"))
    args = ap.parse_args()

    deduped = os.path.join(DATA, "deduped.csv")
    step("dedup.py", "--detections", args.model, args.hand_labels, "--out", deduped)
    step("match_wells.py", "--detections", deduped)
    step("enrich.py")
    step("score.py")

    scored = pd.read_csv(os.path.join(DATA, "scored.csv"), dtype={"detectionId": str})
    reviews, conflicts = resolve(scored)
    verdicts = [v["verdict"] for v in reviews.values()]
    print(f"\nUndocumented candidates: {len(scored)}   verified: {verdicts.count('verified')}   "
          f"rejected: {verdicts.count('rejected')}   not reviewed: {len(scored) - len(reviews)}   "
          f"conflicts: {len(conflicts)}")
    for det in conflicts:
        print(f"  CONFLICT: {det} is in false_detections.csv but merged with a hand label; kept verified")


if __name__ == "__main__":
    main()
