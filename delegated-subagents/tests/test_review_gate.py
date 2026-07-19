import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
DELEGATE = SKILL_DIR / "scripts" / "delegate.py"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DELEGATE), *args],
        text=True,
        capture_output=True,
        timeout=15,
    )


def init_review_run(root: Path) -> tuple[Path, Path, str]:
    repo = root / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    (repo / "tracked.txt").write_text("before\n")
    subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "initial"], check=True)
    base = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    (repo / "tracked.txt").write_text("after\n")
    (repo / "new.txt").write_text("new\n")

    state_root = root / "runs"
    run_dir = state_root / "implementation"
    run_dir.mkdir(parents=True)
    state = {
        "run_id": "implementation",
        "task_type": "code-small",
        "tool": "cursor",
        "models": ["composer-2.5"],
        "repo": str(repo),
        "workdir": str(repo),
        "base_commit": base,
        "permission_profile": "edit",
        "state": "worker-complete",
        "decision": "worker-complete",
        "changed_paths": ["tracked.txt", "new.txt"],
        "manifest": {
            "goal": "change files",
            "acceptance_criteria": ["tracked changed", "new file added"],
            "allowed_paths": ["tracked.txt", "new.txt"],
        },
        "report": {
            "acceptance": [
                {"status": "pass", "criterion": "tracked changed", "evidence": "focused test"}
            ]
        },
    }
    (run_dir / "state.json").write_text(json.dumps(state))
    return state_root, run_dir, base


def init_pre_review(state_root: Path, implementation_run: Path) -> Path:
    implementation = json.loads((implementation_run / "state.json").read_text())
    run_dir = state_root / "pre-review"
    run_dir.mkdir()
    state = {
        "run_id": "pre-review",
        "task_type": "review",
        "tool": "opencode",
        "models": ["opencode/nemotron-3-ultra-free"],
        "workdir": implementation["workdir"],
        "state": "worker-complete",
        "decision": "worker-complete",
        "report": {
            "acceptance": [
                {"status": "pass", "criterion": "review final diff", "evidence": "no findings"}
            ]
        },
    }
    (run_dir / "state.json").write_text(json.dumps(state))
    return run_dir


class ReviewGateTests(unittest.TestCase):
    def test_review_packet_contains_complete_diff_and_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            state_root, run_dir, _base = init_review_run(Path(temp))
            pre_review = init_pre_review(state_root, run_dir)
            state = json.loads((run_dir / "state.json").read_text())
            state["manifest"]["allowed_paths"].append("late.txt")
            (run_dir / "state.json").write_text(json.dumps(state))
            (Path(state["workdir"]) / "late.txt").write_text("late\n")

            result = run_cli(
                "review-packet",
                str(run_dir),
                "--state-root",
                str(state_root),
                "--pre-review-run",
                str(pre_review),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            packet_path = Path(result.stdout.strip())
            packet = packet_path.read_text()
            state = json.loads((run_dir / "state.json").read_text())
            self.assertIn("tracked.txt", packet)
            self.assertIn("new.txt", packet)
            self.assertIn("late.txt", packet)
            self.assertIn("Pre-review evidence", packet)
            self.assertIn("opencode/nemotron-3-ultra-free", packet)
            self.assertNotIn("PRIVATE PROMPT", packet)
            self.assertEqual(state["state"], "codex-review-required")
            canonical_diff = Path(state["review_packet"]["diff_path"]).read_text()
            self.assertEqual(
                state["review_packet"]["diff_hash"],
                hashlib.sha256(canonical_diff.encode()).hexdigest(),
            )

    def test_approval_requires_codex_and_matching_diff_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            state_root, run_dir, _base = init_review_run(Path(temp))
            pre_review = init_pre_review(state_root, run_dir)
            packet = run_cli(
                "review-packet",
                str(run_dir),
                "--state-root",
                str(state_root),
                "--pre-review-run",
                str(pre_review),
            )
            self.assertEqual(packet.returncode, 0, packet.stderr)

            wrong_reviewer = run_cli(
                "record-review",
                str(run_dir),
                "--state-root",
                str(state_root),
                "--reviewer",
                "composer",
                "--decision",
                "approved",
                "--verification-summary",
                "tests passed",
            )
            self.assertEqual(wrong_reviewer.returncode, 2)

            approved = run_cli(
                "record-review",
                str(run_dir),
                "--state-root",
                str(state_root),
                "--reviewer",
                "codex",
                "--decision",
                "approved",
                "--verification-summary",
                "full diff reviewed; tests passed",
                "--residual-risk",
                "none",
            )
            self.assertEqual(approved.returncode, 0, approved.stderr)
            state = json.loads((run_dir / "state.json").read_text())
            self.assertEqual(state["state"], "approved")
            self.assertEqual(state["review"]["reviewer"], "codex")

            (Path(state["workdir"]) / "tracked.txt").write_text("changed again\n")
            status = run_cli("status", "--state-root", str(state_root), "--json")
            self.assertEqual(status.returncode, 0, status.stderr)
            refreshed = json.loads((run_dir / "state.json").read_text())
            self.assertEqual(refreshed["state"], "codex-review-required")
            self.assertEqual(refreshed["review"]["status"], "stale")

    def test_cannot_approve_before_review_packet_exists(self):
        with tempfile.TemporaryDirectory() as temp:
            state_root, run_dir, _base = init_review_run(Path(temp))

            result = run_cli(
                "record-review",
                str(run_dir),
                "--state-root",
                str(state_root),
                "--reviewer",
                "codex",
                "--decision",
                "approved",
                "--verification-summary",
                "reviewed",
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("review packet", result.stderr)

    def test_edit_review_packet_requires_external_pre_review(self):
        with tempfile.TemporaryDirectory() as temp:
            state_root, run_dir, _base = init_review_run(Path(temp))

            result = run_cli("review-packet", str(run_dir), "--state-root", str(state_root))

            self.assertEqual(result.returncode, 2)
            self.assertIn("pre-review", result.stderr)

    def test_review_packet_rechecks_final_manifest_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            state_root, run_dir, _base = init_review_run(Path(temp))
            pre_review = init_pre_review(state_root, run_dir)
            state = json.loads((run_dir / "state.json").read_text())
            (Path(state["workdir"]) / "outside.txt").write_text("outside\n")

            result = run_cli(
                "review-packet",
                str(run_dir),
                "--state-root",
                str(state_root),
                "--pre-review-run",
                str(pre_review),
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("outside manifest scope", result.stderr)

    def test_pre_review_must_use_an_independent_model_family(self):
        with tempfile.TemporaryDirectory() as temp:
            state_root, run_dir, _base = init_review_run(Path(temp))
            pre_review = init_pre_review(state_root, run_dir)
            state = json.loads((pre_review / "state.json").read_text())
            state["tool"] = "cursor"
            state["models"] = ["composer-2.5"]
            (pre_review / "state.json").write_text(json.dumps(state))

            result = run_cli(
                "review-packet",
                str(run_dir),
                "--state-root",
                str(state_root),
                "--pre-review-run",
                str(pre_review),
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("independent", result.stderr)


if __name__ == "__main__":
    unittest.main()
