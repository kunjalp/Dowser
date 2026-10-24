"""Download only the selected public USGS sources and pinned free PROJ grid.

Separate acquisition from offline tiling. Existing mismatched files are retained
and reported; nothing is silently replaced. No paid API/account is involved.
"""

import hashlib
import json
import urllib.request
from pathlib import Path

from pipeline.prepare_dataset import ROOT, SOURCE_FILES


def download(url, target, expected_sha=None):
    """Download via a temporary sibling, verify identity, then publish locally."""
    if target.exists():
        if expected_sha and hashlib.sha256(target.read_bytes()).hexdigest() != expected_sha:
            raise ValueError(f"Existing file has wrong checksum; retained: {target}")
        return
    target.parent.mkdir(parents=True,exist_ok=True)
    partial = target.with_suffix(target.suffix+".part")
    with urllib.request.urlopen(url,timeout=60) as response, partial.open("wb") as output:
        while chunk := response.read(1024*1024):
            output.write(chunk)
    if expected_sha and hashlib.sha256(partial.read_bytes()).hexdigest() != expected_sha:
        raise ValueError(f"Downloaded file has wrong checksum; inspect {partial}")
    partial.rename(target)


def main():
    region = json.loads((ROOT/"pipeline/config/region.json").read_text())
    config = json.loads((ROOT/"pipeline/config/dataset.json").read_text())
    for spec in region["maps"]:
        target = ROOT/"data/research/maps"/(SOURCE_FILES[spec["map_id"]]+".tif")
        download(spec["geotiff_url"],target,spec["sha256"])
        download(spec["metadata_url"],target.with_suffix(".xml"))
        print("Ready:",spec["map_id"])
    grid = config["coordinate_grid"]
    download(grid["url"],ROOT/grid["local_path"],grid["sha256"])
    print("Ready: pinned public NADCON grid")


if __name__ == "__main__":
    main()
