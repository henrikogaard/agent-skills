import json
import os
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
DELEGATE = SKILL_DIR / "scripts" / "delegate.py"


def run_cli(*args: str, timeout: float = 15) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DELEGATE), *args],
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class ControlCliTests(unittest.TestCase):
    def test_status_json_lists_model_state_and_resource_use(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = root / "run-1"
            run.mkdir()
            (run / "state.json").write_text(
                json.dumps(
                    {
                        "run_id": "run-1",
                        "task_type": "review",
                        "tool": "opencode",
                        "active_model": "fake/model",
                        "state": "running",
                        "decision": "pending",
                        "repo": "/tmp/repo",
                        "heartbeat_at": "2026-07-11T00:00:00+00:00",
                        "rss_mb": 42.5,
                    }
                )
            )

            result = run_cli("status", "--state-root", str(root), "--json")

            self.assertEqual(result.returncode, 0, result.stderr)
            rows = json.loads(result.stdout)
            self.assertEqual(rows[0]["model"], "fake/model")
            self.assertEqual(rows[0]["rss_mb"], 42.5)

    def test_cleanup_refuses_identity_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = root / "run-1"
            run.mkdir()
            process = subprocess.Popen(["sleep", "30"], start_new_session=True)
            try:
                state = {
                    "run_id": "run-1",
                    "state": "running",
                    "active_process": {
                        "pid": process.pid,
                        "pgid": process.pid,
                        "start_signature": "stale-reused-pid",
                    },
                }
                (run / "state.json").write_text(json.dumps(state))

                result = run_cli("cleanup", "--state-root", str(root))

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIsNone(process.poll())
                updated = json.loads((run / "state.json").read_text())
                self.assertEqual(updated["state"], "orphaned")
                self.assertIn("identity mismatch", updated["error"])
            finally:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=5)

    def test_cleanup_dry_run_never_mutates_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = root / "run-1"
            run.mkdir()
            original = {
                "run_id": "run-1",
                "state": "running",
                "active_process": {"pid": 999999, "pgid": 999999, "start_signature": "stale"},
            }
            (run / "state.json").write_text(json.dumps(original))

            result = run_cli("cleanup", "--state-root", str(root), "--dry-run")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads((run / "state.json").read_text()), original)

    def test_scorecard_aggregates_model_history(self):
        with tempfile.TemporaryDirectory() as temp:
            state_root = Path(temp) / "runs"
            state_root.mkdir()
            history = state_root.parent / "model-history.jsonl"
            history.write_text(
                "\n".join(
                    [
                        json.dumps({"model": "fake/a", "result": "worker-complete", "duration_seconds": 2}),
                        json.dumps({"model": "fake/a", "result": "failed", "duration_seconds": 4}),
                        json.dumps({"model": "fake/b", "result": "approved", "duration_seconds": 1}),
                    ]
                )
                + "\n"
            )

            result = run_cli("scorecard", "--state-root", str(state_root), "--json")

            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {row["model"]: row for row in json.loads(result.stdout)}
            self.assertEqual(rows["fake/a"]["runs"], 2)
            self.assertEqual(rows["fake/a"]["completion_rate"], 0.5)
            self.assertNotIn("acceptance_rate", rows["fake/a"])
            self.assertEqual(rows["fake/a"]["task_type"], "unknown")

    def test_concurrency_limit_and_external_cancel(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            write_executable(
                fake_bin / "opencode",
                "#!/usr/bin/env python3\nimport time\nprint('working', flush=True)\ntime.sleep(30)\n",
            )
            prompt = root / "prompt.txt"
            prompt.write_text("task")
            state_root = root / "state"
            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
            base = [
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
                "fake/one",
                "--state-root",
                str(state_root),
                "--isolation",
                "none",
                "--poll",
                "0.1",
                "--max-global",
                "1",
            ]
            first = subprocess.Popen(base, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            assert first.stdout is not None
            run_dir = Path(first.stdout.readline().strip())
            deadline = time.time() + 5
            while time.time() < deadline:
                if (run_dir / "state.json").exists():
                    state = json.loads((run_dir / "state.json").read_text())
                    if state.get("state") == "running":
                        break
                time.sleep(0.05)
            second = subprocess.run(base, text=True, capture_output=True, env=env, timeout=10)
            self.assertEqual(second.returncode, 75, second.stderr)

            cancelled = run_cli("cancel", str(run_dir), "--state-root", str(state_root))
            self.assertEqual(cancelled.returncode, 0, cancelled.stderr)
            first.wait(timeout=10)
            first.communicate(timeout=1)
            state = json.loads((run_dir / "state.json").read_text())
            self.assertEqual(state["state"], "cancelled")

    def test_rss_limit_terminates_large_process(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            write_executable(
                fake_bin / "opencode",
                "#!/usr/bin/env python3\nimport time\ndata=bytearray(20*1024*1024)\nprint(len(data), flush=True)\ntime.sleep(30)\n",
            )
            prompt = root / "prompt.txt"
            prompt.write_text("task")
            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
            result = subprocess.run(
                [
                    sys.executable,
                    str(DELEGATE),
                    "run",
                    "--tool",
                    "opencode",
                    "--prompt-file",
                    str(prompt),
                    "--workdir",
                    str(root),
                    "--models",
                    "fake/one",
                    "--state-root",
                    str(root / "state"),
                    "--isolation",
                    "none",
                    "--poll",
                    "0.1",
                    "--max-rss-mb",
                    "1",
                    "--max-attempts",
                    "1",
                ],
                text=True,
                capture_output=True,
                env=env,
                timeout=15,
            )
            self.assertEqual(result.returncode, 124, result.stderr)
            state = json.loads((Path(result.stdout.strip()) / "state.json").read_text())
            self.assertEqual(state["state"], "resource-limit")

    def test_prune_removes_only_old_terminal_runs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = root / "old"
            recent = root / "recent"
            active = root / "active"
            pending = root / "pending-review"
            for path, state in (
                (old, "accepted"),
                (recent, "approved"),
                (active, "running"),
                (pending, "codex-review-required"),
            ):
                path.mkdir()
                (path / "state.json").write_text(json.dumps({"run_id": path.name, "state": state}))
            old_time = time.time() - 30 * 86400
            os.utime(old / "state.json", (old_time, old_time))
            os.utime(pending / "state.json", (old_time, old_time))

            result = run_cli("prune", "--state-root", str(root), "--days", "14")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(old.exists())
            self.assertTrue(recent.exists())
            self.assertTrue(active.exists())
            self.assertTrue(pending.exists())


class WorktreeCliTests(unittest.TestCase):
    def test_create_and_clean_worktree_but_refuse_dirty_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            (repo / "README.md").write_text("test\n")
            subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "initial"], check=True)
            worktree_root = root / "worktrees"

            created = run_cli(
                "worktree",
                "create",
                "--repo",
                str(repo),
                "--worktree-root",
                str(worktree_root),
                "--run-id",
                "test-run",
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            worktree = Path(created.stdout.strip())
            self.assertTrue((worktree / ".git").exists())

            (worktree / "dirty.txt").write_text("preserve me")
            refused = run_cli("worktree", "cleanup", "--repo", str(repo), "--path", str(worktree))
            self.assertEqual(refused.returncode, 2)
            self.assertTrue(worktree.exists())

            (worktree / "dirty.txt").unlink()
            cleaned = run_cli("worktree", "cleanup", "--repo", str(repo), "--path", str(worktree))
            self.assertEqual(cleaned.returncode, 0, cleaned.stderr)
            self.assertFalse(worktree.exists())


if __name__ == "__main__":
    unittest.main()
