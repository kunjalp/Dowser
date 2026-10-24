"""Pixel-edge coordinates, source CRS transforms, and native map neatlines.

Boxes use top-left x/y/width/height in original tile pixels. Affines map pixel
edges; a box center already includes its half width/height, so do not add 0.5.
All public latitude/longitude results are WGS84 with explicit axis naming.
"""

import warnings
from functools import lru_cache
from pathlib import Path

import numpy as np
from affine import Affine
from pyproj import CRS, datadir, network
from pyproj.aoi import AreaOfInterest
from pyproj.transformer import TransformerGroup


@lru_cache(maxsize=24)
def transformer(source_wkt, target="EPSG:4326"):
    """Return an available regional transform without network/grid downloads.

    The best NADCON grid may be absent. Preserve that fact and the operation's
    stated accuracy; neither is evidence of absolute map/survey accuracy.
    """
    network.set_network_enabled(False)
    local_grids = Path(__file__).resolve().parents[1]/"data/research/proj"
    if local_grids.is_dir():
        datadir.append_data_dir(str(local_grids))
    with warnings.catch_warnings(record=True) as caught:
        group = TransformerGroup(
            source_wkt, target, always_xy=True, allow_ballpark=False,
            area_of_interest=AreaOfInterest(-119.25, 35.25, -118.75, 35.625),
        )
    if not group.transformers:
        raise ValueError("No non-ballpark coordinate operation is available offline")
    operation = group.transformers[0]
    return operation, {
        "description": operation.description,
        "operation_accuracy_m": operation.accuracy,
        "best_available": group.best_available,
        "warnings": [str(w.message) for w in caught],
    }


def pixel_to_wgs84(affine_coefficients, crs_wkt, x, y):
    """Convert one tile pixel-edge position to named lat/lon; reject bad values."""
    if len(affine_coefficients) != 6 or not np.isfinite([*affine_coefficients, x, y]).all():
        raise ValueError("Expected six finite affine coefficients and finite x/y")
    native_x, native_y = Affine(*affine_coefficients) * (x, y)
    op, _ = transformer(crs_wkt)
    lon, lat = op.transform(native_x, native_y, errcheck=True)
    if not np.isfinite([lat, lon]).all() or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Invalid WGS84 output")
    return {"lat": lat, "lon": lon}


def box_center_to_wgs84(tile, box):
    """Use a manifest tile and native xywh box; raise on out-of-tile boxes."""
    x, y, width, height = (box[k] for k in ["x", "y", "w", "h"])
    if not np.isfinite([x, y, width, height]).all() or min(x, y) < 0 or min(width, height) <= 0:
        raise ValueError("Box must be finite, positive-size, and nonnegative")
    if x + width > tile["widthPx"] or y + height > tile["heightPx"]:
        raise ValueError("Box exceeds original tile dimensions")
    return pixel_to_wgs84(tile["transform"], tile["crs"], x + width / 2, y + height / 2)


def projected_tile_bounds(tile, target="EPSG:3310"):
    """Conservative densified tile-edge bounds in a target CRS, including padding."""
    affine = Affine(*tile["transform"])
    width, height = tile["widthPx"], tile["heightPx"]
    edges = []
    for t in np.linspace(0, 1, 17):
        edges.extend([(width*t, 0), (width*t, height), (0, height*t), (width, height*t)])
    world = [affine * p for p in edges]
    op, _ = transformer(tile["crs"], target)
    xs, ys = op.transform(*zip(*world), errcheck=True)
    return [min(xs), min(ys), max(xs), max(ys)]


def neatline_polygon(crs_wkt, nominal_bounds):
    """Project nominal printed quad bounds in the SOURCE geodetic datum.

    Historical NAD27 collar numbers must not be treated as WGS84 coordinates.
    Densify the borders because a projected latitude edge need not be straight.
    """
    west, south, east, north = nominal_bounds
    crs = CRS.from_wkt(crs_wkt)
    from pyproj import Transformer
    op = Transformer.from_crs(crs.geodetic_crs, crs, always_xy=True)
    ring = []
    for a, b in [((west, south), (east, south)), ((east, south), (east, north)),
                 ((east, north), (west, north)), ((west, north), (west, south))]:
        for t in np.linspace(0, 1, 33):
            ring.append(op.transform(a[0] + t*(b[0]-a[0]), a[1] + t*(b[1]-a[1])))
    ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}
