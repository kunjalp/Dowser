"""Tests for briefs.py (no API calls). Run from the repo root: python -m pytest pipeline/test_briefs.py -q"""
import json
import os
import sys
from types import SimpleNamespace

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import briefs  # noqa: E402

ROW = pd.Series({
    "detectionId": "d7", "lat": 35.42, "lon": -119.02, "score": 0.6104, "status": "candidate",
    "editionsSeen": "[1947, 1962]", "quadName": "Oildale", "source": "model",
    "nearestDocumentedDistM": 254.8, "distToHomeM": 0.0, "distToSchoolM": 1434.0,
    "distToWaterM": 907.0, "buildingsNear250m": 12,
    "part_confidence": 0.8067, "part_undocumented": 0.7013, "part_people": 0.9202, "part_water": 0.327,
})
FACTS = briefs.facts_for(ROW, 1, 2)

GOOD = {
    "summary": "A well symbol appears at latitude 35.42000, longitude -119.02000 on the Oildale "
               "quadrangle in editions from 1947 and 1962, with no state-recorded well within 250 m.",
    "why_it_ranks_here": "It ranks 1 of 2 because it sits inside a residential area with 12 "
                         "buildings within 250 m, and its closeness to people part is 92.",
    "whats_uncertain": "This is a candidate only. The symbol could be misread, or a known well "
                       "may have a wrong recorded location, so nobody should treat it as a real well yet.",
    "next_step": "Send a field crew to look for a wellhead at the listed location and take a "
                 "methane reading before any plugging decision is made by program staff.",
}


def test_facts_use_rounded_distances_and_whole_number_scores():
    text = "\n".join(FACTS)
    assert "250 m away" in text and "1430 m" in text and "910 m" in text
    assert "Priority score: 61 out of 100" in text
    assert "1947, 1962" in text


def test_good_brief_passes_all_rules():
    assert briefs.problems(GOOD, FACTS, "candidate") == []


def test_catches_invented_numbers_confirmed_and_length():
    bad = dict(GOOD, next_step="It is confirmed leaking about 3 tons a year.")
    issues = " ".join(briefs.problems(bad, FACTS, "candidate"))
    assert "confirmed" in issues
    assert "3" in issues   # "3 tons" is not in the facts
    short = {k: "Too short." for k in GOOD}
    assert "words" in " ".join(briefs.problems(short, FACTS, "candidate"))


def test_unconfirmed_is_allowed():
    ok = dict(GOOD, whats_uncertain=GOOD["whats_uncertain"].replace("a candidate only", "unconfirmed"))
    assert not any("confirmed" in i for i in briefs.problems(ok, FACTS, "candidate"))


class FakeClient:
    """Returns a rule-breaking brief first, then a good one."""
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0)
        return SimpleNamespace(stop_reason="end_turn",
                               content=[SimpleNamespace(type="text", text=json.dumps(reply))])


def test_retry_then_success_and_request_shape():
    bad = dict(GOOD, next_step="Confirmed leak, plug it now.")
    client = FakeClient([bad, GOOD])
    text, how = briefs.brief_for(client, ROW, FACTS)
    assert how == "claude-retry"
    assert text.startswith("Summary: ")
    req = client.calls[0]
    assert req["output_config"]["format"]["type"] == "json_schema"
    assert "temperature" not in req and "tool_choice" not in req
    assert "broke these rules" in client.calls[1]["messages"][0]["content"]


def test_falls_back_to_template_and_template_follows_rules():
    bad = dict(GOOD, summary="It leaks about 5 tons of methane a year.")
    client = FakeClient([bad, bad, bad])
    text, how = briefs.brief_for(client, ROW, FACTS)
    assert how == "template"
    assert "confirmed" not in text.lower().replace("unconfirmed", "")
    assert briefs.numbers_in(text) <= briefs.numbers_in(" ".join(FACTS))


def test_api_error_uses_template():
    class Broken:
        messages = SimpleNamespace(create=lambda **k: (_ for _ in ()).throw(RuntimeError("401")))
    text, how = briefs.brief_for(Broken(), ROW, FACTS)
    assert how == "template"
