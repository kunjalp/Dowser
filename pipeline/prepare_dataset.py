"""Prepare local, unlabeled map tiles and an auditable spatial split.

Run from repository root: .venv/bin/python -m pipeline.prepare_dataset
No cloud service, model inference, or training is invoked. Existing output is
never overwritten. Raw maps must already be downloaded and match their hashes.
"""

import argparse
import hashlib
import json
import math
import platform
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pyproj
import rasterio
from PIL import Image
from rasterio.features import geometry_mask
from rasterio.windows import Window

from pipeline.geo import neatline_polygon, projected_tile_bounds, transformer


ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = {
    "usgs_293661": "oil_center_1954_reference",
    "usgs_293664": "oildale_1954",
    "usgs_102321": "oil_center_1992",
}


def spatial_split(tiles, test_fraction=.2, min_test=30, val_fraction=.1, min_val=10):
    """Choose fixed north/test, south/validation bands before looking at labels.

    A tile crossing either geographic boundary is quarantined as buffer. Every
    era uses the same EPSG:3310 boundaries, so cross-year overlaps cannot leak.
    Fractions apply to retained tiles; buffer tiles never enter training.
    """
    if not tiles:
        raise ValueError("No tiles to split")
    extents = np.array([t["split_bounds_m"] for t in tiles])
    years = {t["mapYear"] for t in tiles}
    best = None
    for north in sorted(set(extents[:, 1])):
        test = extents[:, 1] >= north
        lower = extents[:, 3] < north
        if test.sum() < min_test:
            continue
        for south in sorted(set(extents[lower, 3])):
            val = lower & (extents[:, 3] <= south)
            train = lower & (extents[:, 1] > south)
            active = int(test.sum() + val.sum() + train.sum())
            if val.sum() < min_val or train.sum() < max(1, .5*active):
                continue
            # Keep both date-on-map eras represented in each retained partition.
            if any({t["mapYear"] for t, keep in zip(tiles, mask) if keep} != years
                   for mask in [train, val, test]):
                continue
            loss = abs(test.sum()/active-test_fraction) + abs(val.sum()/active-val_fraction)
            score = (loss, len(tiles)-active, float(north), float(south))
            if best is None or score < best[0]:
                best = (score, train, val, test)
    if best is None:
        raise ValueError("Insufficient spatially independent tiles for the requested holdouts")
    score, train, val, test = best
    result = {}
    for index, tile in enumerate(tiles):
        result[tile["tileId"]] = ("train" if train[index] else "val" if val[index]
                                  else "test" if test[index] else "buffer")
    return result, {"projection": "EPSG:3310", "north_test_boundary_m": score[2],
                    "south_validation_boundary_m": score[3],
                    "policy": "Whole tile footprint must lie on one side; crossing tiles excluded"}


def verify_no_cross_split_overlap(tiles):
    """Fail if any retained image's metric envelope overlaps another split."""
    for i, a in enumerate(tiles):
        if a["split"] == "buffer":
            continue
        ax0, ay0, ax1, ay1 = a["split_bounds_m"]
        for b in tiles[i+1:]:
            if b["split"] in (a["split"], "buffer"):
                continue
            bx0, by0, bx1, by1 = b["split_bounds_m"]
            if min(ax1,bx1) > max(ax0,bx0) and min(ay1,by1) > max(ay0,by0):
                raise ValueError(f"Spatial leakage: {a['tileId']} / {b['tileId']}")


