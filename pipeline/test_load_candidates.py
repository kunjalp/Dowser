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


def test_kern_box():
    from load_candidates import in_kern
    assert in_kern(35.2, -119.44)
    assert not in_kern(37.8, -122.4)   # San Francisco


def test_publish_evidence_copies_local_files(tmp_path):
    from load_candidates import publish_evidence
    crop = tmp_path / "d7_1947.png"
    crop.write_bytes(b"png")
    public = tmp_path / "public"
    assert publish_evidence(str(crop), str(public)) == "/evidence/d7_1947.png"
    assert (public / "evidence" / "d7_1947.png").exists()
    assert publish_evidence("/evidence/d7_1947.png", str(public)) == "/evidence/d7_1947.png"
    assert publish_evidence("https://example.org/x.png", str(public)) == "https://example.org/x.png"
    assert publish_evidence(str(tmp_path / "missing.png"), str(public)) is None


def test_brief_is_sent_when_present():
    c = to_candidate(ROW.copy().set_axis(ROW.index).combine_first(pd.Series({"brief": "Summary: hi"})))
    assert c["brief"] == "Summary: hi"
    assert "brief" not in to_candidate(ROW)


def test_review_and_hand_label_are_attached_and_rejected_rows_get_no_brief():
    row = ROW.copy()
    row["brief"], row["handLabeled"] = "Summary: hi", "True"
    rejected = {"verdict": "rejected", "reason": "Not a well", "reviewedBy": "r"}
    c = to_candidate(row, rejected)
    assert c["review"] == rejected and c["handLabeled"] is True
    assert "brief" not in c
    c = to_candidate(row, {"verdict": "verified", "reason": "ok", "reviewedBy": "r"})
    assert c["brief"] == "Summary: hi"
    assert "review" not in to_candidate(ROW) and "handLabeled" not in to_candidate(ROW)


def test_prune_lists_stale_undocumented_rows_and_deletes_only_after_yes(monkeypatch):
    import load_candidates as lc
    calls = []
    in_db = [{"id": "cand-keep", "source": "model", "status": "candidate"},
             {"id": "cand-old", "source": "model", "status": "queued"},
             {"id": "cand-gt", "source": "ground_truth", "status": "candidate"},
             {"id": "idle-1", "source": "calgem_idle", "status": "candidate"}]  # never listed by the backend

    def fake_run(fn, args, prod):
        calls.append((fn, args))
        if fn == "candidates:undocumentedIds":
            return json.dumps(in_db[:3])
        return json.dumps({"deleted": len(args["ids"]), "refused": []})

    monkeypatch.setattr(lc, "convex_run", fake_run)
    assert lc.prune({"cand-keep"}, False, "dev", ask=lambda _: "no") == 0
    assert [c[0] for c in calls] == ["candidates:undocumentedIds"]
    assert lc.prune({"cand-keep"}, False, "dev", ask=lambda _: "yes") == 2
    assert calls[-1] == ("candidates:deleteUndocumented", {"ids": ["cand-old", "cand-gt"]})
