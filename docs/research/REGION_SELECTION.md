# Region and map selection

Decision: use **Kern County, specifically the Oil Center + Oildale study area**.
Start with **USGS Oil Center, map 293661, date-on-map 1954, photorevised 1968,
printed 1970, 1:24,000 GeoTIFF**. Add Oildale 1954 and Oil Center 1992 for the
initial three-map set. The exact files and checksums are in
[the canonical region config](../../pipeline/config/region.json).

Research date: October 23, 2026, America/Los_Angeles. Code baseline:
`15f7c8f` on main. This is source/data research and an ML region decision;
no detector was trained or run, and no well or leak was field-confirmed.

## Why this selection

The strongest advantage is an independently published reproducibility package
for the exact Oil Center sheet. It contains a U-Net model, inference notebook,
map/XML, point detections, candidate CSV, and a historical CalGEM snapshot.
This gives the team a concrete input/output reference rather than an arbitrary
map. The public resource list and small artifacts were actually retrieved.
The model weights were listed but not downloaded or executed. [1]

The adjacent Oildale sheet provides different geography, oil fields, urban edges,
tanks, roads, buildings, and useful negative examples. Oil Center 1992 is a
visually inspected conventional topographic map for a later era. These maps
support a compact, consistent region with enough historical symbols to begin
labeling. The published Oil Center output has 1,907 predictions, which is evidence
of symbol abundance, not a count of correct labels or Dowser model performance.

In the inspected native-resolution crops, Oil Center has many isolated hollow
circles on a relatively light background. The inspected Inglewood/Baldwin Hills
and Signal Hill crops combine well symbols with denser urban linework, lettering,
contours, or very crowded symbols. That is a qualitative reason to prefer the
Kern example for a first labeling/detection pass; it is not a measured accuracy
comparison between regions. LA remains a good later transfer test.

## Bounds and scope

Study rectangle, **WGS84, west/south/east/north**:

```json
[-119.125, 35.375, -118.875, 35.500]
```

Its geodesic area is about **314.82 km²**. It spans two nominal 7.5-minute
quadrangles; it is not all Kern County. The original `kern` rectangle in the
CalGEM loader is much broader and remains unchanged.

Reference-well extraction needs a margin so a documented well just outside the
study rectangle is still available for a 100 m match. Use the config's conservative
query rectangle, approximately 500 m or more beyond each edge:

```json
[-119.131, 35.370, -118.869, 35.505]
```

```sh
python3 pipeline/load_calgem.py --region kern \
  --bbox -119.131 35.370 -118.869 35.505 --inspect
```

Remove `--inspect` only when actually loading reference data. Do not substitute
the unbuffered study bbox for the reference-data query. Nominal quadrangle
coordinates are a selection aid; use each raster's native transform and CRS for
actual pixel coordinates, collar masking, and sheet edges.

## Comparison based on actual API probes

All record counts below came from the same live CalGEM layer with `where=1=1`
and a WGS84 envelope. They include all statuses, repeated surface locations,
and planned/canceled records where the service maps them. They are **not** counts
of orphaned wells, unknown wells, emissions, or unique physical wellheads.
The rectangles have different sizes, so totals alone are not a fair ranking.

| Candidate subregion | WGS84 bbox (W,S,E,N) | Area km² | Mapped CalGEM records | Records/km² | 1:24k historical map options, 1947–1992 |
| --- | --- | ---: | ---: | ---: | --- |
| **Oil Center/Oildale, Kern** | -119.125,35.375,-118.875,35.5 | 314.82 | **27,381** | 87.0 | 12 catalog editions; 2 quadrangles; exact published reference sheet |
| Taft/Maricopa, Kern | -119.5,35.0,-119.25,35.25 | 632.02 | 18,792 | 29.7 | 19 editions; Taft, Maricopa, Mouth of Kern, Pentland |
| McKittrick-area search box, Kern | -119.75,35.25,-119.5,35.5 | 630.11 | 47,206 | 74.9 | 17 editions; Belridge, Lokern, Reward, West Elk Hills |
| Western LA Basin | -118.5,33.875,-118.25,34.125 | 640.47 | 5,017 | 7.8 | 30 editions; Beverly Hills, Hollywood, Inglewood, Venice, edge coverage of Burbank |
| Signal Hill/Long Beach, LA | -118.25,33.75,-118.125,33.875 | 160.46 | 8,554 | 53.3 | 9 editions of Long Beach |

Catalog editions were filtered to 1:24,000, the stated year range, and positive
area intersection: the USGS API also returns sheets merely touching the query
boundary. Editions include reprints and are not independent training examples.
The McKittrick label denotes this specific search rectangle, not an official
town/field boundary. Density supports data-volume planning; it does not predict
the number of genuinely undocumented wells.

The selected Kern count includes 9,645 Active, 2,806 Idle, 13,694 Plugged,
1,123 Canceled, 100 New, and 13 other status records. Excluding Plugged wells
would create false undocumented candidates. Whether Canceled/New records should
participate in matching needs an explicit backend policy; the current PRD says
to compare against documented records generally. None of the five closest
records in the published-candidate recheck below were Canceled/New. [2]

