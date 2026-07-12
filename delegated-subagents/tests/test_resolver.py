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


class ResolverTests(unittest.TestCase):
    def test_skill_treats_explicit_swe_request_as_delegation_opt_in(self):
        text = SKILL.read_text(encoding="utf-8")

        self.assertIn("launch subagents with SWE 1.7", text)
        self.assertIn("scripts/spawn-devin.sh", text)

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

    def test_code_small_prefers_qwen_before_mistral(self):
        with tempfile.TemporaryDirectory() as temp:
            fake = Path(temp) / "opencode"
            fake.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"$1\" == models ]]; then\n"
                "  printf '%s\\n' airouter/Qwen3.6 mistral/mistral-medium-latest\n"
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
            self.assertEqual(result.stdout.strip(), "airouter/Qwen3.6")

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


if __name__ == "__main__":
    unittest.main()
