import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
DELEGATE_PATH = SCRIPTS_DIR / "delegate.py"


def load_delegate():
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        spec = importlib.util.spec_from_file_location("delegated_usage", DELEGATE_PATH)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPTS_DIR))


class UsageParsingTests(unittest.TestCase):
    def setUp(self):
        self.delegate = load_delegate()

    def test_devin_uses_exported_final_metrics(self):
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            (run_dir / "devin-export.json").write_text(
                json.dumps(
                    {
                        "final_metrics": {
                            "total_prompt_tokens": 1200,
                            "total_completion_tokens": 300,
                            "total_cached_tokens": 800,
                            "total_steps": 4,
                        }
                    }
                ),
                encoding="utf-8",
            )

            usage = self.delegate.capture_attempt_usage("devin", "swe-1.7", "", run_dir)

            self.assertEqual(usage["source"], "provider-reported")
            self.assertEqual(usage["input_tokens"], 1200)
            self.assertEqual(usage["cached_input_tokens"], 800)
            self.assertEqual(usage["output_tokens"], 300)
            self.assertEqual(usage["total_tokens"], 1500)
            self.assertEqual(usage["billing_class"], "free")
            self.assertEqual(usage["actual_charge_usd"], 0)

    def test_devin_model_identity_preserves_dynamic_variants(self):
        max_model = self.delegate.model_identity("devin", "SWE-1.7 Max Beta")
        lightning_model = self.delegate.model_identity("devin", "SWE 1_7 Lightning Beta")
        future_model = self.delegate.model_identity("devin", "swe-1.7 Horizon")

        self.assertEqual(
            max_model,
            {
                "raw_model": "SWE-1.7 Max Beta",
                "model_family": "swe-1.7",
                "display_name": "SWE-1.7 Max Beta",
                "variant": "max",
            },
        )
        self.assertEqual(lightning_model["model_family"], "swe-1.7")
        self.assertEqual(lightning_model["variant"], "lightning")
        self.assertEqual(future_model["model_family"], "swe-1.7")
        self.assertEqual(future_model["variant"], "horizon")

    def test_dynamic_swe_family_is_free_for_this_installation(self):
        self.assertEqual(self.delegate.billing_class("devin", "SWE-1.7 Max Beta"), "free")
        self.assertEqual(self.delegate.billing_class("devin", "SWE 1_7 Lightning Beta"), "free")
        self.assertEqual(self.delegate.billing_class("opencode", "swe-1.7-lookalike"), "unknown")

    def test_devin_family_resolution_prefers_explicit_configured_then_observed(self):
        observed = ["SWE-1.7 Lightning Beta", "SWE-1.7 Max Beta"]

        self.assertEqual(
            self.delegate.resolve_devin_model("SWE-1.7 Horizon", "SWE-1.7 Max Beta", observed),
            "SWE-1.7 Horizon",
        )
        self.assertEqual(
            self.delegate.resolve_devin_model("swe-1.7", "SWE-1.7 Max Beta", observed),
            "SWE-1.7 Max Beta",
        )
        self.assertEqual(
            self.delegate.resolve_devin_model("swe-1.7", None, observed),
            "SWE-1.7 Lightning Beta",
        )
        self.assertEqual(self.delegate.resolve_devin_model("swe-1.7", None, []), "swe-1.7")

    def test_opencode_sums_json_message_usage_and_preserves_nominal_cost(self):
        payload = {
            "role": "assistant",
            "providerID": "airouter",
            "modelID": "Qwen3.6",
            "cost": 0.02,
            "tokens": {
                "total": 28617,
                "input": 174,
                "output": 462,
                "reasoning": 13,
                "cache": {"write": 0, "read": 27968},
            },
        }

        usage = self.delegate.capture_attempt_usage(
            "opencode", "airouter/Qwen3.6", json.dumps(payload), Path("/missing")
        )

        self.assertEqual(usage["total_tokens"], 28617)
        self.assertEqual(usage["cache_read_tokens"], 27968)
        self.assertEqual(usage["reasoning_tokens"], 13)
        self.assertEqual(usage["reported_cost_usd"], 0.02)
        self.assertEqual(usage["billing_class"], "free")
        self.assertEqual(usage["actual_charge_usd"], 0)

    def test_cursor_without_usage_is_explicitly_unavailable(self):
        usage = self.delegate.capture_attempt_usage(
            "cursor", "composer-2.5", json.dumps({"type": "result", "text": "done"}), Path("/missing")
        )

        self.assertEqual(usage["source"], "unavailable")
        self.assertIsNone(usage["total_tokens"])
        self.assertEqual(usage["billing_class"], "subscription")
        self.assertIsNone(usage["actual_charge_usd"])

    def test_cursor_nested_usage_is_counted_once(self):
        usage = self.delegate.capture_attempt_usage(
            "cursor",
            "composer-2.5",
            json.dumps(
                {
                    "type": "result",
                    "usage": {
                        "inputTokens": 900,
                        "cachedInputTokens": 600,
                        "outputTokens": 100,
                        "totalTokens": 1000,
                    },
                }
            ),
            Path("/missing"),
        )

        self.assertEqual(usage["input_tokens"], 900)
        self.assertEqual(usage["cached_input_tokens"], 600)
        self.assertEqual(usage["output_tokens"], 100)
        self.assertEqual(usage["total_tokens"], 1000)

    def test_cursor_report_text_excludes_tool_output(self):
        valid = """STATUS: success
MODEL: composer-2.5-fast
TASK_TYPE: scout
REPO: /tmp/repo
ACCEPTANCE_CRITERIA:
- [pass] inspect -> heading found
CLOSURE_RECOMMENDATION:
not-applicable
"""
        misleading_tool_output = """STATUS: failed
MODEL: wrong/model
TASK_TYPE: debug
REPO: /tmp/other
ACCEPTANCE_CRITERIA:
- [fail] tests -> missing
CLOSURE_RECOMMENDATION:
needs-fix
"""
        log = "\n".join(
            (
                json.dumps(
                    {
                        "type": "tool_call",
                        "subtype": "completed",
                        "result": {"text": misleading_tool_output},
                    }
                ),
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {"role": "assistant", "content": [{"type": "text", "text": "Preparing report."}]},
                    }
                ),
                json.dumps(
                    {
                        "type": "tool_call",
                        "subtype": "completed",
                        "tool_call": {"createPlanToolCall": {"args": {"plan": valid}}},
                    }
                ),
                json.dumps({"type": "result", "subtype": "success", "result": "Preparing report."}),
            )
        )

        extracted = self.delegate.report_text_from_log("cursor", log)
        report = self.delegate.parse_report(extracted, expected_model="composer-2.5-fast")

        self.assertTrue(report.valid, report.errors)
        self.assertEqual(report.decision, "worker-complete")

    def test_codex_delta_uses_snapshots_surrounding_run_window(self):
        with tempfile.TemporaryDirectory() as temp:
            rollout = Path(temp) / "rollout.jsonl"
            before = {
                "timestamp": "2026-07-19T10:00:00+00:00",
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {
                            "input_tokens": 800,
                            "cached_input_tokens": 500,
                            "cache_write_input_tokens": 0,
                            "output_tokens": 150,
                            "reasoning_output_tokens": 50,
                            "total_tokens": 1000,
                        }
                    },
                },
            }
            after = {
                "timestamp": "2026-07-19T10:05:00+00:00",
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {
                            "input_tokens": 1300,
                            "cached_input_tokens": 750,
                            "cache_write_input_tokens": 0,
                            "output_tokens": 220,
                            "reasoning_output_tokens": 80,
                            "total_tokens": 1600,
                        }
                    },
                },
            }
            rollout.write_text("\n".join((json.dumps(before), json.dumps(after))) + "\n", encoding="utf-8")

            usage = self.delegate.codex_usage_delta(
                rollout,
                "2026-07-19T10:01:00+00:00",
                "2026-07-19T10:04:00+00:00",
            )

            self.assertEqual(usage["source"], "codex-session-delta")
            self.assertEqual(usage["input_tokens"], 500)
            self.assertEqual(usage["output_tokens"], 70)
            self.assertEqual(usage["reasoning_tokens"], 30)
            self.assertEqual(usage["total_tokens"], 600)


