#!/usr/bin/env python3
"""Run and supervise non-interactive OpenCode and Devin subagents."""

from __future__ import annotations

import argparse
import collections
import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from runtime import (
    TERMINAL_STATES,
    atomic_write_json,
    capture_process_identity,
    create_run_dir,
    dedupe,
    is_availability_failure,
    parse_report,
    process_matches,
    rank_models_by_history,
    utc_now,
)


DEFAULT_STATE_ROOT = Path(os.environ.get("SUBAGENT_STATE_ROOT", "~/.codex/state/delegated-subagents/runs")).expanduser()
ACTIVE_STATES = {"starting", "running", "cancelling"}
current_process: subprocess.Popen[bytes] | None = None
current_identity: dict[str, Any] | None = None
cancel_requested = False


def load_state(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_state(run_dir: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    atomic_write_json(run_dir / "state.json", state)


def process_group_rss_mb(pgid: int) -> float:
    try:
        output = subprocess.check_output(
            ["ps", "-axo", "pgid=,rss="], text=True, stderr=subprocess.DEVNULL
        )
    except (OSError, subprocess.CalledProcessError):
        return 0.0
    total_kb = 0
    for line in output.splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[0].isdigit() and fields[1].isdigit() and int(fields[0]) == pgid:
            total_kb += int(fields[1])
    return round(total_kb / 1024, 1)


def process_died(return_code: int) -> bool:
    return return_code < 0 or return_code in {134, 137, 139, 143}


def terminate_owned_process(
    process: subprocess.Popen[bytes] | None,
    identity: dict[str, Any] | None,
    grace_seconds: float = 2.0,
) -> bool:
    if process is None or process.poll() is not None:
        return True
    if identity is not None and not process_matches(identity):
        return False
    pgid = identity.get("pgid") if identity else process.pid
    try:
        os.killpg(int(pgid), signal.SIGTERM)
    except ProcessLookupError:
        return True
    deadline = time.monotonic() + grace_seconds
    while process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    if process.poll() is None:
        try:
            os.killpg(int(pgid), signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=max(1.0, grace_seconds))
    except subprocess.TimeoutExpired:
        return False
    return True


def terminate_remaining_group(identity: dict[str, Any] | None, grace_seconds: float = 1.0) -> str:
    if not isinstance(identity, dict):
        return "missing-identity"
    pgid = identity.get("pgid")
    if not isinstance(pgid, int) or pgid <= 1:
        return "invalid-process-group"
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return "empty"
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return "empty"
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return "terminated"
        time.sleep(0.05)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    return "killed"


def signal_handler(signum: int, _frame: Any) -> None:
    global cancel_requested
    cancel_requested = True
    terminate_owned_process(current_process, current_identity)


def child_setup(nice_value: int) -> None:
    os.setsid()
    if nice_value:
        try:
            os.nice(nice_value)
        except OSError:
            pass


def build_command(args: argparse.Namespace, model: str, prompt_copy: Path, run_dir: Path) -> list[str]:
    instruction = "Read the attached task instructions and return the required structured report. Do not ask the user questions."
    if args.tool == "opencode":
        command = [
            "opencode",
            "run",
            instruction,
            "--pure",
            "--auto",
            "-m",
            model,
            "--dir",
            str(args.workdir),
            "--title",
            f"delegated-{run_dir.name}",
            "--file",
            str(prompt_copy),
        ]
        return command

    permission_mode = "accept-edits" if args.permission_profile == "edit" else "auto"
    command = [
        "devin",
        "--permission-mode",
        permission_mode,
        "--sandbox",
        "--respect-workspace-trust",
        "true",
        "--model",
        model,
        "--prompt-file",
        str(prompt_copy),
        "--export",
        str(run_dir / "devin-export.json"),
        "--print",
    ]
    return command


def append_history(state_root: Path, record: dict[str, Any]) -> None:
    history = state_root.parent / "model-history.jsonl"
    history.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with history.open("a", encoding="utf-8") as handle:
        os.chmod(history, 0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def count_active_runs(state_root: Path, repo: Path) -> tuple[int, int]:
    global_count = 0
    repo_count = 0
    if not state_root.exists():
        return 0, 0
    for state_path in state_root.glob("*/state.json"):
        try:
            state = load_state(state_path)
        except (OSError, json.JSONDecodeError):
            continue
        if state.get("state") not in ACTIVE_STATES:
            continue
        identity = state.get("active_process")
        if state.get("state") != "starting":
            if not isinstance(identity, dict) or not process_matches(identity):
                continue
        global_count += 1
        if state.get("repo") == str(repo):
            repo_count += 1
    return global_count, repo_count


def iter_states(state_root: Path) -> list[tuple[Path, dict[str, Any]]]:
    rows: list[tuple[Path, dict[str, Any]]] = []
    if not state_root.exists():
        return rows
    for state_path in sorted(state_root.glob("*/state.json"), reverse=True):
        try:
            rows.append((state_path.parent, load_state(state_path)))
        except (OSError, json.JSONDecodeError):
            continue
    return rows


def status_rows(state_root: Path) -> list[dict[str, Any]]:
    rows = []
    for run_dir, state in iter_states(state_root):
        rows.append(
            {
                "id": state.get("run_id", run_dir.name),
                "task": state.get("task_type", "unknown"),
                "tool": state.get("tool", "unknown"),
                "model": state.get("active_model") or (state.get("models") or ["unknown"])[0],
                "state": state.get("state", "unknown"),
                "decision": state.get("decision", "pending"),
                "repo": state.get("repo", "unknown"),
                "heartbeat": state.get("heartbeat_at") or state.get("updated_at") or state.get("created_at"),
                "rss_mb": state.get("rss_mb", 0),
                "run_dir": str(run_dir),
            }
        )
    return rows


def status_command(args: argparse.Namespace) -> int:
    rows = status_rows(args.state_root)
    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
        return 0
    if not rows:
        print("No delegated subagent runs found.")
        return 0
    print("ID\tTASK\tTOOL/MODEL\tSTATE\tRSS_MB\tHEARTBEAT\tDECISION")
    for row in rows:
        print(
            f"{row['id']}\t{row['task']}\t{row['tool']}/{row['model']}\t{row['state']}\t"
            f"{row['rss_mb']}\t{row['heartbeat'] or '-'}\t{row['decision']}"
        )
    return 0


def watch_command(args: argparse.Namespace) -> int:
    try:
        while True:
            os.system("clear" if sys.stdout.isatty() else "true")
            status_command(argparse.Namespace(state_root=args.state_root, json=False))
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


def terminate_identity(identity: dict[str, Any], grace_seconds: float = 2.0) -> str:
    if not process_matches(identity):
        return "identity-mismatch"
    pgid = identity.get("pgid")
    if not isinstance(pgid, int) or pgid <= 1:
        return "invalid-process-group"
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return "already-exited"
    deadline = time.monotonic() + grace_seconds
    while process_matches(identity) and time.monotonic() < deadline:
        time.sleep(0.05)
    if process_matches(identity):
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    return "terminated"


def resolve_run_dir(state_root: Path, value: str) -> Path:
    candidate = Path(value).expanduser()
    if candidate.is_dir():
        return candidate.resolve()
    candidate = state_root / value
    if candidate.is_dir():
        return candidate.resolve()
    raise FileNotFoundError(f"run not found: {value}")


def cancel_command(args: argparse.Namespace) -> int:
    try:
        run_dir = resolve_run_dir(args.state_root, args.run)
        state = load_state(run_dir / "state.json")
    except (FileNotFoundError, OSError, json.JSONDecodeError) as error:
        print(error, file=sys.stderr)
        return 2
    (run_dir / "cancel.requested").touch(mode=0o600, exist_ok=True)
    identity = state.get("active_process")
    state["state"] = "cancelling"
    save_state(run_dir, state)
    if isinstance(identity, dict):
        outcome = terminate_identity(identity)
        if outcome == "identity-mismatch":
            state["state"] = "orphaned"
            state["error"] = "cancel refused: process identity mismatch"
            save_state(run_dir, state)
            print(state["error"], file=sys.stderr)
            return 2
    state["state"] = "cancelled"
    state["decision"] = "rejected"
    save_state(run_dir, state)
    print(run_dir)
    return 0


def cleanup_command(args: argparse.Namespace) -> int:
    for run_dir, state in iter_states(args.state_root):
        if state.get("state") not in ACTIVE_STATES:
            continue
        identity = state.get("active_process")
        if not isinstance(identity, dict):
            state["state"] = "orphaned"
            state["error"] = "cleanup could not find process identity"
            save_state(run_dir, state)
            print(f"orphaned\t{run_dir}\tmissing identity")
            continue
        if args.dry_run:
            outcome = "would-terminate" if process_matches(identity) else "identity-mismatch"
            print(f"{outcome}\t{run_dir}")
            continue
        else:
            outcome = terminate_identity(identity)
        if outcome == "identity-mismatch":
            state["state"] = "orphaned"
            state["error"] = "cleanup refused: process identity mismatch"
        else:
            state["state"] = "cancelled"
            state["decision"] = "rejected"
            state.pop("active_process", None)
        save_state(run_dir, state)
        print(f"{outcome}\t{run_dir}")
    return 0


def scorecard_command(args: argparse.Namespace) -> int:
    history = args.state_root.parent / "model-history.jsonl"
    aggregate: dict[tuple[str, str], dict[str, Any]] = collections.defaultdict(
        lambda: {"runs": 0, "accepted": 0, "duration": 0.0, "results": collections.Counter()}
    )
    if history.exists():
        for line in history.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            model = record.get("model")
            if not isinstance(model, str):
                continue
            task_type = str(record.get("task_type", "unknown"))
            item = aggregate[(model, task_type)]
            item["runs"] += 1
            item["accepted"] += int(record.get("result") == "accepted")
            item["duration"] += float(record.get("duration_seconds", 0))
            item["results"][str(record.get("result", "unknown"))] += 1
    rows = []
    for (model, task_type), item in aggregate.items():
        rows.append(
            {
                "model": model,
                "task_type": task_type,
                "runs": item["runs"],
                "acceptance_rate": round(item["accepted"] / item["runs"], 3),
                "average_duration_seconds": round(item["duration"] / item["runs"], 2),
                "results": dict(item["results"]),
            }
        )
    rows.sort(key=lambda row: (row["task_type"], -row["acceptance_rate"], -row["runs"], row["model"]))
    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
    else:
        print("TASK\tMODEL\tRUNS\tACCEPT_RATE\tAVG_SECONDS\tRESULTS")
        for row in rows:
            print(f"{row['task_type']}\t{row['model']}\t{row['runs']}\t{row['acceptance_rate']}\t{row['average_duration_seconds']}\t{json.dumps(row['results'], sort_keys=True)}")
    return 0


def models_command(args: argparse.Namespace) -> int:
    if shutil.which("opencode") is None:
        print("opencode is not installed", file=sys.stderr)
        return 127
    result = subprocess.run(["opencode", "models"], text=True, capture_output=True)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr, end="")
        return result.returncode
    models = dedupe(line.strip() for line in result.stdout.splitlines())
    snapshot = {"refreshed_at": utc_now(), "models": models}
    snapshot_path = args.state_root.parent / "model-snapshot.json"
    atomic_write_json(snapshot_path, snapshot)
    if args.json:
        print(json.dumps(snapshot, indent=2, sort_keys=True))
    else:
        print("\n".join(models))
        print(f"snapshot={snapshot_path}", file=sys.stderr)
    return 0


def prune_command(args: argparse.Namespace) -> int:
    cutoff = time.time() - args.days * 86400
    removable_states = TERMINAL_STATES | {"needs-follow-up", "orphaned"}
    for run_dir, state in iter_states(args.state_root):
        state_path = run_dir / "state.json"
        if state.get("state") not in removable_states:
            continue
        try:
            old_enough = state_path.stat().st_mtime < cutoff
        except OSError:
            continue
        if not old_enough:
            continue
        if args.dry_run:
            print(f"would-remove\t{run_dir}")
        else:
            shutil.rmtree(run_dir)
            print(f"removed\t{run_dir}")
    return 0


def git(repo: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *arguments],
        text=True,
        capture_output=True,
        check=check,
    )


def porcelain_paths(output: str) -> list[str]:
    paths: list[str] = []
    for line in output.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path.strip('"'))
    return paths


