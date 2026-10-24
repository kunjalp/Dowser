"""Check proposal provenance, pixel conversion, and protection of held-out data."""

import unittest

from pyproj import CRS

from pipeline.propose_annotations import MAP_ID, MAP_SHA, point_boxes, select_tiles


class ProposalTest(unittest.TestCase):
    def tile(self, **changes):
        return dict({"tileId":"fixture", "split":"train", "source_map_id":MAP_ID,
                     "source_sha256":MAP_SHA, "crs":CRS.from_epsg(4326).to_wkt(),
                     "transform":[.001,0,-119,0,-.001,35.5],
                     "widthPx":1024,"heightPx":1024}, **changes)

    def test_projects_centers_clips_edges_and_preserves_distance_not_confidence(self):
        boxes = point_boxes(self.tile(), {"a":[[35.48,-118.99],187],
                                         "b":[[35.499,-118.999],0],
                                         "outside":[[36,-119],5]}, radius=8)
        self.assertEqual(len(boxes),2)
        self.assertAlmostEqual(boxes[0]["x"],2)
        self.assertAlmostEqual(boxes[0]["y"],12)
        self.assertEqual(boxes[0]["published_nearest_record_distance_m"],187)
        self.assertNotIn("confidence",boxes[0])
        self.assertEqual(boxes[0]["review_status"],"unreviewed")
        self.assertEqual(boxes[1]["x"],0)
        self.assertEqual(boxes[1]["y"],0)

    def test_never_proposes_on_validation_test_or_buffer(self):
        for split in ["val","test","buffer"]:
            with self.assertRaises(ValueError):
                point_boxes(self.tile(split=split),{})

    def test_rejects_wrong_source_and_invalid_geometry(self):
        for tile in [self.tile(source_map_id="usgs_102321"), self.tile(source_sha256="wrong")]:
            with self.assertRaises(ValueError):
                point_boxes(tile,{})
        with self.assertRaises(ValueError):
            point_boxes(self.tile(),{"a":[[float("nan"),-119],5]})
        with self.assertRaises(ValueError):
            point_boxes(self.tile(),{},radius=0)

    def test_selection_maximizes_distinct_ids_deterministically(self):
        a=({"tileId":"a"},[{"published_id":"1"},{"published_id":"2"}])
        b=({"tileId":"b"},[{"published_id":"1"},{"published_id":"2"}])
        c=({"tileId":"c"},[{"published_id":"3"}])
        self.assertEqual([t[0]["tileId"] for t in select_tiles([b,c,a],2)],["a","c"])


if __name__ == "__main__":
    unittest.main()