class UsageReportTests(unittest.TestCase):
    def test_report_reads_legacy_devin_export_without_mutating_state(self):
        with tempfile.TemporaryDirectory() as temp:
            state_root = Path(temp) / "runs"
            run_dir = state_root / "legacy-devin"
            run_dir.mkdir(parents=True)
            original = {
                "run_id": "legacy-devin",
                "tool": "devin",
                "task_type": "code-small",
                "attempts": [{"model": "swe-1.7", "log": str(run_dir / "attempt-1.log")}],
            }
            (run_dir / "state.json").write_text(json.dumps(original), encoding="utf-8")
            (run_dir / "attempt-1.log").write_text("legacy text output", encoding="utf-8")
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

            result = subprocess.run(
                [sys.executable, str(DELEGATE_PATH), "usage-report", "--state-root", str(state_root), "--json"],
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["external"]["total_tokens"], 500)
            self.assertEqual(report["coverage"], {"attempts": 1, "measured": 1, "unavailable": 0})
            self.assertEqual(report["groups"][0]["raw_model"], "swe-1.7")
            self.assertEqual(report["groups"][0]["model_family"], "swe-1.7")
            self.assertIsNone(report["groups"][0]["variant"])
            self.assertEqual(json.loads((run_dir / "state.json").read_text()), original)

    def test_report_aggregates_external_usage_and_optional_codex_share(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state_root = root / "runs"
            run_dir = state_root / "run-1"
            run_dir.mkdir(parents=True)
            state = {
                "run_id": "run-1",
                "tool": "opencode",
                "task_type": "review",
                "created_at": "2026-07-19T10:01:00+00:00",
                "updated_at": "2026-07-19T12:00:00+00:00",
                "attempts": [
                    {
                        "model": "opencode/test-free",
                        "started_at": "2026-07-19T10:01:00+00:00",
                        "finished_at": "2026-07-19T10:04:00+00:00",
                        "usage": {
                            "source": "provider-reported",
                            "input_tokens": 700,
                            "cached_input_tokens": 300,
                            "cache_write_tokens": 0,
                            "output_tokens": 200,
                            "reasoning_tokens": 100,
                            "total_tokens": 1000,
                            "reported_cost_usd": 0.01,
                            "billing_class": "free",
                            "actual_charge_usd": 0,
                        },
                    },
                    {"model": "opencode/unknown-free", "usage": {"source": "unavailable", "total_tokens": None}},
                ],
            }
            (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
            rollout = root / "rollout.jsonl"
            snapshots = []
            for timestamp, total in (("2026-07-19T10:00:00+00:00", 1000), ("2026-07-19T10:05:00+00:00", 1500)):
                snapshots.append(
                    {
                        "timestamp": timestamp,
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "total_token_usage": {
                                    "input_tokens": total,
                                    "cached_input_tokens": 0,
                                    "cache_write_input_tokens": 0,
                                    "output_tokens": 0,
                                    "reasoning_output_tokens": 0,
                                    "total_tokens": total,
                                }
                            },
                        },
                    }
                )
            rollout.write_text("\n".join(json.dumps(item) for item in snapshots) + "\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(DELEGATE_PATH),
                    "usage-report",
                    "--state-root",
                    str(state_root),
                    "--codex-session",
                    str(rollout),
                    "--json",
                ],
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["external"]["total_tokens"], 1000)
            self.assertEqual(report["coverage"], {"attempts": 2, "measured": 1, "unavailable": 1})
            self.assertEqual(report["codex"]["total_tokens"], 500)
            self.assertAlmostEqual(report["delegated_share"], 2 / 3, places=4)
            self.assertEqual(report["groups"][0]["billing_class"], "free")
            self.assertEqual(report["groups"][0]["date"], "2026-07-19")


if __name__ == "__main__":
    unittest.main()
