"""Run records retain real optimizer progress and failures without GPU fixtures."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pipeline.train_detector import run


class TrainingRecordTest(unittest.TestCase):
    def exercise(self, root, fail=False):
        class Optimizer:
            def register_step_post_hook(self, hook):
                self.hook = hook

            def step(self):
                self.hook(self, (), {})

        class Model:
            def __init__(self, weights):
                self.callbacks = {}
                self.trainer = SimpleNamespace(optimizer=Optimizer(),epoch=0,
                    metrics={"precision":0.25},save_dir=root/"training")

            def add_callback(self, event, callback):
                self.callbacks[event] = callback

            def train(self, **kwargs):
                self.callbacks["on_pretrain_routine_end"](self.trainer)
                # Two batches but only one optimizer update: telemetry must not
                # equate epochs/batches with actual steps under accumulation.
                self.trainer.optimizer.step()
                self.callbacks["on_train_epoch_end"](self.trainer)
                if fail:
                    raise RuntimeError("fixture interrupted after first epoch")

        config={"versions":{},"train_import":"train","validation_import":"val",
                "weights":"base.pt","training":{}}
        with patch("pipeline.train_detector.ROOT",root), \
             patch("pipeline.train_detector.check_inputs",return_value={"validation_has_positives":True}), \
             patch("pipeline.train_detector.local_sdk",return_value=Model), \
             patch("pipeline.train_detector.subprocess.check_output",side_effect=["fixture\n",""]):
            return run(config,"fixture")

    def test_success_records_actual_updates_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            result=self.exercise(root)
            self.assertEqual(result["state"],"completed")
            self.assertEqual(result["progress"],{"optimizer_steps":1,"epochs_completed":1})
            self.assertIn("finished_at",result)
            with self.assertRaises(FileExistsError):
                self.exercise(root)

    def test_failure_preserves_partial_progress(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with self.assertRaisesRegex(RuntimeError,"fixture interrupted"):
                self.exercise(root,fail=True)
            record=json.loads((root/"data/ml/runs/fixture/run.json").read_text())
            self.assertEqual(record["state"],"failed_or_interrupted")
            self.assertEqual(record["progress"]["optimizer_steps"],1)
            self.assertEqual(record["progress"]["epochs_completed"],1)


if __name__ == "__main__":
    unittest.main()
