"""Before fitting, add full-content held-outs without moving labeled Train/Test.

Old Validation images remain, and neighboring unreviewed Train images are
quarantined as buffer across all editions. Source datasets are never overwritten.
"""

import argparse
import copy
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from pipeline.prepare_dataset import ROOT, verify_no_cross_split_overlap


def overlaps(a, b):
    """Positive overlap of conservative metric envelopes, including padded pixels."""
    x,y,r,s = a["split_bounds_m"]
    u,v,w,z = b["split_bounds_m"]
    return min(r,w)>max(x,u) and min(s,z)>max(y,v)


def revise(tiles, reserved, protected_train, minimum_fraction=.95):
    """Return a revised split; reject reservations touching user labels or Test."""
    by_id = {t["tileId"]:t for t in tiles}
    chosen = [by_id[k] for k in reserved]
    if not chosen or len(set(reserved)) != len(reserved):
        raise ValueError("Choose distinct held-out tiles")
    for tile in chosen:
        if tile["split"] != "train" or tile["valid_fraction"] < minimum_fraction:
            raise ValueError("New validation must use full-content unreviewed Train tiles")
        if any(overlaps(tile,by_id[k]) for k in protected_train):
            raise ValueError("Reservation would touch existing human training labels")
    result = copy.deepcopy(tiles)
    for tile in result:
        if tile["tileId"] in reserved:
            tile["split"] = "val"
        elif tile["split"] == "train" and any(overlaps(tile,r) for r in chosen):
            if tile["tileId"] in protected_train:
                raise ValueError("Cannot quarantine a human-reviewed training image")
            tile["split"] = "buffer"
    assert {t["tileId"] for t in result if t["split"]=="test"} == {t["tileId"] for t in tiles if t["split"]=="test"}
    verify_no_cross_split_overlap(result)
    return result


def prepare(config_path):
    """Build a separate versioned manifest/images and a new Validation ZIP."""
    config = json.loads(config_path.read_text())
    base,output = ROOT/config["base_dataset"],ROOT/config["output_dataset"]
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite: {output}")
    source_manifest = base/"manifest.jsonl"
    old = list(map(json.loads,source_manifest.read_text().splitlines()))
    protected = json.loads((ROOT/config["preserved_human_import"]/"audit.json").read_text())["images"]
    protected_ids = {r["tileId"] for r in protected}
    rows = revise(old,config["reserve_tile_ids"],protected_ids,config["minimum_full_tile_fraction"])
    output.mkdir(parents=True)
    (output/"INCOMPLETE").write_text("Split revision not complete.\n")
    old_byid = {r["tileId"]:r for r in old}
    for tile in rows:
        previous = old_byid[tile["tileId"]]
        if tile["split"] == "buffer":
            tile.pop("image_path",None)
            continue
        source = base/previous["image_path"]
        relative = Path("images")/tile["split"]/(tile["tileId"]+".png")
        target = output/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
        tile["image_path"] = str(relative)
        tile["original_split"] = previous["split"]
    manifest = "".join(json.dumps(r,sort_keys=True)+"\n" for r in rows)
    (output/"manifest.jsonl").write_text(manifest)
    summary = {"schema_version":1,"reason":config["reason"],
               "counts":{s:sum(r["split"]==s for r in rows) for s in ["train","val","test","buffer"]},
               "base_manifest_sha256":hashlib.sha256(source_manifest.read_bytes()).hexdigest(),
               "manifest_sha256":hashlib.sha256(manifest.encode()).hexdigest(),
               "new_validation_ids":config["reserve_tile_ids"],
               "preserved_human_training_ids":sorted(protected_ids),"test_ids_unchanged":True,
               "cross_split_overlap_pairs":0,"human_annotations_added":0,
               "limits":["Original validation images remain predominantly edge strips",
                         "Added full-content images need independent annotation; positive symbols not guaranteed",
                         "Split is revised before detector fitting; old source and five human labels remain unchanged"]}
    (output/"summary.json").write_text(json.dumps(summary,indent=2))
    (output/"annotation_import").mkdir()
    with zipfile.ZipFile(output/"annotation_import/val.zip","w",zipfile.ZIP_STORED) as z:
        for row in rows:
            if row["split"] == "val":
                z.write(output/row["image_path"],row["tileId"]+".png")
    (output/"INCOMPLETE").unlink()
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",type=Path,default=ROOT/"pipeline/config/validation_revision.json")
    args=parser.parse_args()
    print(json.dumps(prepare(args.config),indent=2))


if __name__ == "__main__":
    main()
