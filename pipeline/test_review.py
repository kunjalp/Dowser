"""Tests for review.py. Run: python -m pytest pipeline/test_review.py -q"""
import os, subprocess, sys
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from review import DEFAULT_REJECT_REASON, resolve  # noqa: E402


def test_marked_false_detections_are_kept_and_later_ranks_skip_them(tmp_path):
    root = tmp_path
    (root / "pipeline" / "data").mkdir(parents=True)
    rows = [{"detectionId": f"d{i}", "lat": 35.4, "lon": -119.0, "confidence": 0.8, "editionsSeen": "[1954]",
             "nearestDocumentedDistM": 300 + i * 10, "distToHomeM": 100, "distToSchoolM": 900,
             "distToWaterM": 500, "buildingsNear250m": 5, "quadName": "Oildale"} for i in range(5)]
    pd.DataFrame(rows).to_csv(root / "pipeline/data/enriched.csv", index=False)
    run = lambda *a: subprocess.run([sys.executable, *a], cwd=root, text=True, capture_output=True, check=True)
    run(os.path.join(HERE, "score.py"))
    top = pd.read_csv(root / "pipeline/data/scored.csv").detectionId.tolist()
    run(os.path.join(HERE, "review.py"), "--false-ranks", "1", "3", "--yes")
    marked = pd.read_csv(root / "pipeline/review/false_detections.csv")
    assert set(marked.detectionId) == {top[0], top[2]}
    run(os.path.join(HERE, "score.py"))
    assert len(pd.read_csv(root / "pipeline/data/scored.csv")) == 5  # rejected rows are kept
    # rank 1 now means the best NON-rejected row (top[1])
    run(os.path.join(HERE, "review.py"), "--false-ranks", "1", "--yes")
    marked = pd.read_csv(root / "pipeline/review/false_detections.csv")
    assert list(marked.detectionId) == [top[0], top[2], top[1]]


def test_resolve_rules(tmp_path):
    false_csv, verified_csv = tmp_path / "false.csv", tmp_path / "verified.csv"
    pd.DataFrame([{"detectionId": "m-bad", "reason": "blue circle: water well", "reviewer": "r", "reviewedAt": "2026-10-24T10:48"},
                  {"detectionId": "m-blank", "reason": "", "reviewer": "r", "reviewedAt": ""},
                  {"detectionId": "m-merged", "reason": "note", "reviewer": "r", "reviewedAt": ""}]).to_csv(false_csv, index=False)
    pd.DataFrame([{"detectionId": "m-good", "verdict": "verified", "reason": "Looks right",
                   "reviewer": "ryann", "reviewedAt": "2026-10-24"}]).to_csv(verified_csv, index=False)
    df = pd.DataFrame([
        {"detectionId": "m-good", "source": "model", "handLabeled": "False"},
        {"detectionId": "m-bad", "source": "model", "handLabeled": False},
        {"detectionId": "m-blank", "source": "model", "handLabeled": False},
        {"detectionId": "m-merged", "source": "model", "handLabeled": "True"},  # rejected, but hand-labeled too
        {"detectionId": "gt-1", "source": "ground_truth", "handLabeled": True},  # hand label, no model match
        {"detectionId": "m-new", "source": "model", "handLabeled": False},       # not reviewed
    ])
    reviews, conflicts = resolve(df, str(false_csv), str(verified_csv))
    assert reviews["m-good"] == {"verdict": "verified", "reason": "Looks right", "reviewedBy": "ryann",
                                 "reviewedAt": "2026-10-24"}
    assert reviews["m-bad"] == {"verdict": "rejected", "reason": "blue circle: water well", "reviewedBy": "r",
                                "reviewedAt": "2026-10-24T10:48"}
    assert reviews["m-blank"] == {"verdict": "rejected", "reason": DEFAULT_REJECT_REASON, "reviewedBy": "r"}
    assert reviews["m-merged"]["verdict"] == "verified"
    assert reviews["gt-1"]["verdict"] == "verified"
    assert "m-new" not in reviews
    assert conflicts == ["m-merged"]
