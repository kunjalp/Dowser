"""Run: python3 scripts/test_load_calgem.py   (plain asserts, no pytest needed)"""
import csv
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from load_calgem import normalize  # noqa: E402


def test_clean_row():
    doc, why = normalize({"API": 3708211, "Latitude": 34.05123, "Longitude": -118.24567,
                          "WellStatus": "Idle", "OperatorName": "Acme"}, None, 8)
    assert why is None
    assert doc["apiNumber"] == "03708211"  # leading zero restored
    assert doc["locationQuality"] == "good" and doc["lat"] == 34.05123


def test_bad_coordinates_are_flagged_not_dropped():
    for lat, lon, expect in [(0, 0, "zero"), (None, None, "missing"), (34.0, 118.2, "outside California"),
                             (34.1, -118.2, "low-precision")]:
        doc, why = normalize({"API": 1, "Latitude": lat, "Longitude": lon}, None, 8)
        assert doc is not None and expect in why, (lat, lon, why)
        assert doc["locationQuality"] == "uncertain" and "lat" not in doc


def test_geometry_fallback():
    doc, why = normalize({"API": 5}, {"x": -119.5123, "y": 35.3456}, 8)
    assert why is None and doc["lon"] == -119.5123


def test_missing_api_is_dropped():
    assert normalize({"Latitude": 34.1234, "Longitude": -118.1234}, None, 8)[0] is None


def test_end_to_end_csv():
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "in.csv")
        with open(src, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["api", "latitude", "longitude", "wellstatus"])
            w.writerow([3708211, 34.05123, -118.24567, "Idle"])      # in LA basin
            w.writerow([3708211, 34.05123, -118.24567, "Idle"])      # duplicate
            w.writerow([2900001, 35.40123, -119.01234, "Plugged"])    # Kern, outside LA bbox
            w.writerow([3700002, 0, 0, "Unknown"])                    # uncertain
            w.writerow(["", 34.05123, -118.24567, "x"])               # no api
        out = os.path.join(d, "out")
        r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "load_calgem.py"),
                            "--csv", src, "--region", "la_basin", "--out", out],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        rows = [json.loads(l) for l in open(os.path.join(out, "calgem_wells.jsonl"))]
        assert [x["apiNumber"] for x in rows] == ["03708211", "03700002"], rows
        assert "Rows written: 2" in r.stdout and "uncertain location: 1" in r.stdout
        gj = json.load(open(os.path.join(out, "calgem_wells.geojson")))
        assert len(gj["features"]) == 1


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