def path_allowed(path: str, allowed_paths: list[str]) -> bool:
    for allowed in allowed_paths:
        normalized = allowed.strip().lstrip("./").rstrip("/")
        if normalized and (path == normalized or path.startswith(normalized + "/")):
            return True
    return False


def create_managed_worktree(repo: Path, worktree_root: Path, run_id: str) -> tuple[Path, str]:
    root = Path(git(repo, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    branch = git(root, "branch", "--show-current").stdout.strip()
    if not branch:
        raise ValueError("cannot create delegated worktree from detached HEAD")
    slug = root.name.replace(" ", "-")
    path = worktree_root.expanduser().resolve() / slug / run_id
    delegated_branch = f"codex/delegated/{run_id}"
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    result = git(root, "worktree", "add", "-b", delegated_branch, str(path), "HEAD", check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git worktree add failed")
    return path, delegated_branch


def worktree_create_command(args: argparse.Namespace) -> int:
    repo = args.repo.expanduser().resolve()
    try:
        path, _branch = create_managed_worktree(repo, args.worktree_root, args.run_id)
    except (subprocess.CalledProcessError, OSError, RuntimeError, ValueError) as error:
        print(f"not a usable git repository: {error}", file=sys.stderr)
        return 2
    print(path)
    return 0


def worktree_cleanup_command(args: argparse.Namespace) -> int:
    repo = args.repo.expanduser().resolve()
    path = args.path.expanduser().resolve()
    status = git(path, "status", "--porcelain", check=False)
    if status.returncode != 0:
        print(status.stderr, file=sys.stderr, end="")
        return 2
    if status.stdout.strip():
        print(f"refusing to remove dirty worktree: {path}", file=sys.stderr)
        return 2
    branch = git(path, "branch", "--show-current").stdout.strip()
    result = git(repo, "worktree", "remove", str(path), check=False)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr, end="")
        return result.returncode
    if branch.startswith("codex/delegated/"):
        git(repo, "branch", "-D", branch, check=False)
    print(path)
    return 0


def run_command(args: argparse.Namespace) -> int:
    global current_identity, current_process, cancel_requested
    os.umask(0o077)
    args.workdir = args.workdir.expanduser().resolve()
    if not args.workdir.is_dir():
        print(f"workdir does not exist: {args.workdir}", file=sys.stderr)
        return 2
    if not args.prompt_file.is_file():
        print(f"prompt file does not exist: {args.prompt_file}", file=sys.stderr)
        return 2
    if shutil.which(args.tool) is None:
        print(f"{args.tool} is not installed", file=sys.stderr)
        return 127

    manifest: dict[str, Any] | None = None
    if args.manifest is not None:
        try:
            manifest = load_state(args.manifest)
        except (OSError, json.JSONDecodeError) as error:
            print(f"invalid manifest: {error}", file=sys.stderr)
            return 2
        if not isinstance(manifest.get("goal"), str) or not isinstance(manifest.get("acceptance_criteria"), list):
            print("manifest requires string goal and acceptance_criteria list", file=sys.stderr)
            return 2

    models = dedupe(item.strip() for item in args.models.split(","))
    if not models:
        print("at least one explicit model is required", file=sys.stderr)
        return 2
    models = rank_models_by_history(
        models,
        args.state_root.parent / "model-history.jsonl",
        args.task,
        preserve_first=args.preserve_first,
    )[: args.max_attempts]

    original_repo = args.workdir
    state: dict[str, Any] = {
        "schema_version": 1,
        "tool": args.tool,
        "task_type": args.task,
        "repo": str(original_repo),
        "workdir": str(args.workdir),
        "permission_profile": args.permission_profile,
        "models": models,
        "state": "starting",
        "decision": "pending",
        "created_at": utc_now(),
        "attempts": [],
        "limits": {
            "timeout_seconds": args.timeout,
            "idle_seconds": args.idle,
            "max_rss_mb": args.max_rss_mb,
            "max_attempts": args.max_attempts,
        },
    }
    if manifest is not None:
        state["manifest"] = manifest
    args.state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    admission_lock = args.state_root.parent / ".admission.lock"
    with admission_lock.open("a+") as lock_handle:
        os.chmod(admission_lock, 0o600)
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        global_active, repo_active = count_active_runs(args.state_root, args.workdir)
        if global_active >= args.max_global:
            print(f"global subagent limit reached ({global_active}/{args.max_global})", file=sys.stderr)
            return 75
        if repo_active >= args.max_per_repo:
            print(f"repository subagent limit reached ({repo_active}/{args.max_per_repo})", file=sys.stderr)
            return 75
        run_dir = create_run_dir(args.state_root, args.tool)
        state["run_id"] = run_dir.name
        save_state(run_dir, state)

    prompt_copy = run_dir / "prompt.txt"
    shutil.copyfile(args.prompt_file, prompt_copy)
    prompt_copy.chmod(0o600)
    if args.manifest is not None:
        manifest_copy = run_dir / "manifest.json"
        shutil.copyfile(args.manifest, manifest_copy)
        manifest_copy.chmod(0o600)

    if args.isolation == "managed":
        try:
            worktree, branch = create_managed_worktree(original_repo, args.worktree_root, run_dir.name)
        except (subprocess.CalledProcessError, OSError, RuntimeError, ValueError) as error:
            state["state"] = "failed"
            state["decision"] = "rejected"
            state["error"] = f"managed worktree creation failed: {error}"
            save_state(run_dir, state)
            print(run_dir)
            print(state["error"], file=sys.stderr)
            return 2
        args.workdir = worktree
        state["workdir"] = str(worktree)
        state["worktree"] = {"path": str(worktree), "branch": branch, "managed": True}
        save_state(run_dir, state)
    git_before_result = git(args.workdir, "status", "--porcelain", check=False)
    git_before = git_before_result.stdout if git_before_result.returncode == 0 else ""
    state["git_before"] = git_before
    save_state(run_dir, state)
    print(run_dir, flush=True)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    last_terminal_state = "failed"

    for number, model in enumerate(models, start=1):
        if cancel_requested:
            state["state"] = "cancelled"
            state["decision"] = "rejected"
            save_state(run_dir, state)
            return 130

        log_path = run_dir / f"attempt-{number}.log"
        command = build_command(args, model, prompt_copy, run_dir)
        attempt: dict[str, Any] = {
            "number": number,
            "model": model,
            "state": "starting",
            "started_at": utc_now(),
            "log": str(log_path),
            "command": command,
        }
        state["attempts"].append(attempt)
        state["state"] = "running"
        state["active_model"] = model
        save_state(run_dir, state)

        started = time.monotonic()
        last_growth = started
        last_size = -1
        breach_samples = 0
        terminal_state = "failed"
        with log_path.open("wb") as log_handle:
            current_process = subprocess.Popen(
                command,
                cwd=args.workdir,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                preexec_fn=lambda: child_setup(args.nice),
            )
            current_identity = capture_process_identity(current_process.pid)
            if current_identity is None:
                current_identity = {
                    "pid": current_process.pid,
                    "pgid": current_process.pid,
                    "start_signature": "owned-current-process",
                    "command": command[0],
                }
            attempt["process"] = current_identity
            attempt["state"] = "running"
            state["active_process"] = current_identity
            save_state(run_dir, state)

            while current_process.poll() is None:
                now = time.monotonic()
                try:
                    size = log_path.stat().st_size
                except OSError:
                    size = 0
                if size != last_size:
                    last_size = size
                    last_growth = now
                    state["last_activity_at"] = utc_now()

                rss_mb = process_group_rss_mb(int(current_identity.get("pgid", current_process.pid)))
                attempt["rss_mb"] = rss_mb
                state["rss_mb"] = rss_mb
                if args.max_rss_mb > 0 and rss_mb > args.max_rss_mb:
                    breach_samples += 1
                else:
                    breach_samples = 0

                if cancel_requested or (run_dir / "cancel.requested").exists():
                    terminal_state = "cancelled"
                    terminate_owned_process(current_process, current_identity)
                    break
                if now - started > args.timeout:
                    terminal_state = "timeout"
                    terminate_owned_process(current_process, current_identity)
                    break
                if now - last_growth > args.idle:
                    terminal_state = "idle-timeout"
                    terminate_owned_process(current_process, current_identity)
                    break
                if breach_samples >= 3:
                    terminal_state = "resource-limit"
                    terminate_owned_process(current_process, current_identity)
                    break

                state["heartbeat_at"] = utc_now()
                save_state(run_dir, state)
                time.sleep(args.poll)

            return_code = current_process.wait()

        if (run_dir / "cancel.requested").exists():
            terminal_state = "cancelled"
        attempt["process_group_cleanup"] = terminate_remaining_group(current_identity)

        attempt["exit_code"] = return_code
        attempt["finished_at"] = utc_now()
        attempt["duration_seconds"] = round(time.monotonic() - started, 2)
        state.pop("active_process", None)
        current_process = None
        current_identity = None

        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        if terminal_state in {"timeout", "idle-timeout", "resource-limit", "cancelled"}:
            attempt["state"] = terminal_state
            last_terminal_state = terminal_state
            append_history(args.state_root, {"at": utc_now(), "tool": args.tool, "model": model, "task_type": args.task, "result": terminal_state, "duration_seconds": attempt["duration_seconds"]})
            save_state(run_dir, state)
            if terminal_state == "cancelled":
                state["state"] = "cancelled"
                state["decision"] = "rejected"
                save_state(run_dir, state)
                return 130
            continue

        if return_code != 0:
            if process_died(return_code):
                attempt["state"] = "died"
                last_terminal_state = "died"
                append_history(args.state_root, {"at": utc_now(), "tool": args.tool, "model": model, "task_type": args.task, "result": "died", "duration_seconds": attempt["duration_seconds"]})
                save_state(run_dir, state)
                continue
            if is_availability_failure(log_text, return_code):
                attempt["state"] = "provider-unavailable"
                last_terminal_state = "provider-unavailable"
                append_history(args.state_root, {"at": utc_now(), "tool": args.tool, "model": model, "task_type": args.task, "result": "provider-unavailable", "duration_seconds": attempt["duration_seconds"]})
                save_state(run_dir, state)
                continue
            attempt["state"] = "failed"
            state["state"] = "failed"
            state["decision"] = "rejected"
            state["error"] = f"subagent exited with code {return_code}"
            append_history(args.state_root, {"at": utc_now(), "tool": args.tool, "model": model, "task_type": args.task, "result": "failed", "duration_seconds": attempt["duration_seconds"]})
            save_state(run_dir, state)
            return return_code or 1

        report = parse_report(log_text, expected_model=model)
        git_after_result = git(args.workdir, "status", "--porcelain", check=False)
        git_after = git_after_result.stdout if git_after_result.returncode == 0 else ""
        state["git_after"] = git_after
        attempt["report"] = report.to_dict()
        attempt["state"] = report.decision
        state["report"] = report.to_dict()
        state["decision"] = report.decision
        state["state"] = report.decision
        if args.permission_profile == "read-only" and git_after != git_before:
            attempt["state"] = "rejected"
            state["state"] = "rejected"
            state["decision"] = "rejected"
            state["policy_violation"] = "read-only subagent changed files"
        changed_paths = porcelain_paths(git_after)
        state["changed_paths"] = changed_paths
        if args.permission_profile == "edit" and manifest is not None:
            allowed_paths = manifest.get("allowed_paths")
            if isinstance(allowed_paths, list) and allowed_paths:
                out_of_scope = [
                    path
                    for path in changed_paths
                    if not path_allowed(path, [item for item in allowed_paths if isinstance(item, str)])
                ]
                if out_of_scope:
                    attempt["state"] = "rejected"
                    state["state"] = "rejected"
                    state["decision"] = "rejected"
                    state["policy_violation"] = "subagent changed paths outside manifest scope"
                    state["out_of_scope_paths"] = out_of_scope
        final_decision = state["decision"]
        append_history(args.state_root, {"at": utc_now(), "tool": args.tool, "model": model, "task_type": args.task, "result": final_decision, "duration_seconds": attempt["duration_seconds"]})
        save_state(run_dir, state)
        if final_decision == "accepted":
            return 0
        if final_decision == "needs-follow-up":
            return 3
        return 4

    state["state"] = last_terminal_state if last_terminal_state in {"timeout", "idle-timeout", "resource-limit"} else "failed"
    state["decision"] = "rejected"
    state["error"] = "all model attempts exhausted"
    save_state(run_dir, state)
    return 124


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="launch and supervise a subagent")
    run.add_argument("--tool", choices=("opencode", "devin"), required=True)
    run.add_argument("--task", default="scout")
    run.add_argument("--prompt-file", type=Path, required=True)
    run.add_argument("--manifest", type=Path)
    run.add_argument("--workdir", type=Path, default=Path.cwd())
    run.add_argument("--models", required=True, help="comma-separated fallback chain")
    run.add_argument("--preserve-first", action="store_true", help="do not reorder the explicitly selected first model")
    run.add_argument("--permission-profile", choices=("read-only", "edit"), default="read-only")
    run.add_argument("--isolation", choices=("managed", "none"), default="managed")
    run.add_argument("--worktree-root", type=Path, default=Path("~/.codex/worktrees/delegated-subagents"))
    run.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    run.add_argument("--timeout", type=float, default=float(os.environ.get("SUBAGENT_TIMEOUT_SECONDS", "1800")))
    run.add_argument("--idle", type=float, default=float(os.environ.get("SUBAGENT_IDLE_SECONDS", "300")))
    run.add_argument("--poll", type=float, default=2.0)
    run.add_argument("--max-attempts", type=int, default=int(os.environ.get("SUBAGENT_MAX_ATTEMPTS", "3")))
    run.add_argument("--max-rss-mb", type=float, default=float(os.environ.get("SUBAGENT_MAX_RSS_MB", "4096")))
    run.add_argument("--max-global", type=int, default=int(os.environ.get("SUBAGENT_MAX_GLOBAL", "3")))
    run.add_argument("--max-per-repo", type=int, default=int(os.environ.get("SUBAGENT_MAX_PER_REPO", "2")))
    run.add_argument("--nice", type=int, default=int(os.environ.get("SUBAGENT_NICE", "5")))
    run.set_defaults(func=run_command)

    status = subparsers.add_parser("status", help="show delegated subagent runs")
    status.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=status_command)

    watch = subparsers.add_parser("watch", help="continuously show delegated subagent status")
    watch.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    watch.add_argument("--interval", type=float, default=2.0)
    watch.set_defaults(func=watch_command)

    cancel = subparsers.add_parser("cancel", help="cancel one active run")
    cancel.add_argument("run")
    cancel.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    cancel.set_defaults(func=cancel_command)

    cleanup = subparsers.add_parser("cleanup", help="terminate safely identified stale runs")
    cleanup.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    cleanup.add_argument("--dry-run", action="store_true")
    cleanup.set_defaults(func=cleanup_command)

    scorecard = subparsers.add_parser("scorecard", help="summarize model outcomes")
    scorecard.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    scorecard.add_argument("--json", action="store_true")
    scorecard.set_defaults(func=scorecard_command)

    models = subparsers.add_parser("models", help="refresh the live OpenCode model snapshot")
    models.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    models.add_argument("--json", action="store_true")
    models.set_defaults(func=models_command)

    prune = subparsers.add_parser("prune", help="remove old terminal run logs and prompts")
    prune.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    prune.add_argument("--days", type=int, default=int(os.environ.get("SUBAGENT_RETENTION_DAYS", "14")))
    prune.add_argument("--dry-run", action="store_true")
    prune.set_defaults(func=prune_command)

    worktree = subparsers.add_parser("worktree", help="manage isolated delegated worktrees")
    worktree_sub = worktree.add_subparsers(dest="worktree_command", required=True)
    create = worktree_sub.add_parser("create")
    create.add_argument("--repo", type=Path, required=True)
    create.add_argument("--worktree-root", type=Path, default=Path("~/.codex/worktrees/delegated-subagents"))
    create.add_argument("--run-id", required=True)
    create.set_defaults(func=worktree_create_command)
    clean = worktree_sub.add_parser("cleanup")
    clean.add_argument("--repo", type=Path, required=True)
    clean.add_argument("--path", type=Path, required=True)
    clean.set_defaults(func=worktree_cleanup_command)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
