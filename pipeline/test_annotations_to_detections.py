import json
import pytest
from pyproj import CRS
from PIL import Image

from pipeline.annotations_to_detections import convert, parse_yolo


def test_parse_yolo_pixels_and_clipping():
    b = parse_yolo("0 0.5 0.5 0.1 0.2\n\n0 0.01 0.5 0.1 0.1\n", 1000, 1000)
    assert b[0]["x"] == pytest.approx(450) and b[0]["h"] == pytest.approx(200)
    assert b[1]["x"] == 0 and b[1]["w"] == pytest.approx(60)  # clipped at the edge


def test_parse_yolo_rejects_bad_rows():
    with pytest.raises(ValueError):
        parse_yolo("1 0.5 0.5 0.1 0.1", 100, 100)
    with pytest.raises(ValueError):
        parse_yolo("0 0.5 0.5", 100, 100)


def test_convert_makes_rows_and_crops(tmp_path):
    tile = {"tileId": "t1", "sheetName": "Oildale", "mapYear": 1954, "widthPx": 1024, "heightPx": 1024,
            "transform": [1, 0, 1900000, 0, -1, 600000], "crs": CRS.from_epsg(26743).to_wkt()}
    labels = tmp_path / "labels" / "train"; labels.mkdir(parents=True)
    (labels / "t1.txt").write_text("0 0.5 0.5 0.04 0.04\n0 0.1 0.9 0.04 0.04\n")
    images = tmp_path / "images"; images.mkdir()
    Image.new("RGB", (1024, 1024), "white").save(images / "t1.png")
    rows, skipped = convert({"t1": tile}, [str(tmp_path / "labels")], str(images), str(tmp_path / "crops"), False)
    assert not skipped and len(rows) == 2
    r = rows[0]
    assert r["source"] == "ground_truth" and r["confidence"] == 1.0 and r["year"] == 1954
    assert 34 < r["lat"] < 40 and -125 < r["lon"] < -114
    assert (tmp_path / "crops" / "gt_t1_001.png").exists()
    assert Image.open(r["crop"]).size == (160, 160)


def test_assistant_labels_skipped_unless_allowed(tmp_path):
    tile = {"tileId": "t1", "sheetName": "x", "mapYear": 1954, "widthPx": 1024, "heightPx": 1024,
            "transform": [1, 0, 1900000, 0, -1, 600000], "crs": CRS.from_epsg(26743).to_wkt()}
    d = tmp_path / "a"; d.mkdir(); (d / "t1.txt").write_text("0 0.5 0.5 0.04 0.04\n")
    assert convert({"t1": tile}, [f"{d}:assistant"], None, None, False)[0] == []
    assert len(convert({"t1": tile}, [f"{d}:assistant"], None, None, True)[0]) == 1
