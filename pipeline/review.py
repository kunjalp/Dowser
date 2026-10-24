#!/usr/bin/env python3
"""
Record candidates that a person reviewed and found are NOT well symbols (false detections).

They are kept on record in pipeline/review/false_detections.csv (committed to git), never
silently deleted. score.py leaves them out of the ranking, so they drop off the map and the
briefs, impact numbers and ranks are recomputed without them.

Ranks are the CURRENT ranks shown in the app (same order as pipeline/data/scored.csv).
Run from the repo root:
  python pipeline/review.py --false-ranks 1 2 4 6          # shows what it will mark, asks to confirm
  python pipeline/review.py --list                          # show everything marked so far
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import sys

import pandas as pd

SCORED = os.path.join("pipeline", "data", "scored.csv")
REVIEW = os.path.join("pipeline", "review", "false_detections.csv")
FIELDS = ["detectionId", "reason", "reviewer", "reviewedAt", "rankWhenReviewed", "quadName", "lat", "lon"]


def load_false_ids(path: str = REVIEW) -> set[str]:
    if not os.path.exists(path):
        return set()
    return set(pd.read_csv(path, dtype=str)["detectionId"].dropna())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--false-ranks", type=int, nargs="+")
    ap.add_argument("--reason", default="not a well symbol (manual review of evidence crop)")
    ap.add_argument("--reviewer", default=os.environ.get("USER", "team"))
    ap.add_argument("--yes", action="store_true", help="skip the confirmation question")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list or not args.false_ranks:
        if os.path.exists(REVIEW):
            print(pd.read_csv(REVIEW).to_string(index=False))
        else:
            print("Nothing marked yet.")
        return

    df = pd.read_csv(SCORED, dtype={"detectionId": str})
    df = df.sort_values("score", ascending=False).reset_index(drop=True)
    already = load_false_ids()
    bad = [r for r in args.false_ranks if r < 1 or r > len(df)]
    if bad:
        sys.exit(f"Ranks out of range (1..{len(df)}): {bad}")
    rows = df.iloc[[r - 1 for r in args.false_ranks]]
    print("Will mark as false detections:")
    for r, (_, row) in zip(args.false_ranks, rows.iterrows()):
        flag = "  (already marked)" if row["detectionId"] in already else ""
        print(f"  rank {r:>3}  score {row['score']:.2f}  {row.get('quadName', '')}  {row['detectionId']}{flag}")
    if not args.yes and input("Type yes to save: ").strip().lower() != "yes":
        sys.exit("Nothing saved.")

    os.makedirs(os.path.dirname(REVIEW), exist_ok=True)
    new_file = not os.path.exists(REVIEW)
    now = dt.datetime.now().isoformat(timespec="minutes")
    with open(REVIEW, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        for r, (_, row) in zip(args.false_ranks, rows.iterrows()):
            if row["detectionId"] in already:
                continue
            w.writerow({"detectionId": row["detectionId"], "reason": args.reason, "reviewer": args.reviewer,
                        "reviewedAt": now, "rankWhenReviewed": r, "quadName": row.get("quadName", ""),
                        "lat": row["lat"], "lon": row["lon"]})
    print(f"Saved to {REVIEW}. Now re-run: score.py, briefs.py, load_candidates.py, impact.py")


if __name__ == "__main__":
    main()
