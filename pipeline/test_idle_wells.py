"""Tests for idle_wells.py. Run from the repo root: python -m pytest pipeline/test_idle_wells.py -q"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from idle_wells import near_people, quad_names, select_idle, to_idle_candidate  # noqa: E402
from score import weighted_score  # noqa: E402

ROW = pd.Series({
    "apiNumber": "0402912345", "status": "Idle", "locationQuality": "good",
    "operator": "Example Oil Co.", "lat": 35.41, "lon": -119.05,
    "distToHomeM": 120.0, "distToSchoolM": float("nan"), "distToWaterM": 900.0, "buildingsNear250m": 7.0,
})

REQUIRED = {"id", "lat", "lon", "score", "scoreParts", "editionsSeen", "status", "evidenceImages", "quadName"}


def test_selects_only_good_idle_wells_inside_the_box():
    wells = pd.DataFrame([
        dict(ROW),
        dict(ROW, apiNumber="1", status="Active"),
        dict(ROW, apiNumber="2", status="Plugged"),
        dict(ROW, apiNumber="3", locationQuality="uncertain"),
        dict(ROW, apiNumber="4", lon=-120.5),  # west of the OSM study box
    ])
    assert select_idle(wells)["apiNumber"].tolist() == ["0402912345"]


def test_keeps_wells_near_a_home_or_a_school():
    df = pd.DataFrame([
        {"apiNumber": "home", "distToHomeM": 200, "distToSchoolM": 900},
        {"apiNumber": "school", "distToHomeM": 900, "distToSchoolM": 250},
        {"apiNumber": "far", "distToHomeM": 251, "distToSchoolM": float("nan")},
    ])
    assert near_people(df)["apiNumber"].tolist() == ["home", "school"]


def test_record_is_the_candidate_format_with_the_idle_extras():
    c = to_idle_candidate(ROW)
    assert REQUIRED <= set(c)
    assert c["id"] == "idle-0402912345"                # leading zero kept
    assert c["source"] == "calgem_idle"
    assert c["status"] == "candidate"
    assert c["evidenceImages"] == [] and c["editionsSeen"] == []
    assert (c["wellStatus"], c["operator"], c["apiNumber"]) == ("Idle", "Example Oil Co.", "0402912345")
    assert "nearestDocumentedDistM" not in c and "detectionId" not in c
    assert "distToSchoolM" not in c                   # NaN is left out, Convex rejects NaN
    assert c["buildingsNear250m"] == 7 and isinstance(c["buildingsNear250m"], int)


def test_scored_as_known_well_not_in_records_gap():
    c = to_idle_candidate(ROW)
    assert c["scoreParts"]["undocumented"] == 0
    assert c["scoreParts"]["confidence"] == 1.0
    assert c["scoreParts"]["field"] == 0
    assert c["scoreParts"]["people"] > 0
    assert abs(c["score"] - weighted_score(c["scoreParts"])) < 1e-4


def test_quad_name_comes_from_the_grid_cell_of_known_sheets():
    det = pd.DataFrame([
        {"lat": 35.45, "lon": -119.06, "quadName": "Oildale"},
        {"lat": 35.40, "lon": -119.10, "quadName": "Oildale"},
        {"lat": 35.40, "lon": -119.0006, "quadName": "Oil Center"},  # sheet collar spills over
        {"lat": 35.42, "lon": -118.95, "quadName": "Oil Center"},
    ])
    names = quad_names(det)
    assert to_idle_candidate(ROW, names)["quadName"] == "Oildale"
    assert to_idle_candidate(pd.Series(dict(ROW, lon=-118.9)), names)["quadName"] == "Oil Center"
    assert to_idle_candidate(pd.Series(dict(ROW, lat=35.1)), names)["quadName"] == "Kern County"
