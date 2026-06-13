import json
import tempfile
import unittest
from pathlib import Path

from android_adk_rl_env.core.artifacts import ArtifactWriter


class ArtifactTest(unittest.TestCase):
    def test_artifact_writer_creates_required_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            writer = ArtifactWriter(root=tmp, run_id="run_test")
            writer.write_config({"backend": "adb"})
            writer.append_rollout({"step": 1})
            writer.append_reward({"reward": 1.0})
            writer.write_replay([{"task_id": "t1", "reward": 1.0, "exact_success": True}])
            summary = writer.write_summary("adb", "scripted", [{"reward": 1.0, "exact_success": True}], "start", "end")
            writer.write_device_info({})
            writer.write_apk_info({})
            writer.write_logcat("")
            writer.ensure_required_files()
            run_dir = Path(tmp) / "run_test"
            for name in [
                "config.json",
                "summary.json",
                "rollout.jsonl",
                "reward_trace.jsonl",
                "final_screen.png",
                "emulator_run.mp4",
                "replay.html",
                "logcat.txt",
                "device_info.json",
                "apk_info.json",
            ]:
                self.assertTrue((run_dir / name).exists(), name)
            self.assertEqual(json.loads((run_dir / "summary.json").read_text())["success_rate"], summary["success_rate"])
            self.assertIn("exact_success_rate", summary)
            self.assertIn("benchmark_alignment", summary)


if __name__ == "__main__":
    unittest.main()
