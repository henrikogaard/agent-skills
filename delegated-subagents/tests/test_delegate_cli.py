import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
DELEGATE = SKILL_DIR / "scripts" / "delegate.py"


def write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def valid_report(model: str, status: str = "success") -> str:
    return textwrap.dedent(
        f"""\
        STATUS: {status}
        MODEL: {model}
        TASK_TYPE: scout
        REPO: /tmp/repo
        SUMMARY:
        - inspected
        FILES_INSPECTED:
        - README.md
        FILES_CHANGED:
        - none
        COMMANDS_RUN:
        - check -> passed
        VERIFICATION:
        - report -> passed
        ACCEPTANCE_CRITERIA:
        - [pass] inspect repository -> evidence recorded
        CLOSURE_RECOMMENDATION:
        not-applicable
        RISKS_OR_BLOCKERS:
        - none
        FOLLOW_UPS:
        - none
        """
    )


class DelegateCliTests(unittest.TestCase):
    def run_delegate(self, root: Path, fake_bin: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        prompt = root / "prompt.txt"
        prompt.write_text("PRIVATE PROMPT CONTENT", encoding="utf-8")
        env = os.environ.copy()
        env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
        return subprocess.run(
            [
                sys.executable,
                str(DELEGATE),
                "run",
                "--tool",
                "opencode",
                "--task",
                "scout",
                "--prompt-file",
                str(prompt),
                "--workdir",
                str(root),
                "--models",
                "fake/one,fake/two",
                "--state-root",
                str(root / "state"),
                "--isolation",
                "none",
                "--timeout",
                "8",
                "--idle",
                "4",
                "--poll",
                "0.1",
                *extra,
            ],
            text=True,
            capture_output=True,
            env=env,
            timeout=20,
        )

    def test_success_requires_valid_report_and_hides_prompt_from_argv(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            args_file = root / "args.json"
            report = valid_report("fake/one")
            write_executable(
                fake_bin / "opencode",
                f"#!/usr/bin/env python3\nimport json,sys\njson.dump(sys.argv[1:], open({str(args_file)!r}, 'w'))\nprint({report!r})\n",
            )

            result = self.run_delegate(root, fake_bin)

            self.assertEqual(result.returncode, 0, result.stderr)
            run_dir = Path(result.stdout.strip())
            state = json.loads((run_dir / "state.json").read_text())
            self.assertEqual(state["state"], "accepted")
            self.assertEqual(state["decision"], "accepted")
            args = json.loads(args_file.read_text())
            self.assertNotIn("PRIVATE PROMPT CONTENT", args)
            self.assertIn("--auto", args)
            self.assertIn("--file", args)

    def test_opencode_worker_disables_unneeded_mcp_tools(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            config_file = root / "opencode-config.json"
            report = valid_report("fake/one")
            write_executable(
                fake_bin / "opencode",
                f"#!/usr/bin/env python3\nimport os\nopen({str(config_file)!r}, 'w').write(os.environ.get('OPENCODE_CONFIG_CONTENT', ''))\nprint({report!r})\n",
            )

            result = self.run_delegate(root, fake_bin)

            self.assertEqual(result.returncode, 0, result.stderr)
            config = json.loads(config_file.read_text())
            self.assertEqual(
                config["tools"],
                {"infomaniak_*": False, "cua-driver_*": False},
            )

    def test_explicit_mcp_override_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            config_file = root / "opencode-config.json"
            report = valid_report("fake/one")
            write_executable(
                fake_bin / "opencode",
                f"#!/usr/bin/env python3\nimport os\nopen({str(config_file)!r}, 'w').write(os.environ.get('OPENCODE_CONFIG_CONTENT', ''))\nprint({report!r})\n",
            )
            original = os.environ.get("OPENCODE_CONFIG_CONTENT")
            os.environ["OPENCODE_CONFIG_CONTENT"] = json.dumps({"tools": {"infomaniak_*": True}})
            try:
                result = self.run_delegate(root, fake_bin)
            finally:
                if original is None:
                    os.environ.pop("OPENCODE_CONFIG_CONTENT", None)
                else:
                    os.environ["OPENCODE_CONFIG_CONTENT"] = original

            self.assertEqual(result.returncode, 0, result.stderr)
            config = json.loads(config_file.read_text())
            self.assertEqual(config["tools"]["infomaniak_*"], True)
            self.assertEqual(config["tools"]["cua-driver_*"], False)

    def test_provider_failure_falls_back_to_next_model(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            report = valid_report("fake/two")
            write_executable(
                fake_bin / "opencode",
                f"""#!/usr/bin/env python3
import sys
model = sys.argv[sys.argv.index('-m') + 1]
if model == 'fake/one':
    print('ProviderError: model provider unavailable (HTTP 503 capacity exhausted)')
    raise SystemExit(1)
print({report!r})
""",
            )

            result = self.run_delegate(root, fake_bin, "--max-attempts", "2")

            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads((Path(result.stdout.strip()) / "state.json").read_text())
            self.assertEqual([attempt["model"] for attempt in state["attempts"]], ["fake/one", "fake/two"])
            self.assertEqual(state["attempts"][0]["state"], "provider-unavailable")
            self.assertEqual(state["attempts"][1]["state"], "accepted")

    def test_default_attempt_limit_stops_after_one_provider_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            write_executable(
                fake_bin / "opencode",
                "#!/usr/bin/env python3\n"
                "print('ProviderError: model provider unavailable (HTTP 503 capacity exhausted)')\n"
                "raise SystemExit(1)\n",
            )

            result = self.run_delegate(root, fake_bin)

            self.assertEqual(result.returncode, 124, result.stderr)
            state = json.loads((Path(result.stdout.strip()) / "state.json").read_text())
            self.assertEqual(len(state["attempts"]), 1)
            self.assertEqual(state["attempts"][0]["state"], "provider-unavailable")

    def test_crashed_process_is_replaced(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            report = valid_report("fake/two")
            write_executable(
                fake_bin / "opencode",
                f"""#!/usr/bin/env python3
import os,signal,sys
model = sys.argv[sys.argv.index('-m') + 1]
if model == 'fake/one':
    os.kill(os.getpid(), signal.SIGKILL)
print({report!r})
""",
            )

            result = self.run_delegate(root, fake_bin, "--max-attempts", "2")

            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads((Path(result.stdout.strip()) / "state.json").read_text())
            self.assertEqual(state["attempts"][0]["state"], "died")
            self.assertEqual(state["attempts"][1]["state"], "accepted")

    def test_exit_zero_blocked_report_needs_follow_up(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            report = valid_report("fake/one", status="blocked").replace("[pass]", "[unknown]")
            write_executable(fake_bin / "opencode", f"#!/usr/bin/env python3\nprint({report!r})\n")

            result = self.run_delegate(root, fake_bin)

            self.assertEqual(result.returncode, 3, result.stderr)
            state = json.loads((Path(result.stdout.strip()) / "state.json").read_text())
            self.assertEqual(state["state"], "needs-follow-up")

    def test_timeout_kills_process_group_and_records_attempt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            child_file = root / "child.pid"
            write_executable(
                fake_bin / "opencode",
                f"""#!/usr/bin/env python3
import subprocess,time
p = subprocess.Popen(['sleep', '30'])
open({str(child_file)!r}, 'w').write(str(p.pid))
print('started', flush=True)
time.sleep(30)
""",
            )

            result = self.run_delegate(root, fake_bin, "--timeout", "1", "--idle", "10", "--max-attempts", "1")

            self.assertEqual(result.returncode, 124, result.stderr)
            run_dir = Path(result.stdout.strip())
            state = json.loads((run_dir / "state.json").read_text())
            self.assertEqual(state["state"], "timeout")
            child_pid = int(child_file.read_text())
            with self.assertRaises(ProcessLookupError):
                os.kill(child_pid, 0)

    def test_successful_agent_cannot_leave_child_process_running(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            child_file = root / "child.pid"
            report = valid_report("fake/one")
            write_executable(
                fake_bin / "opencode",
                f"""#!/usr/bin/env python3
import subprocess
p = subprocess.Popen(['sleep', '30'])
open({str(child_file)!r}, 'w').write(str(p.pid))
print({report!r})
""",
            )

            result = self.run_delegate(root, fake_bin, "--max-attempts", "1")

            self.assertEqual(result.returncode, 0, result.stderr)
            child_pid = int(child_file.read_text())
            deadline = time.time() + 3
            while time.time() < deadline:
                try:
                    os.kill(child_pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.05)
            with self.assertRaises(ProcessLookupError):
                os.kill(child_pid, 0)


if __name__ == "__main__":
    unittest.main()
