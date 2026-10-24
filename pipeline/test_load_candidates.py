"""Tests for load_candidates.py. Run from the repo root: python -m pytest pipeline/test_load_candidates.py -q"""
import json
import math
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from load_candidates import to_candidate  # noqa: E402

ROW = pd.Series({
    "lat": 35.2, "lon": -119.44, "detectionId": "d7", "score": 0.4123456,
    "editionsSeen": "[1962, 1947]", "evidence": json.dumps([{"year": 1947, "url": "/evidence/d7.png"}]),
    "quadName": "Taft", "source": "ground_truth",
    "nearestDocumentedId": "0402937214", "nearestDocumentedDistM": 254.83,
    "distToHomeM": 120.0, "distToSchoolM": float("nan"), "distToWaterM": 900.0, "buildingsNear250m": 3.0,
    "part_confidence": 0.8, "part_undocumented": 0.39, "part_people": 0.5, "part_water": 0.1, "part_field": 0.0,
})

REQUIRED = {"id", "lat", "lon", "score", "scoreParts", "editionsSeen", "status", "evidenceImages", "quadName"}


def test_has_every_required_field_in_the_agreed_format():
    c = to_candidate(ROW)
    assert REQUIRED <= set(c)
    assert c["id"] == "cand-d7"
    assert c["status"] == "candidate"
    assert c["editionsSeen"] == [1947, 1962]          # list of years, sorted
    assert c["evidenceImages"] == [{"year": 1947, "url": "/evidence/d7.png"}]
    assert set(c["scoreParts"]) == {"confidence", "undocumented", "people", "water", "field"}
    assert c["source"] == "ground_truth"


def test_keeps_leading_zero_and_drops_blanks():
    c = to_candidate(ROW)
    assert c["nearestDocumentedId"] == "0402937214"
    assert "distToSchoolM" not in c                   # NaN is left out, Convex rejects NaN
    assert c["buildingsNear250m"] == 3 and isinstance(c["buildingsNear250m"], int)


def test_output_is_valid_json_with_no_nan():
    text = json.dumps(to_candidate(ROW))
    assert "NaN" not in text
    assert not any(isinstance(v, float) and math.isnan(v) for v in json.loads(text).values())


def test_missing_optional_inputs_still_produce_a_valid_record():
    bare = pd.Series({"lat": 35.0, "lon": -119.0, "score": 0.1, "detectionId": "x"})
    c = to_candidate(bare)
    assert REQUIRED <= set(c)
    assert c["editionsSeen"] == [] and c["evidenceImages"] == []
    assert c["source"] == "model"
