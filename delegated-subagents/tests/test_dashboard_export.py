import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


SKILL_DIR = Path(__file__).resolve().parents[1]
DELEGATE_PATH = SKILL_DIR / "scripts" / "delegate.py"


def load_delegate():
    scripts_dir = SKILL_DIR / "scripts"
    sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location("delegated_dashboard", DELEGATE_PATH)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(scripts_dir))


class DashboardExportTests(unittest.TestCase):
    def test_snapshot_validator_rejects_extra_fields_and_inconsistent_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            delegate = load_delegate()
            snapshot = delegate.build_dashboard_snapshot(
                SimpleNamespace(state_root=Path(temp) / "runs", codex_session=None)
            )
            snapshot["prompt"] = "must not ship"
            with self.assertRaisesRegex(ValueError, "unexpected dashboard fields"):
                delegate.validate_dashboard_snapshot(snapshot)

            del snapshot["prompt"]
            snapshot["summary"]["attempts"] = 1
            with self.assertRaisesRegex(ValueError, "attempt totals"):
                delegate.validate_dashboard_snapshot(snapshot)

    def test_legacy_devin_usage_is_consistent_across_summary_groups_and_attempts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state_root = root / "runs"
            run_dir = state_root / "legacy"
            run_dir.mkdir(parents=True)
            (run_dir / "state.json").write_text(
                json.dumps(
                    {
                        "tool": "devin",
                        "task_type": "code-small",
                        "state": "worker-complete",
                        "created_at": "2026-07-19T10:00:00+00:00",
                        "attempts": [{"model": "swe-1.7", "log": str(run_dir / "attempt-1.log")}],
                    }
                ),
                encoding="utf-8",
            )
            (run_dir / "attempt-1.log").write_text("legacy", encoding="utf-8")
            (run_dir / "devin-export.json").write_text(
                json.dumps(
                    {
                        "final_metrics": {
                            "total_prompt_tokens": 400,
                            "total_completion_tokens": 100,
                            "total_cached_tokens": 300,
                        }
                    }
                ),
                encoding="utf-8",
            )
            output = root / "snapshot.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(DELEGATE_PATH),
                    "dashboard-export",
                    "--state-root",
                    str(state_root),
                    "--output",
                    str(output),
                ],
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            snapshot = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(snapshot["summary"]["delegated_total_tokens"], 500)
            self.assertEqual(snapshot["groups"][0]["total_tokens"], 500)
            self.assertEqual(snapshot["trends"][0]["total_tokens"], 500)
            self.assertTrue(snapshot["attempts"][0]["usage_available"])

    def test_export_is_sanitized_and_groups_dynamic_model_family(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state_root = root / "runs"
            run_dir = state_root / "sensitive-run-id"
            run_dir.mkdir(parents=True)
            state = {
                "run_id": "sensitive-run-id",
                "tool": "devin",
                "task_type": "code-small",
                "state": "worker-complete",
                "decision": "pending",
                "created_at": "2026-07-19T10:00:00+00:00",
                "repo": "/private/repository/path",
                "workdir": "/private/worktree/path",
                "prompt": "DO NOT EXPORT THIS PROMPT",
                "error": "DO NOT EXPORT RAW ERROR",
                "attempts": [
                    {
                        "model": "SWE-1.7 Max Beta",
                        "started_at": "2026-07-19T10:01:00+00:00",
                        "finished_at": "2026-07-19T10:02:00+00:00",
                        "session_id": "DO NOT EXPORT SESSION",
                        "log": "/private/transcript.log",
                        "usage": {
                            "source": "provider-reported",
                            "input_tokens": 1000,
                            "cached_input_tokens": 800,
                            "cache_read_tokens": 800,
                            "cache_write_tokens": 0,
                            "output_tokens": 200,
                            "reasoning_tokens": None,
                            "total_tokens": 1200,
                            "reported_cost_usd": None,
                            "billing_class": "free",
                            "actual_charge_usd": 0,
                            "error": "DO NOT EXPORT USAGE ERROR",
                        },
                    }
                ],
            }
            (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
            output = root / "snapshot.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(DELEGATE_PATH),
                    "dashboard-export",
                    "--state-root",
                    str(state_root),
                    "--output",
                    str(output),
                ],
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            snapshot = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(snapshot["schema_version"], 1)
            self.assertEqual(snapshot["summary"]["runs"], 1)
            self.assertEqual(snapshot["summary"]["delegated_total_tokens"], 1200)
            self.assertEqual(snapshot["coverage"], {"attempts": 1, "measured": 1, "unavailable": 0})
            self.assertEqual(snapshot["groups"][0]["model_family"], "swe-1.7")
            self.assertEqual(snapshot["groups"][0]["variant"], "max")
            self.assertEqual(snapshot["groups"][0]["actual_charge_usd_known"], 0)
            self.assertEqual(snapshot["groups"][0]["actual_charge_unknown_attempts"], 0)
            self.assertEqual(snapshot["attempts"][0]["raw_model"], "SWE-1.7 Max Beta")
            self.assertEqual(snapshot["attempts"][0]["result"], "worker-complete")

            serialized = json.dumps(snapshot)
            for forbidden in (
                "sensitive-run-id",
                "/private/repository/path",
                "/private/worktree/path",
                "DO NOT EXPORT THIS PROMPT",
                "DO NOT EXPORT RAW ERROR",
                "DO NOT EXPORT SESSION",
                "/private/transcript.log",
                "DO NOT EXPORT USAGE ERROR",
            ):
                self.assertNotIn(forbidden, serialized)

    def test_unsafe_categorical_values_are_replaced_not_exported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state_root = root / "runs"
            run_dir = state_root / "run"
            run_dir.mkdir(parents=True)
            state = {
                "tool": "devin\nPRIVATE_PROVIDER_VALUE",
                "task_type": "auroradocs-492-startup-debug",
                "state": "worker-complete\nPRIVATE_RESULT_VALUE",
                "created_at": "2026-07-19T10:00:00+00:00",
                "attempts": [
                    {
                        "model": "SWE-1.7 Max\nPRIVATE_MODEL_VALUE",
                        "usage": {"source": "unavailable", "total_tokens": None},
                    }
                ],
            }
            (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
            output = root / "snapshot.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(DELEGATE_PATH),
                    "dashboard-export",
                    "--state-root",
                    str(state_root),
                    "--output",
                    str(output),
                ],
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            snapshot = json.loads(output.read_text(encoding="utf-8"))
            serialized = json.dumps(snapshot)
            self.assertNotIn("PRIVATE_", serialized)
            self.assertNotIn("auroradocs", serialized)
            self.assertEqual(snapshot["attempts"][0]["provider"], "unknown")
            self.assertEqual(snapshot["attempts"][0]["raw_model"], "unknown")
            self.assertEqual(snapshot["attempts"][0]["task_type"], "unknown")
            self.assertEqual(snapshot["attempts"][0]["result"], "unknown")

    def test_empty_history_exports_a_valid_zero_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "snapshot.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(DELEGATE_PATH),
                    "dashboard-export",
                    "--state-root",
                    str(root / "missing-runs"),
                    "--output",
                    str(output),
                ],
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            snapshot = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(snapshot["summary"]["runs"], 0)
            self.assertEqual(snapshot["summary"]["capture_coverage"], None)
            self.assertEqual(snapshot["groups"], [])
            self.assertEqual(snapshot["attempts"], [])


if __name__ == "__main__":
    unittest.main()
