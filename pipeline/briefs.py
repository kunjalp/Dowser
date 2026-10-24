#!/usr/bin/env python3
"""
Step: Claude-written briefs for the top candidates.

For each of the top N candidates in pipeline/data/scored.csv, Claude writes an 80-120 word
brief in four parts: summary, why it ranks here, what's uncertain, next step.

Rules (Master Plan section 6), checked in code, not just asked for in the prompt:
  - Claude only sees the candidate's own facts, and may only use numbers that appear in them.
  - An unconfirmed candidate's brief never uses the word "confirmed".
  - 80-120 words in total.
If a brief breaks a rule, Claude gets up to two retries with the problem spelled out. If it still
fails (or the API is down), a plain template brief is used instead, so loading never blocks.

Briefs are cached in pipeline/data/briefs_cache.json and only regenerated when a candidate's
facts change. The result is a "brief" column added to scored.csv, which load_candidates.py sends.

Setup: put ANTHROPIC_API_KEY=sk-ant-... in .env.local at the repo root (never commit it).
Run from the repo root, after score.py and before load_candidates.py:
  python pipeline/briefs.py              # top 50
  python pipeline/briefs.py --top 5      # quick test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re

import pandas as pd

MODEL = os.environ.get("DOWSER_BRIEF_MODEL", "claude-sonnet-5-5")
DATA = os.path.join("pipeline", "data")
CACHE_PATH = os.path.join(DATA, "briefs_cache.json")
MIN_WORDS, MAX_WORDS = 80, 120

SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "why_it_ranks_here": {"type": "string"},
        "whats_uncertain": {"type": "string"},
        "next_step": {"type": "string"},
    },
    "required": ["summary", "why_it_ranks_here", "whats_uncertain", "next_step"],
    "additionalProperties": False,
}
PART_LABELS = [("summary", "Summary"), ("why_it_ranks_here", "Why it ranks here"),
               ("whats_uncertain", "What's uncertain"), ("next_step", "Next step")]

SYSTEM = (
    "You write short field briefs for staff at a state orphaned oil and gas well plugging program. "
    "Each brief is about one CANDIDATE: a well symbol found on a historical USGS topographic map "
    "with no matching record in California's CalGEM well database nearby. It is not a verified "
    "well and nobody has visited it unless the facts say so.\n"
    "Rules:\n"
    "1. Use ONLY the facts given. Do not add places, people, history, emissions or causes.\n"
    "2. Every number you write must appear exactly as written in the facts. Do not compute new "
    "numbers, convert units, round, or estimate.\n"
    "3. Never use the word 'confirmed' unless the facts give a confirmed status. Say 'candidate'.\n"
    "4. Plain, calm English for a busy program manager. No hype, no markdown.\n"
    "5. Four parts with STRICT word budgets, about 100 words in total (hard limit 80 to 120):\n"
    "   summary: 25-30 words. What was found and where.\n"
    "   why_it_ranks_here: 25-30 words. Only the two or three strongest reasons from the score parts.\n"
    "   whats_uncertain: 20-25 words. Honest limits, e.g. a misread symbol or a mislocated record.\n"
    "   next_step: 15-20 words. One concrete field action, such as a site visit with a methane check.\n"
    "Do not list every fact. Leave out coordinates. Count your words before answering."
)


def fmt_m(v) -> str | None:
    """Distance as text: nearest 10 m under 2 km, else km with one decimal."""
    if v is None or pd.isna(v):
        return None
    v = float(v)
    return f"{int(round(v, -1))} m" if v < 2000 else f"{v / 1000:.1f} km"


def editions_list(v) -> list[int]:
    try:
        out = json.loads(v) if isinstance(v, str) else list(v)
        return sorted(int(x) for x in out)
    except Exception:
        return []


def facts_for(row: pd.Series, rank: int, total: int) -> list[str]:
    years = editions_list(row.get("editionsSeen"))
    status = str(row.get("status") or "candidate")
    facts = [
        f"Candidate ID: cand-{row.get('detectionId')}",
        f"Rank: {rank} of {total} candidates by priority score",
        f"Priority score: {round(float(row['score']) * 100)} out of 100",
        f"Status: {status.replace('_', ' ')}",
        f"Location: latitude {float(row['lat']):.5f}, longitude {float(row['lon']):.5f}",
    ]
    if isinstance(row.get("quadName"), str) and row.get("quadName"):
        facts.append(f"USGS map quadrangle: {row['quadName']}")
    if years:
        facts.append(f"Well symbol appears on map editions from: {', '.join(map(str, years))} "
                     f"({len(years)} edition{'s' if len(years) != 1 else ''})")
    src = "hand-labeled by our team" if row.get("source") == "ground_truth" else "found by our detection model"
    facts.append(f"How the symbol was found: {src}")
    if (d := fmt_m(row.get("nearestDocumentedDistM"))):
        facts.append(f"Nearest well in state records (CalGEM): {d} away")
    if (d := fmt_m(row.get("distToHomeM"))):
        facts.append(f"Nearest home or residential area: {d}")
    if (d := fmt_m(row.get("distToSchoolM"))):
        facts.append(f"Nearest school: {d}")
    if (d := fmt_m(row.get("distToWaterM"))):
        facts.append(f"Nearest river, stream, canal or lake: {d}")
    if pd.notna(row.get("buildingsNear250m")):
        facts.append(f"Buildings within 250 m: {int(row['buildingsNear250m'])}")
    parts = {k: row.get(f"part_{k}") for k in ("confidence", "undocumented", "people", "water")}
    labels = {"confidence": "symbol confidence", "undocumented": "distance from any record",
              "people": "closeness to people", "water": "closeness to water"}
    facts.append("Score parts (0 to 100, higher means more urgent): " + "; ".join(
        f"{labels[k]} {round(float(v) * 100)}" for k, v in parts.items() if pd.notna(v)))
    facts.append("Rule used: a symbol counts as a candidate when no state-recorded well is within 100 m")
    return facts


def numbers_in(text: str) -> set[str]:
    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


def problems(brief: dict, facts: list[str], status: str) -> list[str]:
    text = " ".join(brief.get(k, "") for k, _ in PART_LABELS)
    issues = []
    words = len(text.split())
    if words > MAX_WORDS:
        issues.append(f"It has {words} words; cut about {words - 100} words to reach about 100 "
                      f"(must be {MIN_WORDS} to {MAX_WORDS}). Keep each part within its budget.")
    elif words < MIN_WORDS:
        issues.append(f"It has {words} words; add about {100 - words} words to reach about 100 "
                      f"(must be {MIN_WORDS} to {MAX_WORDS}).")
    extra = numbers_in(text) - numbers_in(" ".join(facts))
    if extra:
        issues.append(f"It uses numbers not in the facts: {', '.join(sorted(extra))}.")
    if not status.startswith("confirmed") and re.search(r"\bconfirmed\b", text, re.I):
        issues.append("It uses the word 'confirmed' for an unconfirmed candidate.")
    for k, _ in PART_LABELS:
        if not brief.get(k, "").strip():
            issues.append(f"The '{k}' part is empty.")
    return issues


def render(brief: dict) -> str:
    return "\n".join(f"{label}: {brief[k].strip()}" for k, label in PART_LABELS)


def template_brief(row: pd.Series, facts: list[str]) -> str:
    """Rule-safe fallback built only from the facts."""
    fact = {f.split(":")[0]: f.split(":", 1)[1].strip() for f in facts if ":" in f}
    return "\n".join([
        f"Summary: A well symbol on historical USGS maps at {fact.get('Location', 'the listed location')} "
        f"has no state-recorded well nearby. It is a candidate, not a verified well.",
        f"Why it ranks here: {fact.get('Rank', 'See the ranked list')}. Score parts: "
        f"{fact.get('Score parts (0 to 100, higher means more urgent)', 'see the score breakdown')}.",
        "What's uncertain: The symbol may be misread, or it may match a well whose recorded "
        "location is wrong. Nobody has visited the site yet.",
        "Next step: Send a field crew to check for a wellhead and take a methane reading.",
    ])


def fingerprint(facts: list[str]) -> str:
    return hashlib.sha256((MODEL + "\n" + "\n".join(facts)).encode()).hexdigest()[:16]


def ask_claude(client, facts: list[str], feedback: str | None = None) -> dict:
    msg = "Facts:\n- " + "\n- ".join(facts)
    if feedback:
        msg += f"\n\nYour previous brief broke these rules, fix them: {feedback}"
    resp = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM,
        thinking={"type": "between_tools"},
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": msg}],
    )
    if resp.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"stop_reason={resp.stop_reason}")
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)


def brief_for(client, row: pd.Series, facts: list[str]) -> tuple[str, str]:
    """Returns (brief_text, how) where how is 'claude', 'claude-retry' or 'template'."""
    status = str(row.get("status") or "candidate")
    feedback = None
    for attempt in range(3):
        try:
            b = ask_claude(client, facts, feedback)
        except Exception as e:  # API down, bad key, refusal: never block loading
            print(f"    API problem ({type(e).__name__}: {e}); using template")
            break
        issues = problems(b, facts, status)
        if not issues:
            return render(b), "claude" if attempt == 0 else "claude-retry"
        feedback = " ".join(issues)
        print(f"    retrying: {feedback}")
    return template_brief(row, facts), "template"


def load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(".env.local")
    except ImportError:
        pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=os.path.join(DATA, "scored.csv"))
    ap.add_argument("--top", type=int, default=50)
    args = ap.parse_args()

    load_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("No ANTHROPIC_API_KEY found. Add it to .env.local at the repo root.")
    import anthropic
    client = anthropic.Anthropic()

    df = pd.read_csv(args.input, dtype={"nearestDocumentedId": str, "detectionId": str})
    df = df.sort_values("score", ascending=False).reset_index(drop=True)
    cache = json.load(open(CACHE_PATH)) if os.path.exists(CACHE_PATH) else {}
    if "brief" not in df.columns:
        df["brief"] = None
    df["brief"] = df["brief"].astype(object)

    counts = {"cached": 0, "claude": 0, "claude-retry": 0, "template": 0}
    n = min(args.top, len(df))
    for i in range(n):
        row = df.iloc[i]
        facts = facts_for(row, i + 1, len(df))
        key = f"{row['detectionId']}:{fingerprint(facts)}"
        if key in cache:
            df.at[i, "brief"] = cache[key]
            counts["cached"] += 1
            continue
        print(f"  [{i + 1}/{n}] cand-{row['detectionId']}")
        text, how = brief_for(client, row, facts)
        counts[how] += 1
        df.at[i, "brief"] = text
        if how != "template":
            cache[key] = text
            json.dump(cache, open(CACHE_PATH, "w"), indent=1)

    df.to_csv(args.input, index=False)
    print(f"Briefs for top {n}: {counts}. Saved into {args.input}")
    if n:
        print("\nExample (rank 1):\n" + str(df.at[0, "brief"]))


if __name__ == "__main__":
    main()