def sheet_tiles(spec, source_dir, config):
    """Read sheet identity/neatline and produce manifests without resampling."""
    path = source_dir / (SOURCE_FILES[spec["map_id"]] + ".tif")
    if hashlib.sha256(path.read_bytes()).hexdigest() != spec["sha256"]:
        raise ValueError(f"Source checksum mismatch: {path}")
    meta = ET.parse(path.with_suffix(".xml")).getroot()
    nominal = [float(meta.findtext(".//"+key)) for key in ["westbc","southbc","eastbc","northbc"]]
    size = config["tile_size_px"]
    stride = round(size*(1-config["overlap_fraction"]))
    tiles = []
    with rasterio.open(path) as src:
        if src.count < 3 or src.dtypes[0] != "uint8":
            raise ValueError("Expected an RGB uint8 map raster")
        wkt = src.crs.to_wkt()
        polygon = neatline_polygon(wkt, nominal)
        pixels = [~src.transform * tuple(p) for p in polygon["coordinates"][0]]
        left = max(0, math.floor(min(p[0] for p in pixels)))
        top = max(0, math.floor(min(p[1] for p in pixels)))
        right = min(src.width, math.ceil(max(p[0] for p in pixels)))
        bottom = min(src.height, math.ceil(max(p[1] for p in pixels)))
        _, operation = transformer(wkt)
        for row in range(top, bottom, stride):
            for col in range(left, right, stride):
                affine = src.window_transform(Window(col,row,size,size))
                valid = geometry_mask([polygon], (size,size), affine, invert=True)
                valid &= (np.arange(size)[None,:]+col < src.width)
                valid &= (np.arange(size)[:,None]+row < src.height)
                fraction = float(valid.mean())
                if fraction < config["minimum_valid_fraction"]:
                    continue
                tile = {
                    "tileId": f"{spec['map_id']}_x{col:05d}_y{row:05d}",
                    "sheetName": spec["quadrangle"], "mapYear": spec["date_on_map"],
                    "transform": list(affine)[:6], "crs": wkt,
                    "widthPx": size, "heightPx": size,
                    "source_map_id": spec["map_id"], "source_sha256": spec["sha256"],
                    "source_file": str(path.resolve()), "source_pixel_offset": [col,row],
                    "valid_fraction": fraction, "annotation_status": "unlabeled",
                    "photo_revision_year": spec.get("photo_revision_year"),
                    "imprint_year": spec.get("imprint_year"),
                    "coordinate_operation": operation,
                }
                bounds = projected_tile_bounds(tile,"EPSG:4326")
                tile["bounds"] = dict(zip(["minLon","minLat","maxLon","maxLat"],bounds))
                tile["split_bounds_m"] = projected_tile_bounds(tile)
                # A window's affine must agree with the source at every corner.
                residual = max(max(abs(a-b) for a,b in zip(
                    ~src.transform * (affine*(x,y)), (col+x,row+y)))
                    for x,y in [(0,0),(size,0),(0,size),(size,size)])
                tile["corner_residual_px"] = residual
                if residual > 1:
                    raise ValueError("Tile affine reconstruction exceeds one source pixel")
                tiles.append(tile)
    return tiles, polygon


