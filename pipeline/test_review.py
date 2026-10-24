"""Tests for review.py + the score.py filter. Run: python -m pytest pipeline/test_review.py -q"""
import os, subprocess, sys
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))


def test_marked_false_detections_are_left_out(tmp_path):
    root = tmp_path
    (root / "pipeline" / "data").mkdir(parents=True)
    rows = [{"detectionId": f"d{i}", "lat": 35.4, "lon": -119.0, "confidence": 0.8, "editionsSeen": "[1954]",
             "nearestDocumentedDistM": 300 + i * 10, "distToHomeM": 100, "distToSchoolM": 900,
             "distToWaterM": 500, "buildingsNear250m": 5, "quadName": "Oildale"} for i in range(5)]
    pd.DataFrame(rows).to_csv(root / "pipeline/data/enriched.csv", index=False)
    run = lambda *a, inp=None: subprocess.run([sys.executable, *a], cwd=root, input=inp, text=True,
                                              capture_output=True, check=True)
    run(os.path.join(HERE, "score.py"))
    top = pd.read_csv(root / "pipeline/data/scored.csv").detectionId.tolist()
    run(os.path.join(HERE, "review.py"), "--false-ranks", "1", "3", "--yes")
    marked = pd.read_csv(root / "pipeline/review/false_detections.csv")
    assert set(marked.detectionId) == {top[0], top[2]}
    out = run(os.path.join(HERE, "score.py")).stdout
    assert "Leaving out 2" in out
    after = pd.read_csv(root / "pipeline/data/scored.csv").detectionId.tolist()
    assert top[0] not in after and top[2] not in after and len(after) == 3
