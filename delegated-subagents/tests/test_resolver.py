import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
RESOLVER = SKILL_DIR / "scripts" / "resolve-model.sh"
SKILL = SKILL_DIR / "SKILL.md"
DEVIN_SPAWN = SKILL_DIR / "scripts" / "spawn-devin.sh"
PROMPT_TEMPLATE = SKILL_DIR / "references" / "subagent-prompt-template.md"
OPENAI_METADATA = SKILL_DIR / "agents" / "openai.yaml"


class ResolverTests(unittest.TestCase):
    def test_worker_prompt_requires_rtk_when_available(self):
        text = PROMPT_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("Read the applicable `AGENTS.md` instructions", text)
        self.assertIn("When `rtk` is available, prefix every shell command with `rtk`", text)

    def test_skill_treats_explicit_swe_request_as_delegation_opt_in(self):
        text = SKILL.read_text(encoding="utf-8")

        self.assertIn("launch subagents with SWE 1.7", text)
        self.assertIn("scripts/spawn-devin.sh", text)

    def test_skill_is_manual_only(self):
        skill_text = SKILL.read_text(encoding="utf-8")
        metadata = OPENAI_METADATA.read_text(encoding="utf-8")

        self.assertIn("manual-only", skill_text.lower())
        self.assertIn("allow_implicit_invocation: false", metadata)

    def test_skill_has_complexity_gate_and_weighted_model_matrix(self):
        text = SKILL.read_text(encoding="utf-8")

        self.assertIn("## Complexity Gate", text)
        self.assertIn("Native Codex GPT subagent", text)
        self.assertIn("## Weighted External Model Matrix", text)
        self.assertIn("Devin/SWE 1.7", text)

    def test_devin_runner_defaults_to_one_attempt(self):
        text = DEVIN_SPAWN.read_text(encoding="utf-8")

        self.assertIn('MAX_ATTEMPTS="${SUBAGENT_MAX_ATTEMPTS:-1}"', text)

    def test_local_task_type_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            fake = Path(temp) / "opencode"
            fake.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy()
            env["PATH"] = f"{temp}{os.pathsep}{env['PATH']}"

            result = subprocess.run(
                [str(RESOLVER), "--task", "local"],
                text=True,
                capture_output=True,
                env=env,
                timeout=10,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("unknown task type: local", result.stderr)

    def test_code_small_prefers_free_model_before_paid_fallbacks(self):
        with tempfile.TemporaryDirectory() as temp:
            fake = Path(temp) / "opencode"
            fake.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"$1\" == models ]]; then\n"
                "  printf '%s\\n' opencode/north-mini-code-free airouter/Qwen3.6 mistral/mistral-medium-latest\n"
                "fi\n"
            )
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy()
            env["PATH"] = f"{temp}{os.pathsep}{env['PATH']}"

            result = subprocess.run(
                [str(RESOLVER), "--task", "code-small"],
                text=True,
                capture_output=True,
                env=env,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "opencode/north-mini-code-free")

    def test_mistral_requires_an_explicit_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            fake = Path(temp) / "opencode"
            fake.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"$1\" == models ]]; then\n"
                "  printf '%s\\n' opencode/north-mini-code-free mistral/mistral-medium-latest\n"
                "fi\n",
                encoding="utf-8",
            )
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy()
            env["PATH"] = f"{temp}{os.pathsep}{env['PATH']}"

            default_result = subprocess.run(
                [str(RESOLVER), "--task", "debug", "--all"],
                text=True,
                capture_output=True,
                env=env,
                timeout=10,
            )
            mistral_result = subprocess.run(
                [str(RESOLVER), "--task", "debug", "--policy", "mistral"],
                text=True,
                capture_output=True,
                env=env,
                timeout=10,
            )

            self.assertEqual(default_result.returncode, 0, default_result.stderr)
            self.assertNotIn("mistral/mistral-medium-latest", default_result.stdout)
            self.assertEqual(mistral_result.returncode, 0, mistral_result.stderr)
            self.assertEqual(mistral_result.stdout.strip(), "mistral/mistral-medium-latest")

    def test_explicit_hint_is_not_duplicated_in_fallback_chain(self):
        with tempfile.TemporaryDirectory() as temp:
            fake = Path(temp) / "opencode"
            fake.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"$1\" == models ]]; then\n"
                "  printf '%s\\n' opencode/deepseek-v4-flash-free airouter/DeepSeek-V4-Flash\n"
                "fi\n"
            )
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy()
            env["PATH"] = f"{temp}{os.pathsep}{env['PATH']}"

            result = subprocess.run(
                [
                    str(RESOLVER),
                    "--task",
                    "scout",
                    "--hint",
                    "opencode/deepseek-v4-flash-free",
                    "--all",
                ],
                text=True,
                capture_output=True,
                env=env,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            models = result.stdout.splitlines()
            self.assertEqual(models.count("opencode/deepseek-v4-flash-free"), 1)

    def test_unknown_free_model_is_seen_but_not_used_for_code_without_probe(self):
        with tempfile.TemporaryDirectory() as temp:
            fake = Path(temp) / "opencode"
            fake.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"$1\" == models ]]; then\n"
                "  printf '%s\\n' opencode/brand-new-free airouter/Qwen3.6\n"
                "fi\n",
                encoding="utf-8",
            )
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy()
            env["PATH"] = f"{temp}{os.pathsep}{env['PATH']}"

            result = subprocess.run(
                [str(RESOLVER), "--task", "code-small", "--all"],
                text=True,
                capture_output=True,
                env=env,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("opencode/brand-new-free", result.stdout)
            self.assertIn("probe-only", result.stderr)

    def test_review_uses_live_usable_free_model_outside_old_static_chain(self):
        with tempfile.TemporaryDirectory() as temp:
            fake = Path(temp) / "opencode"
            fake.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"$1\" == models ]]; then\n"
                "  printf '%s\\n' opencode/hy3-free\n"
                "fi\n",
                encoding="utf-8",
            )
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy()
            env["PATH"] = f"{temp}{os.pathsep}{env['PATH']}"
            env["SUBAGENT_STATE_ROOT"] = str(Path(temp) / "state" / "runs")

            result = subprocess.run(
                [str(RESOLVER), "--task", "review"],
                text=True,
                capture_output=True,
                env=env,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "opencode/hy3-free")


if __name__ == "__main__":
    unittest.main()
