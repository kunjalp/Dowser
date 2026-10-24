"""Reserve validation before fitting without consuming existing labels/Test."""

import unittest
from pipeline.reserve_validation import revise


def tile(name, split, box, fraction=1):
    return {"tileId":name,"split":split,"split_bounds_m":box,"valid_fraction":fraction}


class RevisionTest(unittest.TestCase):
    def setUp(self):
        self.rows=[tile("human","train",[0,0,10,10]),tile("newval","train",[20,0,30,10]),
                   tile("other_era","train",[25,0,35,10]),tile("oldval","val",[40,0,50,10]),
                   tile("test","test",[60,0,70,10])]

    def test_reserves_whole_geographic_group_and_preserves_work(self):
        result=revise(self.rows,["newval"],{"human"})
        self.assertEqual({r["tileId"]:r["split"] for r in result},
                         {"human":"train","newval":"val","other_era":"buffer","oldval":"val","test":"test"})
        self.assertEqual(self.rows[1]["split"],"train")

    def test_cannot_move_or_overlap_completed_training_image(self):
        with self.assertRaisesRegex(ValueError,"human"):
            revise(self.rows,["human"],{"human"})
        self.rows[1]["split_bounds_m"]=[5,0,15,10]
        with self.assertRaisesRegex(ValueError,"human"):
            revise(self.rows,["newval"],{"human"})

    def test_cannot_use_padded_edge_or_test_image_as_new_validation(self):
        self.rows[1]["valid_fraction"]=.2
        with self.assertRaises(ValueError):
            revise(self.rows,["newval"],{"human"})
        with self.assertRaises(ValueError):
            revise(self.rows,["test"],{"human"})


if __name__ == "__main__":
    unittest.main()
