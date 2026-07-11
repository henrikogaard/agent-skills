import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_PATH = SKILL_DIR / "scripts" / "runtime.py"


def load_runtime():
    spec = importlib.util.spec_from_file_location("delegated_runtime", RUNTIME_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ReportParsingTests(unittest.TestCase):
    def setUp(self):
        self.runtime = load_runtime()

    def test_rejects_exit_zero_without_structured_report(self):
        report = self.runtime.parse_report("looks good", expected_model="provider/model")
        self.assertFalse(report.valid)
        self.assertEqual(report.decision, "rejected")

    def test_blocked_report_is_not_success(self):
        text = """STATUS: blocked
MODEL: provider/model
TASK_TYPE: debug
REPO: /tmp/repo
ACCEPTANCE_CRITERIA:
- [unknown] reproduce issue -> dependency unavailable
CLOSURE_RECOMMENDATION:
blocked
"""
        report = self.runtime.parse_report(text, expected_model="provider/model")
        self.assertTrue(report.valid)
        self.assertEqual(report.status, "blocked")
        self.assertEqual(report.decision, "needs-follow-up")

    def test_success_with_failed_acceptance_criterion_is_rejected(self):
        text = """STATUS: success
MODEL: provider/model
TASK_TYPE: closure-validation
REPO: /tmp/repo
ACCEPTANCE_CRITERIA:
- [pass] tests -> 12 passed
- [fail] docs -> missing
CLOSURE_RECOMMENDATION:
ready-for-review
"""
        report = self.runtime.parse_report(text, expected_model="provider/model")
        self.assertTrue(report.valid)
        self.assertEqual(report.decision, "rejected")

    def test_model_mismatch_is_rejected(self):
        text = """STATUS: success
MODEL: another/model
TASK_TYPE: scout
REPO: /tmp/repo
ACCEPTANCE_CRITERIA:
- [pass] inspect -> complete
CLOSURE_RECOMMENDATION:
not-applicable
"""
        report = self.runtime.parse_report(text, expected_model="provider/model")
        self.assertFalse(report.valid)
        self.assertEqual(report.decision, "rejected")


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.runtime = load_runtime()

    def test_code_output_not_found_is_not_provider_failure(self):
        log = "FAIL test_lookup: expected record, got not found\nHTTP 500 assertion failed"
        self.assertFalse(self.runtime.is_availability_failure(log, return_code=1))

    def test_explicit_provider_unavailable_is_provider_failure(self):
        log = "ProviderError: model provider unavailable (HTTP 503 capacity exhausted)"
        self.assertTrue(self.runtime.is_availability_failure(log, return_code=1))

    def test_model_chain_is_deduplicated(self):
        models = self.runtime.dedupe(["a/model", "a/model", "b/model"])
        self.assertEqual(models, ["a/model", "b/model"])

    def test_model_history_ranks_proven_models_but_preserves_explicit_first(self):
        with tempfile.TemporaryDirectory() as root:
            history = Path(root) / "history.jsonl"
            records = []
            records.extend({"model": "a/model", "task_type": "review", "result": "failed"} for _ in range(3))
            records.extend({"model": "b/model", "task_type": "review", "result": "accepted"} for _ in range(3))
            history.write_text("\n".join(json.dumps(record) for record in records) + "\n")
            ranked = self.runtime.rank_models_by_history(
                ["a/model", "b/model", "c/model"], history, "review", preserve_first=False
            )
            pinned = self.runtime.rank_models_by_history(
                ["a/model", "b/model", "c/model"], history, "review", preserve_first=True
            )
            self.assertEqual(ranked[0], "b/model")
            self.assertEqual(pinned[0], "a/model")


class StateAndProcessTests(unittest.TestCase):
    def setUp(self):
        self.runtime = load_runtime()

    def test_run_directories_are_unique(self):
        with tempfile.TemporaryDirectory() as root:
            first = self.runtime.create_run_dir(Path(root), "opencode")
            second = self.runtime.create_run_dir(Path(root), "opencode")
            self.assertNotEqual(first, second)
            self.assertTrue(first.is_dir())
            self.assertTrue(second.is_dir())

    def test_state_write_is_valid_json(self):
        with tempfile.TemporaryDirectory() as root:
            state_path = Path(root) / "state.json"
            self.runtime.atomic_write_json(state_path, {"state": "running", "attempts": []})
            self.assertEqual(json.loads(state_path.read_text())["state"], "running")
            self.assertFalse((Path(root) / "state.json.tmp").exists())

    def test_process_identity_rejects_reused_or_changed_process(self):
        process = subprocess.Popen(["sleep", "30"], start_new_session=True)
        try:
            identity = self.runtime.capture_process_identity(process.pid)
            self.assertIsNotNone(identity)
            altered = dict(identity)
            altered["start_signature"] = "different"
            self.assertFalse(self.runtime.process_matches(altered))
            self.assertTrue(self.runtime.process_matches(identity))
        finally:
            os.killpg(process.pid, 15)
            process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
