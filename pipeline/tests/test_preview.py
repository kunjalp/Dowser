"""Preview geometry must retain original asymmetric boxes and reject bad scores."""

import unittest

from pipeline.preview_detector import native_box


class PreviewGeometryTest(unittest.TestCase):
    def test_xyxy_is_native_xywh_without_half_pixel_shift(self):
        b=native_box([10,20,30,70],.7,0,(1024,1024))
        self.assertEqual([b[k] for k in ['x','y','w','h']],[10,20,20,50])
        self.assertEqual(b['confidence'],.7)
        self.assertEqual(b['source'],'model')

    def test_wrong_geometry_class_and_nonfinite_scores_fail(self):
        for box,score,cls,shape in [([0,0,10,10],.5,0,(512,512)),
            ([0,0,10,10],.5,1,(1024,1024)),([0,0,1025,10],.5,0,(1024,1024)),
            ([0,0,0,10],.5,0,(1024,1024)),([0,0,10,10],float('nan'),0,(1024,1024))]:
            with self.subTest(box=box,score=score,cls=cls,shape=shape),self.assertRaises(ValueError):
                native_box(box,score,cls,shape)


if __name__=='__main__':
    unittest.main()
