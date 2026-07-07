"""验证 test yolo image pipeline 相关功能。"""

import unittest

from wastekg.yolo.image_pipeline import records_from_yolo_result


class FakeVector:
    def __init__(self, values):
        self.values = values

    def tolist(self):
        return list(self.values)


class FakeBoxes:
    cls = FakeVector([1, 6])
    conf = FakeVector([0.93, 0.52])
    xyxy = FakeVector([[10, 20, 110, 220], [1, 2, 11, 22]])


class FakeMasks:
    xy = [
        [[10, 20], [110, 20], [110, 220], [10, 220]],
        [[1, 2], [11, 2], [11, 22], [1, 22]],
    ]


class FakeResult:
    names = {1: "brick", 6: "metal"}
    boxes = FakeBoxes()
    masks = FakeMasks()


class YoloImagePipelineTests(unittest.TestCase):
    def test_records_from_yolo_result_converts_detection_to_graph_input_record(self) -> None:
        records = records_from_yolo_result(FakeResult())

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["temp_id"], "det_001")
        self.assertEqual(records[0]["yolo_class_name"], "brick")
        self.assertEqual(records[0]["yolo_confidence"], 0.93)
        self.assertEqual(records[0]["bbox_xyxy"], [10.0, 20.0, 110.0, 220.0])
        self.assertEqual(records[0]["center_xyz"], [60.0, 120.0, 0.0])
        self.assertEqual(records[0]["mask_polygon"], [(10.0, 20.0), (110.0, 20.0), (110.0, 220.0), (10.0, 220.0)])

    def test_records_from_yolo_result_can_limit_to_highest_confidence_records(self) -> None:
        records = records_from_yolo_result(FakeResult(), max_detections=1)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["yolo_class_name"], "brick")
        self.assertEqual(records[0]["yolo_confidence"], 0.93)


if __name__ == "__main__":
    unittest.main()
