#!/usr/bin/env python3
"""
Impact numbers for the pitch and Devpost, computed from our own data (Master Plan section 7).

  "In our test region, N candidate wells are not in state records,
   and M are within 250 m of homes or a school."

Run from the repo root, after score.py:
  python pipeline/impact.py
Reads pipeline/data/scored.csv (and the CalGEM file for context). Prints the numbers and the
pitch sentence, and writes them to pipeline/data/impact.json.
Wording rule: these are CANDIDATES, never "found wells".
"""
from __future__ import annotations

import argparse
import json
import os

import pandas as pd

RADIUS_M = 250
DATA = os.path.join("pipeline", "data")


def impact(df: pd.DataFrame, radius_m: float = RADIUS_M) -> dict:
    home = pd.to_numeric(df.get("distToHomeM"), errors="coerce")
    school = pd.to_numeric(df.get("distToSchoolM"), errors="coerce")
    near_home = home <= radius_m
    near_school = school <= radius_m
    water = pd.to_numeric(df.get("distToWaterM"), errors="coerce") <= radius_m
    status = df["status"] if "status" in df else pd.Series(["candidate"] * len(df))
    years = set()
    for v in df.get("editionsSeen", pd.Series(dtype=str)).dropna():
        try:
            years.update(int(y) for y in json.loads(v))
        except (ValueError, TypeError):
            pass
    return {
        "candidates": int(len(df)),
        "nearHomeOrSchool": int((near_home | near_school).sum()),
        "nearHome": int(near_home.sum()),
        "nearSchool": int(near_school.sum()),
        "nearWater": int(water.sum()),
        "multiEdition": int(df.get("editionsSeen", pd.Series(dtype=str)).fillna("[]")
                            .map(lambda s: len(json.loads(s)) if s.startswith("[") else 1).gt(1).sum()),
        "confirmedLeaking": int((status == "confirmed_leaking").sum()),
        "mapYears": sorted(years),
        "radiusM": radius_m,
    }


def sentence(n: dict) -> str:
    s = (f"In our test region, {n['candidates']} candidate wells are not in state records, "
         f"and {n['nearHomeOrSchool']} are within {n['radiusM']:.0f} m of homes or a school.")
    if n["mapYears"]:
        s += f" (Maps checked: {n['mapYears'][0]}-{n['mapYears'][-1]} editions.)"
    return s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=os.path.join(DATA, "scored.csv"))
    ap.add_argument("--radius", type=float, default=RADIUS_M)
    args = ap.parse_args()

    df = pd.read_csv(args.input, dtype={"detectionId": str})
    n = impact(df, args.radius)
    wells = os.path.join(DATA, "calgem", "calgem_wells.jsonl")
    if os.path.exists(wells):
        with open(wells) as fh:
            n["documentedWellsChecked"] = sum(1 for _ in fh)
    for k, v in n.items():
        print(f"  {k}: {v}")
    print("\nPitch line:\n  " + sentence(n))
    with open(os.path.join(DATA, "impact.json"), "w") as fh:
        json.dump({**n, "sentence": sentence(n)}, fh, indent=1)
    print(f"\nWrote {os.path.join(DATA, 'impact.json')}")


if __name__ == "__main__":
    main()
