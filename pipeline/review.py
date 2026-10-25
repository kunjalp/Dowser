#!/usr/bin/env python3
"""
Human review of undocumented candidates: which are real well symbols and which are not.

Two files, both committed to git, never silently deleted:
  pipeline/review/verified.csv          looked at the evidence crop: a real well symbol
  pipeline/review/false_detections.csv  looked at the evidence crop: NOT a well symbol (rejected)

Rules (resolve() below), applied by load_candidates.py by detectionId:
  - in verified.csv                                  -> verified
  - in false_detections.csv                          -> rejected, with its reason (DEFAULT_REJECT_REASON if blank)
  - a hand-labeled row with no model match           -> verified (a person labeled it)
  - rejected, but merged with a hand-labeled row     -> CONFLICT: kept verified and listed
Rejected candidates stay in scored.csv and in Convex, listed last and never ranked or queued.

Ranks are the CURRENT ranks shown in the app: non-rejected rows of pipeline/data/scored.csv by score.
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
VERIFIED = os.path.join("pipeline", "review", "verified.csv")
FIELDS = ["detectionId", "reason", "reviewer", "reviewedAt", "rankWhenReviewed", "quadName", "lat", "lon"]
DEFAULT_REJECT_REASON = "Not an oil/gas well symbol (water well, landmark or building)"
HAND_LABEL_REASON = "Hand-labeled as a well symbol"
HAND_LABEL_BY = "hand labels (detections_groundtruth.csv)"


def _read(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame(columns=["detectionId"])
    return pd.read_csv(path, dtype=str).dropna(subset=["detectionId"])


def load_false_ids(path: str = REVIEW) -> set[str]:
    return set(_read(path)["detectionId"])


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("true", "1")


def _clean(v):
    return None if v is None or pd.isna(v) or not str(v).strip() else str(v).strip()


def resolve(df: pd.DataFrame, false_path: str = REVIEW,
            verified_path: str = VERIFIED) -> tuple[dict[str, dict], list[str]]:
    """Review record per detectionId (only rows that have one), and the list of conflicts."""
    rejected = {r["detectionId"]: r for _, r in _read(false_path).iterrows()}
    verified = {r["detectionId"]: r for _, r in _read(verified_path).iterrows()}
    out: dict[str, dict] = {}
    conflicts: list[str] = []
    for _, row in df.iterrows():
        det = str(row["detectionId"])
        hand = _truthy(row.get("handLabeled"))
        hand_label = {"verdict": "verified", "reason": HAND_LABEL_REASON, "reviewedBy": HAND_LABEL_BY}
        if det in verified:
            v = verified[det]
            out[det] = {"verdict": "verified", "reason": _clean(v.get("reason")) or "Well symbol in crop review",
                        "reviewedBy": _clean(v.get("reviewer")) or "team"}
            if _clean(v.get("reviewedAt")):
                out[det]["reviewedAt"] = _clean(v.get("reviewedAt"))
            if det in rejected:
                conflicts.append(det)
        elif det in rejected:
            if hand:  # a person hand-labeled this exact symbol: the label wins, but say so
                conflicts.append(det)
                out[det] = hand_label
            else:
                r = rejected[det]
                out[det] = {"verdict": "rejected", "reason": _clean(r.get("reason")) or DEFAULT_REJECT_REASON,
                            "reviewedBy": _clean(r.get("reviewer")) or "team"}
                if _clean(r.get("reviewedAt")):
                    out[det]["reviewedAt"] = _clean(r.get("reviewedAt"))
        elif hand and str(row.get("source")) == "ground_truth":
            out[det] = hand_label
    return out, conflicts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--false-ranks", type=int, nargs="+")
    ap.add_argument("--reason", default=DEFAULT_REJECT_REASON, help="shown in the app next to the rejected candidate")
    ap.add_argument("--reviewer", default=os.environ.get("USER", "team"))
    ap.add_argument("--yes", action="store_true", help="skip the confirmation question")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list or not args.false_ranks:
        for label, path in (("Verified", VERIFIED), ("Rejected", REVIEW)):
            print(f"{label} ({path}):")
            print(pd.read_csv(path).to_string(index=False) if os.path.exists(path) else "  nothing yet")
        return

    already = load_false_ids()
    df = pd.read_csv(SCORED, dtype={"detectionId": str})
    df = df[~df["detectionId"].isin(already)]  # rejected rows are not ranked in the app
    df = df.sort_values("score", ascending=False).reset_index(drop=True)
    bad = [r for r in args.false_ranks if r < 1 or r > len(df)]
    if bad:
        sys.exit(f"Ranks out of range (1..{len(df)}): {bad}")
    rows = df.iloc[[r - 1 for r in args.false_ranks]]
    print("Will mark as false detections:")
    for r, (_, row) in zip(args.false_ranks, rows.iterrows()):
        print(f"  rank {r:>3}  score {row['score']:.2f}  {row.get('quadName', '')}  {row['detectionId']}")
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
            w.writerow({"detectionId": row["detectionId"], "reason": args.reason, "reviewer": args.reviewer,
                        "reviewedAt": now, "rankWhenReviewed": r, "quadName": row.get("quadName", ""),
                        "lat": row["lat"], "lon": row["lon"]})
    print(f"Saved to {REVIEW}. Now re-run: briefs.py, load_candidates.py --reset-status, impact.py")


if __name__ == "__main__":
    main()
