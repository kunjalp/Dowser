"""Independent boundary/error cases for exported human labels."""

import tempfile
import unittest
import hashlib
import io
import json
import zipfile
from pathlib import Path

from PIL import Image

from pipeline.audit_annotations import audit, match_tile, parse_labels


class LabelAuditTest(unittest.TestCase):
    def test_normalized_box_maps_to_native_pixels(self):
        boxes,fixes = parse_labels("0 0.5 0.25 0.125 0.0625")
        self.assertEqual(boxes,[{"row":1,"x":448,"y":224,"w":128,"h":64}])
        self.assertEqual(fixes,[])

    def test_only_rounding_scale_overflow_is_clipped_and_logged(self):
        boxes,fixes = parse_labels("0 0.008505859375 0.668564453125 0.017021484375 0.01412109375")
        self.assertEqual(boxes[0]["x"],0)
        self.assertEqual(len(fixes),1)
        self.assertLess(fixes[0]["overflow_px"],0.02)
        with self.assertRaises(ValueError):
            parse_labels("0 0.001 0.5 0.1 0.1")

    def test_wrong_classes_nonfinite_and_degenerate_boxes_fail(self):
        for row in ["1 .5 .5 .1 .1","0 nan .5 .1 .1","0 .5 .5 0 .1",
                    "0 .5 .5 .1 -1","0 .5 .5 .1","0 .5 .5 .1 .1 7"]:
            with self.subTest(row=row),self.assertRaises(ValueError):
                parse_labels(row)

    def test_empty_label_does_not_invent_a_symbol(self):
        self.assertEqual(parse_labels("\n"),([],[]))

    def test_filename_mapping_cannot_move_a_test_tile_into_train(self):
        name="usgs_293661_x00000_y00000"
        filename=name+"_png.rf.abcdef.jpg"
        tile={"tileId":name,"split":"train"}
        self.assertEqual(match_tile(filename,{name:tile}),tile)
        for split in ["val","test","buffer"]:
            with self.assertRaises(ValueError):
                match_tile(filename,{name:dict(tile,split=split)})
        with self.assertRaises(ValueError):
            match_tile("unknown.jpg",{name:tile})

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileExistsError):
                audit(Path("absent.zip"),Path("absent"),Path(folder))

    def test_explicit_validation_import_accepts_only_frozen_validation_ids(self):
        name="usgs_1_x00000_y00000"
        filename=name+"_png.rf.abcdef.jpg"
        tile={"tileId":name,"split":"val"}
        self.assertEqual(match_tile(filename,{name:tile},"val"),tile)
        with self.assertRaises(ValueError):
            match_tile(filename,{name:dict(tile,split="train")},"val")

    def test_mixed_archive_imports_requested_split_and_preserves_explicit_empty_label(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); dataset=root/"source"; dataset.mkdir()
            stream=io.BytesIO(); Image.new("RGB",(1024,1024),"white").save(stream,format="PNG")
            data=stream.getvalue(); manifest=[]
            for split,identifier in [("train","usgs_1_x00000_y00000"),("val","usgs_1_x02000_y00000")]:
                relative=Path("images")/split/(identifier+".png")
                (dataset/relative).parent.mkdir(parents=True,exist_ok=True)
                (dataset/relative).write_bytes(data)
                manifest.append({"tileId":identifier,"split":split,"image_path":str(relative),"mapYear":1954})
            (dataset/"manifest.jsonl").write_text("".join(json.dumps(r)+"\n" for r in manifest))
            archive=root/"export.zip"
            with zipfile.ZipFile(archive,"w") as z:
                z.writestr("data.yaml","nc: 1\nnames: [well_symbol]\n")
                for split,row in zip(["train","valid"],manifest):
                    z.writestr(f'{split}/images/{row["tileId"]}.png',data)
                    z.writestr(f'{split}/labels/{row["tileId"]}.txt',"")
            summary=audit(archive,dataset,root/"import","val")
            self.assertEqual(summary["image_count"],1)
            self.assertEqual(summary["split"],"val")
            self.assertEqual(summary["empty_label_images"],1)
            self.assertFalse((root/"import/images/train").exists())


if __name__ == "__main__":
    unittest.main()
