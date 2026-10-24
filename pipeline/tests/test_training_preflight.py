"""Training must fail closed on missing, changed, or overlapping reviewed data."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from pipeline.train_detector import check_inputs


class TrainingPreflightTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.train_id = "usgs_1_x00000_y00000"
        self.val_id = "usgs_1_x02000_y00000"
        self.manifest = [{"tileId":self.train_id,"split":"train","split_bounds_m":[0,0,10,10]},
                         {"tileId":self.val_id,"split":"val","split_bounds_m":[20,0,30,10]}]
        (self.root/"manifest.jsonl").write_text("".join(json.dumps(r)+"\n" for r in self.manifest))
        self.write_import("train",self.train_id)
        self.write_import("val",self.val_id)
        (self.root/"weights.pt").write_bytes(b"fixture model")
        self.config={"manifest":"manifest.jsonl","train_import":"train","validation_import":"val",
                     "minimum_training_boxes":1,"require_all_validation_tiles":True,
                     "weights":"weights.pt","weights_sha256":hashlib.sha256(b"fixture model").hexdigest()}

    def write_import(self, split, tile_id, negative=False):
        folder=self.root/split
        (folder/"images"/split).mkdir(parents=True,exist_ok=True)
        (folder/"labels"/split).mkdir(parents=True,exist_ok=True)
        path=folder/"images"/split/(tile_id+".png")
        Image.new("RGB",(1024,1024),"white").save(path)
        (folder/"labels"/split/(tile_id+".txt")).write_text("" if negative else "0 0.5 0.5 0.125 0.125\n")
        boxes=[] if negative else [{"row":1,"x":448,"y":448,"w":128,"h":128}]
        (folder/"audit.json").write_text(json.dumps({"images":[{"tileId":tile_id,"split":split,
            "original_png_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"boxes":boxes}]}))

    def test_ready_only_with_independent_reviewed_validation(self):
        result=check_inputs(self.config,self.root)
        self.assertEqual(result["validation_images"],1)
        self.assertTrue(result["validation_has_positives"])
        self.assertFalse(result["test_used"])

    def test_missing_validation_never_starts_a_run(self):
        (self.root/"val/audit.json").unlink()
        with self.assertRaisesRegex(FileNotFoundError,"Missing reviewed val"):
            check_inputs(self.config,self.root)
        self.assertFalse((self.root/"data/ml/runs").exists())

    def test_changed_labels_are_not_silently_used(self):
        (self.root/"train/labels/train"/(self.train_id+".txt")).write_text("0 .1 .1 .1 .1\n")
        with self.assertRaisesRegex(ValueError,"Labels differ"):
            check_inputs(self.config,self.root)

    def test_unaudited_images_cannot_become_fake_negatives(self):
        Image.new("RGB",(1024,1024)).save(self.root/"train/images/train/unreviewed.png")
        with self.assertRaisesRegex(ValueError,"Unexpected unaudited"):
            check_inputs(self.config,self.root)

    def test_wrong_split_and_overlapping_geography_rejected(self):
        self.manifest[1]["split"]="test"
        (self.root/"manifest.jsonl").write_text("".join(json.dumps(r)+"\n" for r in self.manifest))
        with self.assertRaisesRegex(ValueError,"Frozen split"):
            check_inputs(self.config,self.root)
        self.manifest[1].update(split="val",split_bounds_m=[5,0,15,10])
        (self.root/"manifest.jsonl").write_text("".join(json.dumps(r)+"\n" for r in self.manifest))
        with self.assertRaisesRegex(ValueError,"footprints overlap"):
            check_inputs(self.config,self.root)

    def test_negative_only_validation_is_explicitly_diagnostic(self):
        self.write_import("val",self.val_id,negative=True)
        with self.assertRaisesRegex(ValueError,"Positive validation"):
            check_inputs(self.config,self.root)
        result=check_inputs(dict(self.config,allow_negative_only_validation=True),self.root)
        self.assertFalse(result["validation_has_positives"])
        self.assertIn("recall/mAP undefined",result["validation_scope"])

    def test_pretrained_weights_identity_is_checked(self):
        (self.root/"weights.pt").write_bytes(b"different model")
        with self.assertRaisesRegex(ValueError,"checksum"):
            check_inputs(self.config,self.root)


if __name__ == "__main__":
    unittest.main()