def prepare(region_path, dataset_path, source_dir, output):
    """Create image/split manifests atomically enough to mark partial runs incomplete."""
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing dataset: {output}")
    region = json.loads(region_path.read_text())
    config = json.loads(dataset_path.read_text())
    tiles, polygons = [], {}
    for spec in region["maps"]:
        group, polygon = sheet_tiles(spec,source_dir,config)
        tiles.extend(group)
        polygons[spec["map_id"]] = polygon
    assigned, boundaries = spatial_split(tiles, config["test_fraction_target"],
        config["minimum_test_tiles"], config["validation_fraction_target"],
        config["minimum_validation_tiles"])
    for tile in tiles:
        tile["split"] = assigned[tile["tileId"]]
    verify_no_cross_split_overlap(tiles)
    output.mkdir(parents=True)
    (output/"INCOMPLETE").write_text("Do not label/train from this run until preparation finishes.\n")
    counts = {k: sum(t["split"]==k for t in tiles) for k in ["train","val","test","buffer"]}
    for spec in region["maps"]:
        with rasterio.open(source_dir/(SOURCE_FILES[spec["map_id"]]+".tif")) as src:
            for tile in (t for t in tiles if t["source_map_id"]==spec["map_id"]):
                if tile["split"] == "buffer":
                    continue
                size = config["tile_size_px"]
                col,row = tile["source_pixel_offset"]
                image = src.read([1,2,3],window=Window(col,row,size,size),boundless=True,fill_value=255)
                valid = geometry_mask([polygons[spec["map_id"]]],(size,size),
                    rasterio.Affine(*tile["transform"]),invert=True)
                image[:,~valid] = 255
                relative = Path("images")/tile["split"]/(tile["tileId"]+".png")
                target = output/relative
                target.parent.mkdir(parents=True,exist_ok=True)
                Image.fromarray(image.transpose(1,2,0)).save(target,compress_level=3)
                tile["image_path"] = str(relative)
    rows = "".join(json.dumps(t,sort_keys=True)+"\n" for t in tiles)
    (output/"manifest.jsonl").write_text(rows)
    keys = ["tileId","sheetName","mapYear","transform","crs","widthPx","heightPx","bounds"]
    (output/"tiles_for_backend.jsonl").write_text("".join(json.dumps(
        {k:t[k] for k in keys})+"\n" for t in tiles if t["split"]!="buffer"))
    (output/"dataset.template.yaml").write_text(
        "# NOT READY FOR TRAINING: human labels and review are required first.\n"
        f"path: {output.resolve()}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: well_symbol\n")
    imports = output/"annotation_import"
    imports.mkdir()
    for split in ["train","val","test"]:
        with zipfile.ZipFile(imports/(split+".zip"),"w",compression=zipfile.ZIP_STORED) as archive:
            for tile in tiles:
                if tile["split"] == split:
                    archive.write(output/tile["image_path"],Path(tile["image_path"]).name)
    summary = {
        "schema_version": 1, "state": "ready_for_human_annotation_not_training",
        "region_id": region["region_id"], "tile_size_px": config["tile_size_px"],
        "stride_px": round(config["tile_size_px"]*(1-config["overlap_fraction"])),
        "counts": counts, "labeled_tiles": 0, "human_labeled_boxes": 0,
        "split_boundaries": boundaries, "split_manifest_sha256": hashlib.sha256(rows.encode()).hexdigest(),
        "maximum_corner_residual_px": max(t["corner_residual_px"] for t in tiles),
        "cross_split_overlap_pairs": 0,
        "source_maps": region["maps"], "dataset_config": config,
        "code_commit": subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
        "code_dirty": bool(subprocess.check_output(["git","status","--porcelain"],cwd=ROOT,text=True).strip()),
        "versions": {"python": platform.python_version(),"rasterio":rasterio.__version__,"pyproj":pyproj.__version__},
        "code_files_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [ROOT/"pipeline/geo.py",ROOT/"pipeline/prepare_dataset.py",region_path,dataset_path]},
        "coordinate_grids": config["coordinate_grid"],
        "limits": ["No human annotations or negative labels exist yet",
                   "No independent map-control-point or CalGEM accuracy measurement yet",
                   "Missing NADCON grids may reduce coordinate-operation accuracy; see per-tile metadata"],
    }
    (output/"summary.json").write_text(json.dumps(summary,indent=2))
    (output/"INCOMPLETE").unlink()
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region",type=Path,default=ROOT/"pipeline/config/region.json")
    parser.add_argument("--config",type=Path,default=ROOT/"pipeline/config/dataset.json")
    parser.add_argument("--source-dir",type=Path,default=ROOT/"data/research/maps")
    parser.add_argument("--output",type=Path,default=ROOT/"data/ml/kern_1024_v1")
    args = parser.parse_args()
    summary = prepare(args.region,args.config,args.source_dir,args.output)
    print(json.dumps({k:summary[k] for k in ["state","counts","maximum_corner_residual_px","cross_split_overlap_pairs"]},indent=2))


if __name__ == "__main__":
    main()
