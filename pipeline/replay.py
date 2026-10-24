#!/usr/bin/env python3
"""
Replay fallback: send a "knob turned up" sequence of readings to the sensor endpoint, exactly
as the handheld would, with isReplay=true so the app shows the "simulated" banner.

Use it if the handheld or venue Wi-Fi fails on stage. The phone still pairs the well as usual
(Field View), so readings attach to whichever candidate is open there. Or pass --candidate to
attach them directly.

Default sequence (about 40 s, one reading per second):
  10 s clean (value ~40)  ->  8 s ramp up  ->  12 s HIGH (~1300)  ->  10 s back down
With the backend rule (3 readings >= 1000 within 30 s) this auto-confirms the paired well.

Run from the repo root:
  python pipeline/replay.py --dry-run                      # print the readings, send nothing
  python pipeline/replay.py                                # send to PROD (shared) endpoint
  python pipeline/replay.py --url https://healthy-gull-811.convex.site   # your dev copy
  python pipeline/replay.py --file pipeline/data/murad_recording.csv     # replay a recording
Recording CSV columns: value (required), raw (optional), seconds (optional time offset).

The token comes from --token, or INGEST_TOKEN in .env.local (never commit it).
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import random
import sys
import time

PROD_URL = "https://earnest-otter-112.convex.site"


def default_sequence(seed: int = 7) -> list[dict]:
    rnd = random.Random(seed)
    seq = []
    for i in range(10):                       # clean air
        seq.append(40 + rnd.uniform(-8, 8))
    for i in range(8):                        # walking into the leak
        seq.append(40 + (1300 - 40) * (i + 1) / 8 + rnd.uniform(-30, 30))
    for i in range(12):                       # at the wellhead
        seq.append(1300 + rnd.uniform(-60, 60))
    for i in range(10):                       # walking away
        seq.append(1300 - (1300 - 40) * (i + 1) / 10 + rnd.uniform(-30, 30))
    return [{"seconds": float(i), "value": round(max(0.0, v), 1),
             "raw": int(min(4095, max(0, v / 1500 * 4095)))} for i, v in enumerate(seq)]


def read_recording(path: str) -> list[dict]:
    out = []
    with open(path, newline="") as fh:
        for i, row in enumerate(csv.DictReader(fh)):
            v = float(row["value"])
            out.append({"seconds": float(row.get("seconds") or i), "value": v,
                        "raw": float(row.get("raw") or v)})
    if not out:
        sys.exit(f"No readings in {path}")
    return out


def payload(r: dict, device_id: str, candidate: str | None) -> dict:
    p = {"deviceId": device_id, "value": r["value"], "raw": r["raw"], "isReplay": True}
    if candidate:
        p["candidateId"] = candidate
    return p


def load_token(arg: str | None) -> str:
    if arg:
        return arg
    try:
        from dotenv import load_dotenv
        load_dotenv(".env.local")
    except ImportError:
        pass
    tok = os.environ.get("INGEST_TOKEN")
    if not tok:
        sys.exit("No token. Add INGEST_TOKEN=... to .env.local, or pass --token.")
    return tok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=PROD_URL, help="deployment site URL (.convex.site)")
    ap.add_argument("--token")
    ap.add_argument("--device", default="handheld-1")
    ap.add_argument("--candidate", help="attach to this candidate id instead of the phone's pairing")
    ap.add_argument("--file", help="replay a recorded CSV instead of the built-in sequence")
    ap.add_argument("--speed", type=float, default=1.0, help="2 = twice as fast")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    seq = read_recording(args.file) if args.file else default_sequence()
    if args.dry_run:
        for r in seq:
            print(f"  t={r['seconds']:5.1f}s  value={r['value']:7.1f}  raw={r['raw']}")
        print(f"{len(seq)} readings (dry run, nothing sent)")
        return

    import requests
    token = load_token(args.token)
    endpoint = args.url.rstrip("/") + "/ingest/reading"
    print(f"Replaying {len(seq)} readings to {endpoint} (isReplay=true). Ctrl+C to stop.")
    start = time.time()
    for r in seq:
        wait = start + r["seconds"] / args.speed - time.time()
        if wait > 0:
            time.sleep(wait)
        try:
            resp = requests.post(endpoint, json=payload(r, args.device, args.candidate),
                                 headers={"X-Dowser-Token": token}, timeout=10)
            body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        except Exception as e:
            print(f"  t={r['seconds']:5.1f}s  FAILED: {e}")
            continue
        flag = "  <- auto-confirmed!" if body.get("autoConfirmed") else ""
        print(f"  t={r['seconds']:5.1f}s  value={r['value']:7.1f}  -> {resp.status_code} "
              f"candidate={body.get('candidateId')}{flag}")
        if resp.status_code == 401:
            sys.exit("Unauthorized: the token does not match this deployment's INGEST_TOKEN.")
    print("Done.")


if __name__ == "__main__":
    main()