## Exact map choices

| Role | Exact file | Dates verified from source XML | Downloaded size and raster |
| --- | --- | --- | --- |
| **Start here** | `CA_Oil Center_293661_1954_24000_geo.tif` | Date-on-map 1954; photo revision 1968; imprint 1970 | 12,034,183 bytes; 6583×8071 |
| Adjacent geography | `CA_Oildale_293664_1954_24000_geo.tif` | Date-on-map 1954; aerial photo 1952; imprint 1956 | 9,997,593 bytes; 6588×8029 |
| Later era | `CA_Oil Center_102321_1992_24000_geo.tif` | Date-on-map 1992; aerial photo 1992; edit/imprint 1995 | 13,667,891 bytes; 6450×8092 |

All three GeoTIFFs were downloaded, opened, and visually inspected; their XML
metadata was retrieved. Each has a nominal 2.032 m pixel size. That is raster
resolution, **not** a 2 m location-accuracy claim. The selected files total about
35.7 MB (decimal) and remain outside Git under `data/research/maps/`.

Direct primary GeoTIFF: [USGS Oil Center 293661](https://prd-tnm.s3.amazonaws.com/StagedProducts/Maps/HistoricalTopo/GeoTIFF/CA/CA_Oil%20Center_293661_1954_24000_geo.tif).
Direct XML: [USGS metadata](https://thor-f5.er.usgs.gov/ngtoc/metadata/waf/maps/historicaltopo/pdf/CA/24000/CA_Oil_Center_293661_1954_24000_geo.xml).
All three direct URLs and SHA-256 values are in the config.

This is **three sheet editions over two geographic quadrangles and two
date-on-map eras**, not three independent regions. Keep overlapping geography
across years in the same split. If three distinct geographic quadrangles are
needed, the visually checked Rosedale 1954 map 294816 is a nearby extension;
it would require expanding the study bbox west to -119.25. Do not silently use
that extension while keeping the original bounds.

## Traps found by inspecting files rather than titles

**Reject Oil Center 1978, map 293663, from this symbol dataset.** Its collar says
it is an orthophotograph prepared from 1978 aerial photographs. Its image is a
photographic product, not the conventional symbol map expected by this detector.
The generic catalog title alone did not reveal the distinction.

**Year on filename is not the full time history.** The selected 1954 reference
has 1968 photo revisions. Another downloaded Oil Center 1954 edition, map 293660,
was printed in 1966 without that same revision history. Taft 1950 map 295371
has 1973 photo revisions and a 1986 imprint. Preserve source ID, base year,
revision year, imprint year, and artifact checksum separately; do not choose
an arbitrary item with the same map name/year. [3]

**CRS is not simply WGS84 or a guessed UTM code.** The 1954 files contain custom
NAD27 Polyconic definitions. Preserve full WKT and a distinct affine per sheet.
The 1992 map must be read from its own metadata. Check coordinate transformations
against control points before a 100 m record match. GeoTIFF georeferencing
preserves the original map's accuracy, not an improvement over it. [3,4]

**Do not downsample the whole sheet to model input size.** Native crops show tiny
circles among text, tanks, roads, contours, and filled symbols. Tile at native
resolution and retain enough pixels for small symbols. Template/YOLO/U-Net
comparisons need an actual labeled validation split; no precision estimate was
measured in this research.

## Published example: useful baseline, not ground truth

The EDX package's JSON lists **1,907 point predictions** and its CSV lists
**5 candidate points** against a November 28, 2023 CalGEM snapshot. The number
stored beside each coordinate in that JSON is the **distance to the nearest
documented well in metres**, not model confidence. The CSV's `Bbox` also uses
a different ordering from Dowser's W,S,E,N convention. Do not import either
artifact directly as the backend detection schema. [1]

For each published candidate, this research queried current CalGEM geometry
within 1 km and computed WGS84 ellipsoidal nearest distance. No query was
truncated. All five still had no returned mapped record within 100 m:

| Published ID | Published distance m | Current nearest distance m | Current closest record status |
| --- | ---: | ---: | --- |
| 3 | 187 | 187.8 | Plugged |
| 81 | 102 | 101.6 | Plugged |
| 392 | 139 | 138.3 | Plugged |
| 708 | 526 | 526.0 | Plugged |
| 776 | 490 | 488.1 | Plugged |

This proves the spatial-filter example is reproducible against the queried layer,
not that the map predictions are correct or that these are new discoveries.
Native crops were examined: ID 776 appears to overlap a printed numeral zero;
ID 708 is ambiguous near linear features; ID 81 is only about 1.6 m beyond the
threshold. These need human review and calibration. No point here is an endorsed
field visit or a confirmed undocumented well. Threshold sensitivity on this
five-point sample is 5 / 3 / 2 / 1 remaining for 100 / 150 / 200 / 500 m.

Published predictions may seed a review workflow, but must carry attribution and
must never become unreviewed training ground truth or an independent test set.
The EDX README describes CC BY 4.0 attribution terms. Preserve the DOI/citation
and check event rules before using external model weights. The provided model
uses an older TensorFlow/Keras 2.8 environment and is about 294 MB, so availability
does not imply immediate compatibility with a modern local environment. [1]

The PRD calls for fine-tuned YOLO (FR-2.3). Using this published U-Net as the
detector would be an explicit PRD decision, not an invisible replacement.
Region selection does not change that requirement or claim the model has run.

## Why not start elsewhere

**LA Basin:** stronger urban exposure storytelling is plausible, but actual
current school/building distances still need data. The inspected urban crops
have heavier linework and densely overlapping symbols. No exact LA sample with
the same packaged map/metadata/output reference was found in this bounded
research. That is a reproducibility advantage for Oil Center, not a claim that
LA lacks maps, wells, or research evidence. Both counties were covered by the
published Berkeley Lab work. [1,5]

**Taft/Maricopa:** credible alternative with many records and accessible maps.
The inspected Taft edition has usable symbols and oil fields. It loses the
first-choice tie-breaker because Oil Center provides the exact published
input/output package, not because Taft is unsuitable.

**McKittrick/Belridge:** the largest record count among these probes. That does
not make it the easiest location to demonstrate a genuinely absent record;
dense known-well neighborhoods can mask missing wells under a 100 m rule.
Avoid choosing a region solely by how many mapped records it contains.

## Remaining checks and first work

1. Open the primary TIFF in GIS, mask its collar, and verify at least three
   independent control points plus the PRD's ten known-well spot checks.
2. Label/review a small geographically separated batch before committing to a
   detector. Use actual well circles and hard negatives, including numerals,
   circular road features, tanks, and contour loops.
3. Assign spatial groups before overlapping tiles/augmentation; keep repeated
   territory from 1954/1968/1992 together. Report actual per-era metrics.
4. Retrieve buffered current CalGEM data, retain all relevant statuses, and make
   matching uncertainty visible. The live layer exposes `API` as a string;
   preserve it rather than assuming an eight-digit numeric format.
5. Validate current OSM schools/buildings and score inputs. Overpass probes in
   this session failed with TLS, timeout, or rate-limit responses; no modern
   proximity count or distance is claimed. A school printed in 1954 is not
   evidence that it operates today. Keep this as a data-ingestion task.

Berkeley Lab's work supports using standard 1:24,000 symbol maps from the
1947–1992 collection window. The demo should say historical maps; these chosen
editions should not be described as century-old maps. [5]

## Reproduce and evidence boundaries

```sh
python3 pipeline/research/region_sources.py catalog
python3 pipeline/research/region_sources.py wells
python3 -m venv .venv
.venv/bin/python -m pip install -r pipeline/research/requirements.txt
.venv/bin/python pipeline/research/inspect_maps.py
.venv/bin/python pipeline/research/region_sources.py edx
.venv/bin/python pipeline/research/region_sources.py published
```

`catalog` and `wells` use the standard library. Raster inspection and the geodesic
candidate check need the optional research dependencies. `--all` on raster
inspection downloads all nine comparison samples (about 100 MB), including the
rejected orthophoto. JSON source responses, URLs, retrieval times, and checksums
are cached under ignored `data/research/`. Use `--refresh` on source probes when
updating the dated evidence. No deployment or external account is written.

Verified: all nine sampled TIFFs and their XML opened; the three selected hashes
match the config; all five neighborhood queries were complete; the existing
five CalGEM loader tests passed. Not performed: model training/inference, a
complete labeled symbol census, field confirmation, or a successful OSM proximity
ingest. The default `kern`/`la_basin` loader presets were not changed.

## Sources

1. [DOE/NETL EDX dataset, DOI 10.18141/2452768](https://doi.org/10.18141/2452768),
   [public resource metadata API](https://edx.netl.doe.gov/api/3/action/package_show?id=u-net-based-usgs-quadrangles-oil-and-gas-well-symbols-identification),
   including downloaded README, map XML, prediction notebook, output JSON and CSV.
2. [CalGEM WellSTAR layer and query interface](https://gis.conservation.ca.gov/server/rest/services/WellSTAR/Wells/MapServer/0),
   [coverage limitations described by CalGEM](https://conservation.ca.gov/calgem/Online_Data/Pages/WellSTAR-Data-Dashboard.aspx).
3. [USGS TNM catalog query for the chosen study area](https://tnmaccess.nationalmap.gov/api/v1/products?datasets=Historical%20Topographic%20Maps&bbox=-119.125,35.375,-118.875,35.5&max=1000)
   and the exact per-map USGS XML URLs recorded in the config.
4. [USGS topoView format/metadata guide](https://ngmdb.usgs.gov/topoview/help/).
5. [Berkeley Lab explanation of the published California/Oklahoma workflow](https://newscenter.lbl.gov/2024/12/04/ai-helps-researchers-dig-through-old-maps-to-find-lost-oil-and-gas-wells/),
   [underlying paper DOI](https://doi.org/10.1021/acs.est.4c04413).
