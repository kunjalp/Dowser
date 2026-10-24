#!/usr/bin/env python3
"""USB fallback: read the JSON lines the ESP32 prints on serial and POST them to the ingest endpoint.

Use this if the ESP32 cannot reach Wi-Fi at the venue. The laptop does the HTTP instead.

  pip install pyserial requests
  export INGEST_URL=https://healthy-gull-811.convex.site/ingest/reading
  export INGEST_TOKEN=...
  python firmware/serial_bridge.py /dev/cu.usbmodemXXXX      # ls /dev/cu.usb* to find the port
"""
import json
import os
import sys

import requests
import serial


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    url = os.environ["INGEST_URL"]
    token = os.environ["INGEST_TOKEN"]
    with serial.Serial(sys.argv[1], 115200, timeout=2) as port:
        while True:
            line = port.readline().decode("utf-8", "ignore").strip()
            if not line.startswith("{"):
                if line:
                    print(line)  # '# ...' debug lines from the firmware
                continue
            try:
                body = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                r = requests.post(url, json=body, headers={"X-Dowser-Token": token}, timeout=5)
                print(f"{body['value']:>5}  ->  HTTP {r.status_code}  {r.text[:80]}")
            except requests.RequestException as e:
                print(f"post failed: {e}")


if __name__ == "__main__":
    main()
