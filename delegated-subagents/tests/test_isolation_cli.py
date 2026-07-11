import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
DELEGATE = SKILL_DIR / "scripts" / "delegate.py"


def write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def init_repo(path: Path) -> None:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True)
    (path / "README.md").write_text("test\n")
    subprocess.run(["git", "-C", str(path), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "initial"], check=True)


class IsolationTests(unittest.TestCase):
    def test_edit_outside_manifest_allowed_paths_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            init_repo(repo)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            write_executable(
                fake_bin / "opencode",
                """#!/usr/bin/env python3
import pathlib,sys
model = sys.argv[sys.argv.index('-m') + 1]
workdir = pathlib.Path(sys.argv[sys.argv.index('--dir') + 1])
(workdir / 'outside.txt').write_text('changed')
print(f'''STATUS: success
MODEL: {model}
TASK_TYPE: code-small
REPO: {workdir}
ACCEPTANCE_CRITERIA:
- [pass] bounded edit -> complete
CLOSURE_RECOMMENDATION:
ready-for-review''')
""",
            )
            prompt = root / "prompt.txt"
            prompt.write_text("edit only src")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "goal": "bounded edit",
                        "acceptance_criteria": ["bounded edit"],
                        "allowed_paths": ["src/"],
                    }
                )
            )
            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
            result = subprocess.run(
                [
                    sys.executable,
                    str(DELEGATE),
                    "run",
                    "--tool",
                    "opencode",
                    "--task",
                    "code-small",
                    "--prompt-file",
                    str(prompt),
                    "--manifest",
                    str(manifest),
                    "--workdir",
                    str(repo),
                    "--models",
                    "fake/model",
                    "--permission-profile",
                    "edit",
                    "--state-root",
                    str(root / "state"),
                    "--worktree-root",
                    str(root / "worktrees"),
                    "--poll",
                    "0.1",
                ],
                text=True,
                capture_output=True,
                env=env,
                timeout=15,
            )
            self.assertEqual(result.returncode, 4, result.stderr)
            state = json.loads((Path(result.stdout.strip()) / "state.json").read_text())
            self.assertEqual(state["out_of_scope_paths"], ["outside.txt"])

    def test_read_only_model_that_edits_is_rejected_in_managed_worktree(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            init_repo(repo)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            write_executable(
                fake_bin / "opencode",
                """#!/usr/bin/env python3
import pathlib,sys
model = sys.argv[sys.argv.index('-m') + 1]
workdir = pathlib.Path(sys.argv[sys.argv.index('--dir') + 1])
(workdir / 'unauthorized.txt').write_text('changed')
print(f'''STATUS: success
MODEL: {model}
TASK_TYPE: scout
REPO: {workdir}
ACCEPTANCE_CRITERIA:
- [pass] inspect -> complete
CLOSURE_RECOMMENDATION:
not-applicable''')
""",
            )
            prompt = root / "prompt.txt"
            prompt.write_text("inspect only")
            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
            result = subprocess.run(
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
                    str(repo),
                    "--models",
                    "fake/model",
                    "--permission-profile",
                    "read-only",
                    "--state-root",
                    str(root / "state"),
                    "--worktree-root",
                    str(root / "worktrees"),
                    "--poll",
                    "0.1",
                ],
                text=True,
                capture_output=True,
                env=env,
                timeout=15,
            )
            self.assertEqual(result.returncode, 4, result.stderr)
            state = json.loads((Path(result.stdout.strip()) / "state.json").read_text())
            self.assertEqual(state["state"], "rejected")
            self.assertEqual(state["policy_violation"], "read-only subagent changed files")
            self.assertIn("unauthorized.txt", state["git_after"])

    def test_edit_profile_uses_managed_worktree_and_records_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            init_repo(repo)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            write_executable(
                fake_bin / "opencode",
                """#!/usr/bin/env python3
import sys
model = sys.argv[sys.argv.index('-m') + 1]
workdir = sys.argv[sys.argv.index('--dir') + 1]
print(f'''STATUS: success
MODEL: {model}
TASK_TYPE: code-small
REPO: {workdir}
ACCEPTANCE_CRITERIA:
- [pass] change is isolated -> worktree used
CLOSURE_RECOMMENDATION:
ready-for-review''')
""",
            )
            prompt = root / "prompt.txt"
            prompt.write_text("task")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "issue_url": "https://example.invalid/issues/1",
                        "goal": "Make the bounded change",
                        "acceptance_criteria": ["change is isolated"],
                    }
                )
            )
            state_root = root / "state"
            worktree_root = root / "worktrees"
            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"

            result = subprocess.run(
                [
                    sys.executable,
                    str(DELEGATE),
                    "run",
                    "--tool",
                    "opencode",
                    "--task",
                    "code-small",
                    "--prompt-file",
                    str(prompt),
                    "--manifest",
                    str(manifest),
                    "--workdir",
                    str(repo),
                    "--models",
                    "fake/model",
                    "--permission-profile",
                    "edit",
                    "--state-root",
                    str(state_root),
                    "--worktree-root",
                    str(worktree_root),
                    "--poll",
                    "0.1",
                ],
                text=True,
                capture_output=True,
                env=env,
                timeout=15,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads((Path(result.stdout.strip()) / "state.json").read_text())
            self.assertEqual(state["repo"], str(repo.resolve()))
            self.assertNotEqual(state["workdir"], str(repo.resolve()))
            self.assertTrue(Path(state["workdir"]).is_dir())
            self.assertEqual(state["manifest"]["acceptance_criteria"], ["change is isolated"])
            branch = subprocess.check_output(
                ["git", "-C", state["workdir"], "branch", "--show-current"], text=True
            ).strip()
            self.assertTrue(branch.startswith("codex/delegated/"))

    def test_devin_edit_profile_is_noninteractive_and_sandboxed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            args_file = root / "args.json"
            write_executable(
                fake_bin / "devin",
                f"""#!/usr/bin/env python3
import json,sys
json.dump(sys.argv[1:], open({str(args_file)!r}, 'w'))
model = sys.argv[sys.argv.index('--model') + 1]
print(f'''STATUS: success
MODEL: {{model}}
TASK_TYPE: long-autonomous
REPO: {root}
ACCEPTANCE_CRITERIA:
- [pass] bounded task -> complete
CLOSURE_RECOMMENDATION:
ready-for-review''')
""",
            )
            prompt = root / "prompt.txt"
            prompt.write_text("PRIVATE DEVIN PROMPT")
            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
            result = subprocess.run(
                [
                    sys.executable,
                    str(DELEGATE),
                    "run",
                    "--tool",
                    "devin",
                    "--task",
                    "long-autonomous",
                    "--prompt-file",
                    str(prompt),
                    "--workdir",
                    str(root),
                    "--models",
                    "swe-1.7",
                    "--permission-profile",
                    "edit",
                    "--isolation",
                    "none",
                    "--state-root",
                    str(root / "state"),
                    "--poll",
                    "0.1",
                ],
                text=True,
                capture_output=True,
                env=env,
                timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            args = json.loads(args_file.read_text())
            self.assertIn("accept-edits", args)
            self.assertIn("--sandbox", args)
            self.assertIn("--print", args)
            self.assertNotIn("PRIVATE DEVIN PROMPT", args)


if __name__ == "__main__":
    unittest.main()
