"""Tests for impact.py and replay.py. Run from the repo root: python -m pytest pipeline/test_impact_replay.py -q"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from impact import impact, sentence  # noqa: E402
from replay import default_sequence, payload, read_recording  # noqa: E402


def test_impact_counts():
    df = pd.DataFrame({
        "distToHomeM": [100, 900, 3000], "distToSchoolM": [5000, 200, 4000],
        "distToWaterM": [50, 900, 900], "editionsSeen": ["[1947, 1962]", "[1954]", "[1978]"],
    })
    n = impact(df)
    assert n["candidates"] == 3 and n["nearHomeOrSchool"] == 2
    assert n["nearHome"] == 1 and n["nearSchool"] == 1 and n["nearWater"] == 1
    assert n["multiEdition"] == 1 and n["mapYears"] == [1947, 1954, 1962, 1978]
    s = sentence(n)
    assert "3 candidate wells" in s and "2 are within 250 m" in s and "1947-1978" in s


def test_default_sequence_triggers_auto_confirm_rule():
    seq = default_sequence()
    # backend rule: 3 readings >= 1000 within 30 s
    hot = [r["seconds"] for r in seq if r["value"] >= 1000]
    assert len(hot) >= 3 and hot[2] - hot[0] <= 30
    assert seq[0]["value"] < 100            # starts clean
    assert all(0 <= r["raw"] <= 4095 for r in seq)


def test_payload_is_marked_replay():
    p = payload({"value": 12.0, "raw": 33}, "handheld-1", None)
    assert p == {"deviceId": "handheld-1", "value": 12.0, "raw": 33, "isReplay": True}
    assert payload({"value": 1, "raw": 1}, "h", "cand-x")["candidateId"] == "cand-x"


def test_read_recording(tmp_path):
    f = tmp_path / "rec.csv"
    f.write_text("value,raw\n10,100\n1200,3300\n")
    r = read_recording(str(f))
    assert [x["value"] for x in r] == [10, 1200] and r[1]["seconds"] == 1
