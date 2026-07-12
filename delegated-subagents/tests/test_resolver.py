import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
RESOLVER = SKILL_DIR / "scripts" / "resolve-model.sh"


class ResolverTests(unittest.TestCase):
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
