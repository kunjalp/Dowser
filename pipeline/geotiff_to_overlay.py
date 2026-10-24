#!/usr/bin/env python3
"""Turn a USGS TopoView GeoTIFF into a web overlay for the Command Map.

Reprojects the sheet to WGS84 (lat/lon), writes a WebP with transparent margins, and
records the image's four corner coordinates in app/public/historical/manifest.json.
The map's "Historical map overlay" toggle picks the manifest up automatically.

    python pipeline/geotiff_to_overlay.py path/to/sheet.tif --year 1962 --name "Taft"

Options: --max-px 3000 (longest side; smaller = faster page loads), --quality 82 (WebP, lower = smaller file),
        --out app/public/historical
Needs: pip install rasterio numpy pillow
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject

DST_CRS = "EPSG:4326"


def to_rgb(src: rasterio.DatasetReader) -> np.ndarray:
    """Read the sheet as an (3, H, W) uint8 array, expanding palettes and scaling if needed."""
    if src.count == 1:
        band = src.read(1)
        try:
            cmap = src.colormap(1)
            lut = np.zeros((256, 3), dtype=np.uint8)
            for k, v in cmap.items():
                lut[k] = v[:3]
            return np.moveaxis(lut[band], -1, 0)
        except ValueError:
            return np.stack([band, band, band]).astype(np.uint8)
    data = src.read([1, 2, 3])
    if data.dtype != np.uint8:
        hi = float(data.max()) or 1.0
        data = (data.astype(np.float32) / hi * 255).astype(np.uint8)
    return data


def convert(tif: Path, year: int, name: str, out_dir: Path, max_px: int, quality: int = 82) -> dict:
    with rasterio.open(tif) as src:
        if src.crs is None:
            raise SystemExit(f"{tif} has no coordinate system; it is not a georeferenced GeoTIFF.")
        rgb = to_rgb(src)
        valid = src.dataset_mask() > 0  # margins/rotation gaps become transparent
        scale = min(1.0, max_px / max(src.width, src.height))
        tr, w, h = calculate_default_transform(
            src.crs, DST_CRS, src.width, src.height, *src.bounds,
            dst_width=max(1, int(src.width * scale)), dst_height=max(1, int(src.height * scale)),
        )
        out = np.zeros((4, h, w), dtype=np.uint8)
        for i in range(3):
            reproject(
                source=rgb[i], destination=out[i],
                src_transform=src.transform, src_crs=src.crs,
                dst_transform=tr, dst_crs=DST_CRS, resampling=Resampling.bilinear,
            )
        alpha = np.zeros((h, w), dtype=np.uint8)
        reproject(
            source=valid.astype(np.uint8) * 255, destination=alpha,
            src_transform=src.transform, src_crs=src.crs,
            dst_transform=tr, dst_crs=DST_CRS, resampling=Resampling.nearest,
        )
        out[3] = alpha

    left, top = tr * (0, 0)
    right, bottom = tr * (w, h)
    slug = re.sub(r"[^a-z0-9]+", "-", f"{name}-{year}".lower()).strip("-")
    out_dir.mkdir(parents=True, exist_ok=True)
    img_path = out_dir / f"{slug}.webp"
    Image.fromarray(np.moveaxis(out, 0, -1), "RGBA").save(img_path, "WEBP", quality=quality)

    entry = {
        "id": slug,
        "name": name,
        "year": year,
        "url": f"/historical/{slug}.webp",
        # MapLibre order: top-left, top-right, bottom-right, bottom-left, as [lon, lat]
        "corners": [[left, top], [right, top], [right, bottom], [left, bottom]],
    }
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    manifest = [m for m in manifest if m["id"] != slug] + [entry]
    manifest.sort(key=lambda m: (m["year"], m["name"]))
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {img_path} ({w}x{h}, {img_path.stat().st_size/1e6:.1f} MB)")
    print(f"Corners (lon,lat): {entry['corners']}")
    return entry


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tif", type=Path)
    ap.add_argument("--year", type=int, required=True, help="edition year printed on the sheet")
    ap.add_argument("--name", required=True, help="quad name, e.g. Taft")
    ap.add_argument("--max-px", type=int, default=3000)
    ap.add_argument("--quality", type=int, default=82, help="WebP quality 1-100; lower = smaller file")
    ap.add_argument("--out", type=Path, default=Path("app/public/historical"))
    a = ap.parse_args()
    convert(a.tif, a.year, a.name, a.out, a.max_px, a.quality)
