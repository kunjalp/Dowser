"""Independent boundary/error cases for exported human labels."""

import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
