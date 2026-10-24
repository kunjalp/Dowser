"""Tests for score.py. Run from the repo root: python -m pytest pipeline/test_score.py -q"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from score import DEFAULT_WEIGHTS, score, score_parts, weighted_score  # noqa: E402


def test_weighted_score_matches_convex_formula():
    # Hand-computed with convex/scoring.ts weightedScore and DEFAULT_WEIGHTS {.2,.2,.3,.1,.2}:
    # (0.2*1 + 0.2*0.5 + 0.3*0 + 0.1*1 + 0.2*0) / 1.0 = 0.4
    parts = {"confidence": 1, "undocumented": 0.5, "people": 0, "water": 1, "field": 0}
    assert abs(weighted_score(parts) - 0.4) < 1e-9


def test_weights_are_normalized_and_values_clamped_like_convex():
    parts = {"confidence": 2, "undocumented": -1, "people": 1, "water": 0, "field": 0}
    doubled = {k: v * 2 for k, v in DEFAULT_WEIGHTS.items()}
    assert abs(weighted_score(parts) - weighted_score(parts, doubled)) < 1e-9
    assert abs(weighted_score(parts) - (0.2 * 1 + 0.3 * 1) / 1.0) < 1e-9


def test_closer_to_people_scores_higher():
    near = {"confidence": 0.8, "editionsSeen": "[1947, 1962]", "nearestDocumentedDistM": 400,
            "distToHomeM": 50, "distToSchoolM": 300, "distToWaterM": 900, "buildingsNear250m": 15}
    far = dict(near, distToHomeM=3000, distToSchoolM=5000, buildingsNear250m=0)
    r = score(pd.DataFrame([far, near]))
    assert r.loc[0, "distToHomeM"] == 50  # the near one ranks first


def test_part_edges():
    p = score_parts(pd.Series({"confidence": 1.0, "editionsSeen": "[1947, 1962, 1978]",
                               "nearestDocumentedDistM": 100, "distToHomeM": 0,
                               "distToSchoolM": 0, "distToWaterM": 0, "buildingsNear250m": 40}))
    assert p["confidence"] == 1.0
    assert p["undocumented"] == 0.0      # right at the 100 m cut-off
    assert p["people"] == 1.0
    assert p["water"] == 1.0
    assert p["field"] == 0.0


def test_missing_values_do_not_crash():
    p = score_parts(pd.Series({"confidence": float("nan")}))
    assert all(0 <= v <= 1 for v in p.values())
