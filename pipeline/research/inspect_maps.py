#!/usr/bin/env python3
"""Download a bounded research sample and inspect GeoTIFFs (FR-1.1/FR-1.2).

Needs catalog caches from region_sources.py and optional rasterio/Pillow/pyproj.
Original binary files and generated views stay under ignored data/research/.
This does not label symbols or measure detector accuracy.
"""

import concurrent.futures
import argparse
import hashlib
import json
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "research"
# Explicit source IDs avoid choosing an arbitrary same-title reprint.
SAMPLE_IDS = {
    "oil_center_1954_reference": "5a8a3276e4b00f54eb3d5471",
    "oil_center_1954": "5a8a3276e4b00f54eb3d546b",
    "oildale_1954": "5a8a3277e4b00f54eb3d5491",
    # Deliberately retained as a rejected orthophoto comparator; not a default input.
    "oil_center_1978": "5a8a3277e4b00f54eb3d548a",
    "oil_center_1992": "5a8a3276e4b00f54eb3d5456",
    "rosedale_1954": "5a8a33e4e4b00f54eb3d818a",
    "taft_1950": "5a8a3558e4b00f54eb3db27c",
    "inglewood_1950": "5a8a2f45e4b00f54eb3d0722",
    "long_beach_1949": "5a8a30a0e4b00f54eb3d29b3",
}


def inspect(sample):
    """Preserve native raster/CRS, inspect its collar, and record source dates."""
    import rasterio
    from PIL import Image
    from rasterio.enums import Resampling

    label, item = sample
    target = CACHE / "maps" / (label + ".tif")
    target.parent.mkdir(parents=True, exist_ok=True)
    url = item["urls"]["GeoTIFF"]
    if not target.exists():
        # A partial download is never mistaken for a complete research artifact.
        partial = target.with_suffix(".part")
        with urllib.request.urlopen(url, timeout=90) as response, partial.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        partial.rename(target)
    with rasterio.open(target) as src:
        preview = src.read([1, 2, 3], out_shape=(3, 1600, round(src.width * 1600 / src.height)),
                           resampling=Resampling.bilinear)
        preview_path = target.with_suffix(".jpg")
        Image.fromarray(preview.transpose(1, 2, 0)).save(preview_path, quality=92)
        result = {
            "sample": label, "source_id": item["sourceId"], "title": item["title"],
            "source_url": url, "metadata_url": item["vendorMetaUrl"],
            "catalog_bounds_wgs84": item["boundingBox"],
            "bytes": target.stat().st_size,
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "width": src.width, "height": src.height, "bands": src.count,
            "crs": src.crs.to_string(), "crs_wkt": src.crs.to_wkt(),
            "transform_rasterio": list(src.transform)[:6],
            "pixel_size": list(src.res), "nodata": src.nodata,
            "overview_factors": src.overviews(1),
            "preview_path": str(preview_path.relative_to(ROOT)),
        }
        collar = src.read([1, 2, 3], window=rasterio.windows.Window(
            0, src.height - 950, src.width, 950)).transpose(1, 2, 0)
        collar_image = Image.fromarray(collar)
        collar_image.thumbnail((1800, 600))
        collar_image.save(target.with_name(label + "_collar.png"))
    xml_path = target.with_suffix(".xml")
    if not xml_path.exists():
        with urllib.request.urlopen(item["vendorMetaUrl"], timeout=45) as response:
            xml_path.write_bytes(response.read())
    root = ET.fromstring(xml_path.read_bytes())
    result["historical_metadata"] = {
        desc.text: date.text for desc, date in zip(
            root.findall(".//procdesc"), root.findall(".//procdate"))
        if date.text and date.text.isdigit() and int(date.text) < 2000
    }
    (CACHE / (label + "_inspection.json")).write_text(json.dumps(result, indent=2))
    return {k: result[k] for k in ["sample", "bytes", "width", "height", "crs", "pixel_size"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", choices=list(SAMPLE_IDS), action="append")
    parser.add_argument("--all", action="store_true", help="download/inspect all comparison samples")
    args = parser.parse_args()
    items = {}
    for path in CACHE.glob("usgs_*.json"):
        for item in json.loads(path.read_text())["response"]["items"]:
            items[item["sourceId"]] = item
    chosen = list(SAMPLE_IDS) if args.all else (args.sample or [
        "oil_center_1954_reference", "oildale_1954", "oil_center_1992"])
    samples = [(label, items[SAMPLE_IDS[label]]) for label in chosen]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(inspect, samples):
            print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
