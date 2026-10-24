#!/usr/bin/env python3
"""
Step 4: load scored candidates into Convex (candidates:upsertBatch).

Converts each row of pipeline/data/scored.csv into the agreed candidate record
(README "Data contracts") and sends them in batches. Candidate ids are "cand-<detectionId>",
so re-running updates the same candidates instead of duplicating them.

Run from the repo root, after score.py:
  python pipeline/load_candidates.py --dry-run     # only writes pipeline/data/candidates.json, sends nothing
  python pipeline/load_candidates.py               # loads into YOUR dev deployment (safe test)
  python pipeline/load_candidates.py --prod        # loads into the SHARED deployment the team sees

Before sending it checks: inside the Kern box, scores 0..1, unique ids, and that every
evidence image exists. Local crop images are copied into app/public/evidence/ and their
URLs become /evidence/<file>.png, so commit that folder for the website to show them.

Warning: re-loading a candidate overwrites it, including its status. Do not re-run with --prod
after the field check has changed statuses unless you mean to reset them.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys

import pandas as pd

PART_KEYS = ("confidence", "undocumented", "people", "water", "field")
BATCH_SIZE = 50
# Kern study box (minLon, minLat, maxLon, maxLat); anything outside is a bad coordinate.
KERN_BOX = (-120.19, 34.79, -117.63, 35.80)
PUBLIC_DIR = os.path.join("app", "public")   # Next.js serves files here at the site root
EVIDENCE_SUBDIR = "evidence"


def in_kern(lat, lon) -> bool:
    return KERN_BOX[0] <= lon <= KERN_BOX[2] and KERN_BOX[1] <= lat <= KERN_BOX[3]


def publish_evidence(url: str, public_dir: str = PUBLIC_DIR):
    """Return a URL the website can serve, or None if the crop cannot be published.
    - http(s) URLs are kept as they are.
    - paths already under the site (e.g. /evidence/x.png) are kept if the file exists in public/.
    - local files are copied into public/evidence/ and become /evidence/<name>.
    """
    if url.startswith(("http://", "https://")):
        return url
    if url.startswith("/") and os.path.exists(os.path.join(public_dir, url.lstrip("/"))):
        return url
    if os.path.isfile(url):
        dest_dir = os.path.join(public_dir, EVIDENCE_SUBDIR)
        os.makedirs(dest_dir, exist_ok=True)
        name = os.path.basename(url)
        dest = os.path.join(dest_dir, name)
        if not os.path.exists(dest):
            shutil.copyfile(url, dest)
        return f"/{EVIDENCE_SUBDIR}/{name}"
    return None


def _num(v):
    """A finite float, or None for blanks/NaN (Convex rejects NaN)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _str(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    s = str(v).strip()
    return s or None


def _json_list(v):
    s = _str(v)
    if not s:
        return []
    try:
        out = json.loads(s)
        return out if isinstance(out, list) else []
    except json.JSONDecodeError:
        return [int(p) for p in s.strip("[]").split(",") if p.strip().isdigit()]


def to_candidate(row: pd.Series) -> dict:
    """One scored.csv row -> one candidate record in the agreed format."""
    det_id = _str(row.get("detectionId")) or f"row{row.name}"
    years = sorted({int(y) for y in _json_list(row.get("editionsSeen"))})
    evidence = [{"year": int(e["year"]), "url": str(e["url"])}
                for e in _json_list(row.get("evidence")) if isinstance(e, dict) and "url" in e]
    source = _str(row.get("source"))
    doc = {
        "id": f"cand-{det_id}",
        "lat": round(float(row["lat"]), 6),
        "lon": round(float(row["lon"]), 6),
        "score": round(float(row["score"]), 4),
        "scoreParts": {k: round(_num(row.get(f"part_{k}")) or 0.0, 4) for k in PART_KEYS},
        "editionsSeen": years,
        "status": "candidate",
        "evidenceImages": evidence,
        "quadName": _str(row.get("quadName")) or "Kern County",
        "detectionId": det_id,
        "source": source if source in ("model", "ground_truth") else "model",
    }
    if _str(row.get("brief")):
        doc["brief"] = _str(row.get("brief"))
    optional = {
        "nearestDocumentedId": _str(row.get("nearestDocumentedId")),
        "nearestDocumentedDistM": _num(row.get("nearestDocumentedDistM")),
        "distToHomeM": _num(row.get("distToHomeM")),
        "distToSchoolM": _num(row.get("distToSchoolM")),
        "distToWaterM": _num(row.get("distToWaterM")),
        "buildingsNear250m": _num(row.get("buildingsNear250m")),
    }
    for k, v in optional.items():
        if v is not None:
            doc[k] = int(v) if k == "buildingsNear250m" else (round(v, 1) if isinstance(v, float) else v)
    return doc


def send(batch: list[dict], prod: bool) -> str:
    npx = shutil.which("npx")
    if not npx:
        sys.exit("Could not find npx. Run this from the repo root in the zsh terminal.")
    cmd = [npx, "convex", "run"]
    if prod:
        cmd.append("--prod")
    cmd += ["candidates:upsertBatch", json.dumps({"candidates": batch})]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"Convex rejected a batch:\n{r.stderr or r.stdout}")
    return r.stdout.strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=os.path.join("pipeline", "data", "scored.csv"))
    ap.add_argument("--json-out", default=os.path.join("pipeline", "data", "candidates.json"))
    ap.add_argument("--prod", action="store_true", help="load into the shared production deployment")
    ap.add_argument("--dry-run", action="store_true", help="write the JSON file only, send nothing")
    ap.add_argument("--limit", type=int, help="only load the top N by score")
    ap.add_argument("--public-dir", default=PUBLIC_DIR, help="the website's public folder")
    args = ap.parse_args()

    df = pd.read_csv(args.input, dtype={"nearestDocumentedId": str, "detectionId": str})
    df = df.sort_values("score", ascending=False)

    # Checks before anything is sent: Kern box, score range, unique ids, publishable evidence.
    inside = [in_kern(float(r["lat"]), float(r["lon"])) for _, r in df.iterrows()]
    if not all(inside):
        print(f"Skipping {inside.count(False)} rows outside the Kern box {KERN_BOX}")
        df = df[inside]
    if args.limit:
        df = df.head(args.limit)
    candidates = [to_candidate(r) for _, r in df.iterrows()]
    bad_scores = [c["id"] for c in candidates if not 0 <= c["score"] <= 1]
    if bad_scores:
        sys.exit(f"Scores outside 0..1: {bad_scores[:5]}")
    ids = [c["id"] for c in candidates]
    if len(ids) != len(set(ids)):
        sys.exit("Duplicate candidate ids; check that detectionIds are unique.")
    dropped = 0
    for c in candidates:
        kept = []
        for e in c["evidenceImages"]:
            url = publish_evidence(e["url"], args.public_dir)
            if url:
                kept.append({"year": e["year"], "url": url})
            else:
                dropped += 1
        c["evidenceImages"] = kept
    if dropped:
        print(f"Warning: {dropped} evidence images were not found and were left out.")
    n_img = sum(len(c["evidenceImages"]) for c in candidates)
    print(f"Evidence images ready: {n_img} (copied into {os.path.join(args.public_dir, EVIDENCE_SUBDIR)})")
    with open(args.json_out, "w") as fh:
        json.dump(candidates, fh, indent=1)
    jsonl = os.path.splitext(args.json_out)[0] + ".jsonl"
    with open(jsonl, "w") as fh:   # for: npx convex import --table candidates --replace
        for c in candidates:
            fh.write(json.dumps(c) + "\n")
    print(f"Prepared {len(candidates)} candidates -> {args.json_out}")
    if args.dry_run:
        return

    target = "PROD (shared)" if args.prod else "your dev deployment"
    for i in range(0, len(candidates), BATCH_SIZE):
        out = send(candidates[i:i + BATCH_SIZE], args.prod)
        print(f"  batch {i // BATCH_SIZE + 1}: {out}")
    print(f"Loaded {len(candidates)} candidates into {target}.")


if __name__ == "__main__":
    main()
