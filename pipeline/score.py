#!/usr/bin/env python3
"""
Step 8: turn enriched candidates into scoreParts and a score.

Each part is a number from 0 to 1 (1 = more urgent). The final score uses the SAME
formula and default weights as convex/scoring.ts (weightedScore), so the website and the
pipeline always agree. If someone changes DEFAULT_WEIGHTS in convex/scoring.ts, change
it here too (tests check the formula, not the values).

  confidence    how sure we are it is a real well symbol:
                60% model confidence + 40% how many map editions show it (3+ editions = full)
  undocumented  how far it is from the nearest state record:
                0 at the 100 m cut-off, rising to 1 at 500 m or more (closer = maybe a mislocated record)
  people        40% nearest home (1 at 0 m, 0 at 1 km) + 30% nearest school (1 at 0 m, 0 at 1.5 km)
                + 30% buildings within 250 m (1 at 20 or more)
  water         nearest river/stream/canal/lake: 1 at 0 m, 0 at 1 km
  field         always 0 here; the backend sets it to 1 when a leak is confirmed in the field

Run from the repo root, after enrich.py:
  python pipeline/score.py
Reads pipeline/data/enriched.csv, writes pipeline/data/scored.csv (sorted, best first).
"""
from __future__ import annotations

import argparse
import os

import pandas as pd

# Mirror of DEFAULT_WEIGHTS in convex/scoring.ts. Placeholders until tuned Saturday.
DEFAULT_WEIGHTS = {"confidence": 0.2, "undocumented": 0.2, "people": 0.3, "water": 0.1, "field": 0.2}
PART_KEYS = ("confidence", "undocumented", "people", "water", "field")

CROSS_CHECK_RADIUS_M = 100   # below this a detection is not a candidate at all
UNDOCUMENTED_FULL_M = 500    # at or beyond this distance, "undocumented" is 1
HOME_ZERO_M = 1000
SCHOOL_ZERO_M = 1500
WATER_ZERO_M = 1000
BUILDINGS_FULL = 20
EDITIONS_FULL = 3


def clamp01(x) -> float:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return 0.0
    if x != x:  # NaN
        return 0.0
    return min(1.0, max(0.0, x))


def weighted_score(parts: dict, weights: dict = DEFAULT_WEIGHTS) -> float:
    """Exact copy of weightedScore() in convex/scoring.ts."""
    total = 0.0
    s = 0.0
    for k in PART_KEYS:
        w = max(0.0, float(weights[k]))
        total += w
        s += w * clamp01(parts.get(k, 0))
    return s / total if total > 0 else 0.0


def closeness(dist_m, zero_at_m: float) -> float:
    """1 when the distance is 0, falling to 0 at zero_at_m. Missing distance counts as far."""
    if dist_m is None or pd.isna(dist_m):
        return 0.0
    return clamp01(1 - float(dist_m) / zero_at_m)


def count_editions(value) -> int:
    """editionsSeen may be a list, or a string like "[1947, 1962]" after a CSV round trip."""
    if isinstance(value, (list, tuple)):
        return len(value)
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 1
    s = str(value).strip("[] ")
    return len([p for p in s.replace(";", ",").split(",") if p.strip()]) or 1


def score_parts(row: pd.Series) -> dict:
    conf = clamp01(row.get("confidence", 1.0))
    editions = count_editions(row.get("editionsSeen"))
    dist_doc = row.get("nearestDocumentedDistM")
    return {
        "confidence": round(0.6 * conf + 0.4 * clamp01(editions / EDITIONS_FULL), 4),
        "undocumented": round(clamp01((float(dist_doc) - CROSS_CHECK_RADIUS_M)
                                      / (UNDOCUMENTED_FULL_M - CROSS_CHECK_RADIUS_M))
                              if pd.notna(dist_doc) else 1.0, 4),
        "people": round(0.4 * closeness(row.get("distToHomeM"), HOME_ZERO_M)
                        + 0.3 * closeness(row.get("distToSchoolM"), SCHOOL_ZERO_M)
                        + 0.3 * clamp01((row.get("buildingsNear250m") or 0) / BUILDINGS_FULL), 4),
        "water": round(closeness(row.get("distToWaterM"), WATER_ZERO_M), 4),
        "field": 0.0,
    }


def score(df: pd.DataFrame, weights: dict = DEFAULT_WEIGHTS) -> pd.DataFrame:
    out = df.reset_index(drop=True).copy()
    parts = [score_parts(r) for _, r in out.iterrows()]
    out["scoreParts"] = parts
    for k in PART_KEYS:
        out[f"part_{k}"] = [p[k] for p in parts]
    out["score"] = [round(weighted_score(p, weights), 4) for p in parts]
    return out.sort_values("score", ascending=False).reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=os.path.join("pipeline", "data", "enriched.csv"))
    ap.add_argument("--out", default=os.path.join("pipeline", "data", "scored.csv"))
    args = ap.parse_args()

    df = pd.read_csv(args.input, dtype={"nearestDocumentedId": str, "detectionId": str})
    result = score(df)
    result.drop(columns=["scoreParts"]).to_csv(args.out, index=False)
    print(f"Scored {len(result)} candidates. Top 5:")
    cols = [c for c in ("detectionId", "score", "part_confidence", "part_undocumented",
                        "part_people", "part_water") if c in result.columns]
    print(result[cols].head(5).to_string(index=False))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
