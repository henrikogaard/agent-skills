#!/usr/bin/env python3
"""Run and supervise non-interactive OpenCode and Devin subagents."""

from __future__ import annotations

import argparse
import collections
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from runtime import (
    TERMINAL_STATES,
    assess_free_models,
    atomic_write_json,
    capture_process_identity,
    create_run_dir,
    dedupe,
    is_availability_failure,
    model_identity as runtime_model_identity,
    parse_report,
    process_matches,
    rank_models_by_history,
    utc_now,
)


DEFAULT_STATE_ROOT = Path(os.environ.get("SUBAGENT_STATE_ROOT", "~/.codex/state/delegated-subagents/runs")).expanduser()
ACTIVE_STATES = {"starting", "running", "cancelling"}
DASHBOARD_TASK_TYPES = {
    "bulk",
    "closure-validation",
    "code-complex",
    "code-small",
    "debug",
    "long-autonomous",
    "mechanical-edit",
    "review",
    "scout",
}
current_process: subprocess.Popen[bytes] | None = None
current_identity: dict[str, Any] | None = None
cancel_requested = False


def required_executable(tool: str) -> str:
    return "cursor-agent" if tool == "cursor" else tool


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


def worker_environment(args: argparse.Namespace) -> dict[str, str]:
    environment = os.environ.copy()
    if args.tool == "opencode":
        config_content = environment.get("OPENCODE_CONFIG_CONTENT", "{}")
        try:
            config = json.loads(config_content)
        except json.JSONDecodeError:
            config = {}
        if not isinstance(config, dict):
            config = {}
        tools = config.get("tools")
        if not isinstance(tools, dict):
            tools = {}
        tools.setdefault("infomaniak_*", False)
        tools.setdefault("cua-driver_*", False)
        config["tools"] = tools
        environment["OPENCODE_CONFIG_CONTENT"] = json.dumps(config, sort_keys=True)
    return environment


def build_command(args: argparse.Namespace, model: str, prompt_copy: Path, run_dir: Path) -> list[str]:
    instruction = "Read the attached task instructions and return the required structured report. Do not ask the user questions."
    if args.tool == "opencode":
        command = [
            "opencode",
            "run",
            instruction,
            "--format",
            "json",
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

    if args.tool == "cursor":
        command = [
            "cursor-agent",
            "--print",
            "--output-format",
            "stream-json",
            "--model",
            model,
            "--workspace",
            str(args.workdir),
            "--add-dir",
            str(prompt_copy.parent),
            "--sandbox",
            "enabled",
            "--trust",
        ]
        if args.permission_profile == "edit":
            command.append("--force")
        else:
            command.extend(["--mode", "plan"])
        command.append(
            f"Read {prompt_copy} and return its required structured report. Do not ask the user questions."
        )
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


def model_identity(tool: str, model: str) -> dict[str, str | None]:
    del tool
    return runtime_model_identity(model)


def resolve_devin_model(requested: str, configured: str | None, observed: list[str]) -> str:
    requested_identity = model_identity("devin", requested)
    family = requested_identity["model_family"]
    if family != "swe-1.7" or requested_identity["variant"] is not None:
        return requested
    if configured and model_identity("devin", configured)["model_family"] == family:
        return configured
    for candidate in observed:
        if model_identity("devin", candidate)["model_family"] == family:
            return candidate
    return requested


def observed_devin_models(history_path: Path) -> list[str]:
    if not history_path.is_file():
        return []
    observed: list[str] = []
    for line in reversed(history_path.read_text(encoding="utf-8", errors="replace").splitlines()):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("tool") != "devin" or record.get("result") not in {"worker-complete", "approved", "accepted"}:
            continue
        model = record.get("model")
        if isinstance(model, str) and model_identity("devin", model)["model_family"] == "swe-1.7":
            observed.append(model)
    return dedupe(observed)


def billing_class(tool: str, model: str) -> str:
    lowered = model.lower()
    if tool == "cursor":
        return "subscription"
    if (tool == "devin" and model_identity(tool, model)["model_family"] == "swe-1.7") or lowered.startswith("airouter/"):
        return "free"
    if lowered.startswith("opencode/") and "free" in lowered:
        return "free"
    if lowered.startswith("mistral/") or "mistral" in lowered:
        return "subscription"
    return "unknown"


def empty_usage(tool: str, model: str, error: str | None = None) -> dict[str, Any]:
    classification = billing_class(tool, model)
    usage: dict[str, Any] = {
        "source": "unavailable",
        "input_tokens": None,
        "cached_input_tokens": None,
        "cache_read_tokens": None,
        "cache_write_tokens": None,
        "output_tokens": None,
        "reasoning_tokens": None,
        "total_tokens": None,
        "reported_cost_usd": None,
        "billing_class": classification,
        "actual_charge_usd": 0 if classification == "free" else None,
    }
    if error:
        usage["error"] = error
    return usage


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _json_documents(text: str) -> list[Any]:
    documents: list[Any] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            documents.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
    if not documents and text.strip():
        try:
            documents.append(json.loads(text))
        except json.JSONDecodeError:
            pass
    return documents


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _sum_optional(rows: list[dict[str, Any]], key: str) -> int | float | None:
    values = [_number(row.get(key)) for row in rows]
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def _usage_from_opencode(text: str) -> dict[str, Any] | None:
    rows: list[dict[str, Any]] = []
    for document in _json_documents(text):
        for item in _walk_dicts(document):
            tokens = item.get("tokens")
            if not isinstance(tokens, dict):
                continue
            if not any(key in tokens for key in ("total", "input", "output", "reasoning", "cache")):
                continue
            cache = tokens.get("cache") if isinstance(tokens.get("cache"), dict) else {}
            rows.append(
                {
                    "input_tokens": tokens.get("input"),
                    "cached_input_tokens": cache.get("read"),
                    "cache_read_tokens": cache.get("read"),
                    "cache_write_tokens": cache.get("write"),
                    "output_tokens": tokens.get("output"),
                    "reasoning_tokens": tokens.get("reasoning"),
                    "total_tokens": tokens.get("total"),
                    "reported_cost_usd": item.get("cost"),
                }
            )
    if not rows:
        return None
    return {key: _sum_optional(rows, key) for key in rows[0]}


def _usage_from_cursor(text: str) -> dict[str, Any] | None:
    rows: list[dict[str, Any]] = []
    seen_candidates: set[int] = set()
    aliases = {
        "input_tokens": ("input_tokens", "inputTokens", "prompt_tokens", "promptTokens"),
        "cached_input_tokens": ("cached_input_tokens", "cachedInputTokens", "cache_read_tokens", "cacheReadTokens"),
        "cache_read_tokens": ("cache_read_tokens", "cacheReadTokens", "cached_input_tokens", "cachedInputTokens"),
        "cache_write_tokens": ("cache_write_tokens", "cacheWriteTokens"),
        "output_tokens": ("output_tokens", "outputTokens", "completion_tokens", "completionTokens"),
        "reasoning_tokens": ("reasoning_tokens", "reasoningTokens"),
        "total_tokens": ("total_tokens", "totalTokens"),
        "reported_cost_usd": ("cost_usd", "costUsd", "cost"),
    }
    for document in _json_documents(text):
        for item in _walk_dicts(document):
            candidate = item.get("usage") if isinstance(item.get("usage"), dict) else item
            identity = id(candidate)
            if identity in seen_candidates:
                continue
            if not any(alias in candidate for names in aliases.values() for alias in names):
                continue
            seen_candidates.add(identity)
            row: dict[str, Any] = {}
            for target, names in aliases.items():
                row[target] = next((candidate[name] for name in names if name in candidate), None)
            rows.append(row)
    if not rows:
        return None
    result = {key: _sum_optional(rows, key) for key in aliases}
    if result["total_tokens"] is None:
        input_tokens = result["input_tokens"]
        output_tokens = result["output_tokens"]
        if input_tokens is not None and output_tokens is not None:
            result["total_tokens"] = input_tokens + output_tokens
    return result


def capture_attempt_usage(tool: str, model: str, log_text: str, run_dir: Path) -> dict[str, Any]:
    try:
        metrics: dict[str, Any] | None = None
        if tool == "devin":
            export = load_state(run_dir / "devin-export.json")
            final = export.get("final_metrics")
            if isinstance(final, dict):
                prompt = _number(final.get("total_prompt_tokens"))
                completion = _number(final.get("total_completion_tokens"))
                metrics = {
                    "input_tokens": prompt,
                    "cached_input_tokens": _number(final.get("total_cached_tokens")),
                    "cache_read_tokens": _number(final.get("total_cached_tokens")),
                    "cache_write_tokens": None,
                    "output_tokens": completion,
                    "reasoning_tokens": None,
                    "total_tokens": prompt + completion if prompt is not None and completion is not None else None,
                    "reported_cost_usd": None,
                }
        elif tool == "opencode":
            metrics = _usage_from_opencode(log_text)
        elif tool == "cursor":
            metrics = _usage_from_cursor(log_text)
        if metrics is None or metrics.get("total_tokens") is None:
            return empty_usage(tool, model)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        return empty_usage(tool, model, str(error))

    classification = billing_class(tool, model)
    return {
        "source": "provider-reported",
        **metrics,
        "billing_class": classification,
        "actual_charge_usd": 0 if classification == "free" else None,
    }


def report_text_from_log(tool: str, log_text: str) -> str:
    if tool == "devin":
        return log_text
    documents = _json_documents(log_text)
    if not documents:
        return log_text
    text_values: list[str] = []
    if tool == "opencode":
        for document in documents:
            if not isinstance(document, dict) or document.get("type") != "text":
                continue
            part = document.get("part")
            value = part.get("text") if isinstance(part, dict) and part.get("type") == "text" else None
            if isinstance(value, str):
                text_values.append(value)
    elif tool == "cursor":
        for document in documents:
            if not isinstance(document, dict):
                continue
            if document.get("type") == "assistant":
                message = document.get("message")
                content = message.get("content") if isinstance(message, dict) else None
                if isinstance(content, list):
                    for item in content:
                        value = item.get("text") if isinstance(item, dict) and item.get("type") == "text" else None
                        if isinstance(value, str):
                            text_values.append(value)
            if document.get("type") == "tool_call":
                tool_call = document.get("tool_call")
                plan_call = tool_call.get("createPlanToolCall") if isinstance(tool_call, dict) else None
                plan_args = plan_call.get("args") if isinstance(plan_call, dict) else None
                plan = plan_args.get("plan") if isinstance(plan_args, dict) else None
                if isinstance(plan, str):
                    text_values.append(plan)
            if document.get("type") == "result" and isinstance(document.get("result"), str):
                text_values.append(document["result"])
    structured = [
        value
        for value in text_values
        if "STATUS:" in value and "MODEL:" in value and "CLOSURE_RECOMMENDATION:" in value
    ]
    if structured:
        return structured[-1]
    return "\n".join(text_values) if text_values else log_text


def provider_session_ids(log_text: str) -> list[str]:
    identifiers: list[str] = []
    for document in _json_documents(log_text):
        for item in _walk_dicts(document):
            for key in ("sessionID", "sessionId", "session_id", "chatId", "chat_id"):
                value = item.get(key)
                if isinstance(value, str) and value and value not in identifiers:
                    identifiers.append(value)
    return identifiers


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def codex_usage_delta(session_path: Path, started_at: str, finished_at: str) -> dict[str, Any]:
    unavailable = empty_usage("codex", "codex")
    unavailable["billing_class"] = "included-codex"
    snapshots: list[tuple[datetime, dict[str, Any]]] = []
    try:
        for line in session_path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = event.get("payload")
            if event.get("type") != "event_msg" or not isinstance(payload, dict) or payload.get("type") != "token_count":
                continue
            info = payload.get("info")
            usage = info.get("total_token_usage") if isinstance(info, dict) else None
            timestamp = event.get("timestamp")
            if isinstance(timestamp, str) and isinstance(usage, dict):
                snapshots.append((_parse_time(timestamp), usage))
        start = _parse_time(started_at)
        finish = _parse_time(finished_at)
    except (OSError, TypeError, ValueError) as error:
        unavailable["error"] = str(error)
        return unavailable
    before = [item for item in snapshots if item[0] <= start]
    after = [item for item in snapshots if item[0] >= finish]
    if not before or not after:
        unavailable["error"] = "no Codex token snapshots surround the selected run window"
        return unavailable
    baseline = max(before, key=lambda item: item[0])[1]
    final = min(after, key=lambda item: item[0])[1]
    fields = {
        "input_tokens": "input_tokens",
        "cached_input_tokens": "cached_input_tokens",
        "cache_read_tokens": "cached_input_tokens",
        "cache_write_tokens": "cache_write_input_tokens",
        "output_tokens": "output_tokens",
        "reasoning_tokens": "reasoning_output_tokens",
        "total_tokens": "total_tokens",
    }
    result: dict[str, Any] = {
        "source": "codex-session-delta",
        "reported_cost_usd": None,
        "billing_class": "included-codex",
        "actual_charge_usd": None,
    }
    for target, source in fields.items():
        before_value = _number(baseline.get(source))
        after_value = _number(final.get(source))
        result[target] = max(0, after_value - before_value) if before_value is not None and after_value is not None else None
    return result


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
        refresh_approval_state(run_dir, state)
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
        lambda: {"runs": 0, "completed": 0, "duration": 0.0, "results": collections.Counter()}
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
            item["completed"] += int(record.get("result") in {"accepted", "worker-complete", "approved"})
            item["duration"] += float(record.get("duration_seconds", 0))
            item["results"][str(record.get("result", "unknown"))] += 1
    rows = []
    for (model, task_type), item in aggregate.items():
        rows.append(
            {
                "model": model,
                "task_type": task_type,
                "runs": item["runs"],
                "completion_rate": round(item["completed"] / item["runs"], 3),
                "average_duration_seconds": round(item["duration"] / item["runs"], 2),
                "results": dict(item["results"]),
            }
        )
    rows.sort(key=lambda row: (row["task_type"], -row["completion_rate"], -row["runs"], row["model"]))
    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
    else:
        print("TASK\tMODEL\tRUNS\tCOMPLETE_RATE\tAVG_SECONDS\tRESULTS")
        for row in rows:
            print(f"{row['task_type']}\t{row['model']}\t{row['runs']}\t{row['completion_rate']}\t{row['average_duration_seconds']}\t{json.dumps(row['results'], sort_keys=True)}")
    return 0


USAGE_TOTAL_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "output_tokens",
    "reasoning_tokens",
    "total_tokens",
    "reported_cost_usd",
)


def _empty_totals() -> dict[str, int | float]:
    return {field: 0 for field in USAGE_TOTAL_FIELDS}


def _add_usage(totals: dict[str, int | float], usage: dict[str, Any]) -> None:
    for field in USAGE_TOTAL_FIELDS:
        value = _number(usage.get(field))
        if value is not None:
            totals[field] += value


def _resolved_attempt_usage(
    tool: str,
    model: str,
    attempt: dict[str, Any],
    attempt_count: int,
    run_dir: Path,
) -> dict[str, Any]:
    usage = attempt.get("usage")
    if isinstance(usage, dict):
        return usage
    if tool == "devin" and attempt_count != 1:
        return {}
    log_text = ""
    log_value = attempt.get("log")
    if isinstance(log_value, str):
        try:
            log_text = Path(log_value).read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
    return capture_attempt_usage(tool, model, log_text, run_dir)


def build_usage_report(args: argparse.Namespace) -> dict[str, Any]:
    selected: list[tuple[Path, dict[str, Any]]] = []
    for run_dir, state in iter_states(args.state_root):
        if args.run and state.get("run_id", run_dir.name) != args.run:
            continue
        selected.append((run_dir, state))

    external = _empty_totals()
    coverage = {"attempts": 0, "measured": 0, "unavailable": 0}
    grouped: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    known_actual_charge = 0.0
    unknown_actual_charge = 0
    for run_dir, state in selected:
        tool = str(state.get("tool", "unknown"))
        task_type = str(state.get("task_type", "unknown"))
        attempts = state.get("attempts", [])
        if not isinstance(attempts, list):
            continue
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            coverage["attempts"] += 1
            model = str(attempt.get("model", "unknown"))
            usage = _resolved_attempt_usage(tool, model, attempt, len(attempts), run_dir)
            if not isinstance(usage, dict) or _number(usage.get("total_tokens")) is None:
                coverage["unavailable"] += 1
                continue
            coverage["measured"] += 1
            _add_usage(external, usage)
            classification = str(usage.get("billing_class", billing_class(tool, model)))
            attempt_time = attempt.get("started_at") or state.get("created_at")
            date = str(attempt_time)[:10] if isinstance(attempt_time, str) else "unknown"
            key = (date, tool, model, task_type, classification)
            if key not in grouped:
                grouped[key] = {
                    "date": date,
                    "tool": tool,
                    "model": model,
                    **model_identity(tool, model),
                    "task_type": task_type,
                    "billing_class": classification,
                    "attempts": 0,
                    **_empty_totals(),
                }
            grouped[key]["attempts"] += 1
            _add_usage(grouped[key], usage)
            actual_charge = _number(usage.get("actual_charge_usd"))
            if actual_charge is None:
                unknown_actual_charge += 1
            else:
                known_actual_charge += float(actual_charge)

    report: dict[str, Any] = {
        "generated_at": utc_now(),
        "runs": len(selected),
        "coverage": coverage,
        "external": {
            **external,
            "actual_charge_usd_known": round(known_actual_charge, 6),
            "actual_charge_unknown_attempts": unknown_actual_charge,
        },
        "groups": sorted(
            grouped.values(), key=lambda row: (row["date"], row["tool"], row["model"], row["task_type"])
        ),
        "codex": None,
        "delegated_share": None,
    }
    if args.codex_session and selected:
        starts: list[str] = []
        finishes: list[str] = []
        for _, state in selected:
            attempts = state.get("attempts") if isinstance(state.get("attempts"), list) else []
            attempt_starts = [item.get("started_at") for item in attempts if isinstance(item, dict) and isinstance(item.get("started_at"), str)]
            attempt_finishes = [item.get("finished_at") for item in attempts if isinstance(item, dict) and isinstance(item.get("finished_at"), str)]
            state_start = state.get("created_at")
            state_finish = state.get("finished_at") or state.get("updated_at")
            if attempt_starts:
                starts.append(min(attempt_starts, key=_parse_time))
            elif isinstance(state_start, str):
                starts.append(state_start)
            if attempt_finishes:
                finishes.append(max(attempt_finishes, key=_parse_time))
            elif isinstance(state_finish, str):
                finishes.append(state_finish)
        if starts and finishes:
            start = min(starts, key=_parse_time)
            finish = max(finishes, key=_parse_time)
            report["codex"] = codex_usage_delta(args.codex_session, start, finish)
            external_total = _number(external.get("total_tokens"))
            codex_total = _number(report["codex"].get("total_tokens"))
            if (
                coverage["measured"] > 0
                and external_total is not None
                and codex_total is not None
                and external_total + codex_total > 0
            ):
                report["delegated_share"] = round(external_total / (external_total + codex_total), 6)

    return report


def usage_report_command(args: argparse.Namespace) -> int:
    report = build_usage_report(args)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    coverage = report["coverage"]
    external = report["external"]
    print("DATE\tPROVIDER/MODEL\tTASK\tBILLING\tATTEMPTS\tINPUT\tCACHE_READ\tOUTPUT\tREASONING\tTOTAL\tREPORTED_USD")
    for row in report["groups"]:
        print(
            f"{row['date']}\t{row['tool']}/{row['model']}\t{row['task_type']}\t{row['billing_class']}\t{row['attempts']}\t"
            f"{row['input_tokens']}\t{row['cache_read_tokens']}\t{row['output_tokens']}\t"
            f"{row['reasoning_tokens']}\t{row['total_tokens']}\t{row['reported_cost_usd']}"
        )
    print(
        f"coverage={coverage['measured']}/{coverage['attempts']} measured "
        f"external_total={external['total_tokens']} delegated_share={report['delegated_share']}"
    )
    return 0


def _safe_dashboard_label(value: Any, maximum: int = 120) -> str:
    if not isinstance(value, str):
        return "unknown"
    stripped = value.strip()
    if len(stripped) > maximum or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._:/+@-]*", stripped):
        return "unknown"
    return stripped


def _safe_dashboard_task_type(value: Any) -> str:
    task_type = _safe_dashboard_label(value)
    return task_type if task_type in DASHBOARD_TASK_TYPES else "unknown"


def _safe_attempt_rows(state_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run_dir, state in iter_states(state_root):
        provider = _safe_dashboard_label(state.get("tool"))
        task_type = _safe_dashboard_task_type(state.get("task_type"))
        result = _safe_dashboard_label(state.get("state") or state.get("decision"))
        attempts = state.get("attempts", [])
        if not isinstance(attempts, list):
            continue
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            raw_model = _safe_dashboard_label(attempt.get("model"))
            identity = model_identity(provider, raw_model)
            usage = _resolved_attempt_usage(provider, raw_model, attempt, len(attempts), run_dir)
            total_tokens = _number(usage.get("total_tokens"))
            timestamp = attempt.get("started_at") or state.get("created_at")
            row: dict[str, Any] = {
                "timestamp": timestamp if isinstance(timestamp, str) else None,
                "provider": provider,
                **identity,
                "task_type": task_type,
                "result": _safe_dashboard_label(attempt.get("state") or attempt.get("decision") or result),
                "usage_available": total_tokens is not None,
                "billing_class": str(usage.get("billing_class") or billing_class(provider, raw_model)),
            }
            for field in USAGE_TOTAL_FIELDS:
                row[field] = _number(usage.get(field))
            actual_charge = _number(usage.get("actual_charge_usd"))
            row["actual_charge_usd"] = actual_charge
            rows.append(row)
    return rows


def build_dashboard_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    report_args = argparse.Namespace(
        state_root=args.state_root,
        run=None,
        codex_session=args.codex_session,
        json=True,
    )
    report = build_usage_report(report_args)
    attempts = _safe_attempt_rows(args.state_root)
    groups: dict[tuple[Any, ...], dict[str, Any]] = {}
    trends: dict[str, dict[str, Any]] = {}
    timestamps = [row["timestamp"] for row in attempts if isinstance(row.get("timestamp"), str)]
    for attempt in attempts:
        date = str(attempt["timestamp"])[:10] if attempt["timestamp"] else "unknown"
        key = (
            date,
            attempt["provider"],
            attempt["raw_model"],
            attempt["model_family"],
            attempt["variant"],
            attempt["task_type"],
            attempt["result"],
            attempt["billing_class"],
        )
        if key not in groups:
            groups[key] = {
                "date": date,
                "provider": attempt["provider"],
                "raw_model": attempt["raw_model"],
                "model_family": attempt["model_family"],
                "display_name": attempt["display_name"],
                "variant": attempt["variant"],
                "task_type": attempt["task_type"],
                "result": attempt["result"],
                "billing_class": attempt["billing_class"],
                "attempts": 0,
                "measured": 0,
                "actual_charge_usd_known": 0.0,
                "actual_charge_unknown_attempts": 0,
                **_empty_totals(),
            }
        group = groups[key]
        group["attempts"] += 1
        group["measured"] += int(attempt["usage_available"])
        _add_usage(group, attempt)
        actual_charge = attempt["actual_charge_usd"]
        if actual_charge is None:
            group["actual_charge_unknown_attempts"] += int(attempt["usage_available"])
        else:
            group["actual_charge_usd_known"] += float(actual_charge)
        if date not in trends:
            trends[date] = {
                "date": date,
                "attempts": 0,
                "measured": 0,
                "unavailable": 0,
                **_empty_totals(),
            }
        trend = trends[date]
        trend["attempts"] += 1
        trend["measured"] += int(attempt["usage_available"])
        trend["unavailable"] += int(not attempt["usage_available"])
        _add_usage(trend, attempt)

    coverage = report["coverage"]
    attempt_count = int(coverage["attempts"])
    measured_count = int(coverage["measured"])
    external = report["external"]
    codex = report["codex"] if isinstance(report.get("codex"), dict) else None
    snapshot = {
        "schema_version": 1,
        "generated_at": report["generated_at"],
        "window": {
            "from": min(timestamps, key=_parse_time) if timestamps else None,
            "to": max(timestamps, key=_parse_time) if timestamps else None,
        },
        "summary": {
            "runs": report["runs"],
            "attempts": attempt_count,
            "measured": measured_count,
            "unavailable": int(coverage["unavailable"]),
            "capture_coverage": round(measured_count / attempt_count, 6) if attempt_count else None,
            "delegated_input_tokens": external["input_tokens"],
            "delegated_output_tokens": external["output_tokens"],
            "delegated_reasoning_tokens": external["reasoning_tokens"],
            "delegated_total_tokens": external["total_tokens"],
            "cache_read_tokens": external["cache_read_tokens"],
            "actual_charge_usd_known": external["actual_charge_usd_known"],
            "actual_charge_unknown_attempts": external["actual_charge_unknown_attempts"],
            "codex_total_tokens": codex.get("total_tokens") if codex else None,
            "delegated_share": report["delegated_share"],
        },
        "groups": sorted(groups.values(), key=lambda row: tuple(str(value) for value in key_fields(row))),
        "trends": sorted(trends.values(), key=lambda row: row["date"]),
        "attempts": sorted(attempts, key=lambda row: str(row["timestamp"] or ""), reverse=True),
        "coverage": coverage,
    }
    return snapshot


def key_fields(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("date"),
        row.get("provider"),
        row.get("model_family"),
        row.get("raw_model"),
        row.get("task_type"),
        row.get("result"),
        row.get("billing_class"),
    )


def validate_dashboard_snapshot(snapshot: dict[str, Any]) -> None:
    expected_fields = {
        "schema_version",
        "generated_at",
        "window",
        "summary",
        "groups",
        "trends",
        "attempts",
        "coverage",
    }
    if set(snapshot) != expected_fields:
        raise ValueError("unexpected dashboard fields")
    if snapshot.get("schema_version") != 1:
        raise ValueError("unsupported dashboard schema version")
    summary = snapshot.get("summary")
    coverage = snapshot.get("coverage")
    groups = snapshot.get("groups")
    attempts = snapshot.get("attempts")
    if not isinstance(summary, dict) or not isinstance(coverage, dict):
        raise ValueError("dashboard summary and coverage must be objects")
    if not isinstance(groups, list) or not isinstance(attempts, list):
        raise ValueError("dashboard groups and attempts must be arrays")
    attempt_total = sum(int(row.get("attempts", 0)) for row in groups if isinstance(row, dict))
    measured_total = sum(int(row.get("measured", 0)) for row in groups if isinstance(row, dict))
    if attempt_total != summary.get("attempts") or len(attempts) != summary.get("attempts"):
        raise ValueError("inconsistent dashboard attempt totals")
    if measured_total != summary.get("measured"):
        raise ValueError("inconsistent dashboard measured totals")
    if coverage != {
        "attempts": summary.get("attempts"),
        "measured": summary.get("measured"),
        "unavailable": summary.get("unavailable"),
    }:
        raise ValueError("inconsistent dashboard coverage totals")
    if sum(int(bool(row.get("usage_available"))) for row in attempts if isinstance(row, dict)) != summary.get("measured"):
        raise ValueError("inconsistent dashboard attempt coverage")
    for group_field, summary_field in (
        ("total_tokens", "delegated_total_tokens"),
        ("input_tokens", "delegated_input_tokens"),
        ("output_tokens", "delegated_output_tokens"),
        ("reasoning_tokens", "delegated_reasoning_tokens"),
        ("cache_read_tokens", "cache_read_tokens"),
    ):
        grouped_total = sum(
            value
            for row in groups
            if isinstance(row, dict)
            for value in [_number(row.get(group_field))]
            if value is not None
        )
        if grouped_total != summary.get(summary_field):
            raise ValueError(f"inconsistent dashboard {group_field} totals")


def dashboard_export_command(args: argparse.Namespace) -> int:
    try:
        snapshot = build_dashboard_snapshot(args)
        validate_dashboard_snapshot(snapshot)
        atomic_write_json(args.output.expanduser().resolve(), snapshot)
    except (OSError, TypeError, ValueError) as error:
        print(f"dashboard export failed: {error}", file=sys.stderr)
        return 2
    print(args.output.expanduser().resolve())
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
    snapshot = {
        "refreshed_at": utc_now(),
        "models": models,
        "free_opencode": assess_free_models(
            models,
            task_type=args.task,
            history_path=args.state_root.parent / "model-history.jsonl",
        ),
    }
    snapshot_path = args.state_root.parent / "model-snapshot.json"
    atomic_write_json(snapshot_path, snapshot)
    if args.json:
        print(json.dumps(snapshot, indent=2, sort_keys=True))
    else:
        print("\n".join(models))
        print(f"snapshot={snapshot_path}", file=sys.stderr)
    return 0


def canonical_diff(workdir: Path, base_commit: str) -> str:
    tracked = subprocess.run(
        ["git", "-C", str(workdir), "diff", "--binary", "--no-ext-diff", base_commit, "--"],
        text=True,
        capture_output=True,
    )
    if tracked.returncode != 0:
        raise RuntimeError(tracked.stderr.strip() or "could not build tracked diff")
    untracked = subprocess.run(
        ["git", "-C", str(workdir), "ls-files", "--others", "--exclude-standard", "-z"],
        capture_output=True,
    )
    if untracked.returncode != 0:
        raise RuntimeError(untracked.stderr.decode(errors="replace").strip() or "could not list untracked files")
    chunks = [tracked.stdout]
    for raw_path in untracked.stdout.split(b"\0"):
        if not raw_path:
            continue
        path = raw_path.decode("utf-8", errors="surrogateescape")
        result = subprocess.run(
            ["git", "diff", "--no-index", "--binary", "--", "/dev/null", path],
            cwd=workdir,
            text=True,
            capture_output=True,
        )
        if result.returncode not in {0, 1}:
            raise RuntimeError(result.stderr.strip() or f"could not diff untracked path {path}")
        chunks.append(result.stdout)
    return "".join(chunks)


def review_diff(state: dict[str, Any]) -> tuple[str, str]:
    workdir = Path(str(state.get("workdir", ""))).expanduser().resolve()
    base_commit = str(state.get("base_commit", ""))
    if not workdir.is_dir() or not base_commit:
        raise ValueError("run is missing a usable workdir or base_commit")
    diff = canonical_diff(workdir, base_commit)
    return diff, hashlib.sha256(diff.encode("utf-8", errors="surrogateescape")).hexdigest()


def model_family(model: str) -> str:
    return str(model_identity("", model)["model_family"])


def refresh_approval_state(run_dir: Path, state: dict[str, Any]) -> None:
    review = state.get("review")
    if state.get("state") != "approved" or not isinstance(review, dict):
        return
    try:
        _diff, current_hash = review_diff(state)
    except (OSError, RuntimeError, ValueError):
        return
    if current_hash == review.get("diff_hash"):
        return
    review["status"] = "stale"
    review["invalidated_at"] = utc_now()
    state["state"] = "codex-review-required"
    state["decision"] = "pending"
    save_state(run_dir, state)


def review_packet_command(args: argparse.Namespace) -> int:
    try:
        run_dir = resolve_run_dir(args.state_root, args.run)
        state = load_state(run_dir / "state.json")
        diff, diff_hash = review_diff(state)
    except (FileNotFoundError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(error, file=sys.stderr)
        return 2
    if state.get("state") not in {
        "worker-complete",
        "pre-review-complete",
        "changes-required",
        "codex-review-required",
    }:
        print(f"run is not ready for a review packet: {state.get('state')}", file=sys.stderr)
        return 2

    if state.get("permission_profile") == "edit" and not args.pre_review_run:
        print("edit work requires a completed external pre-review run", file=sys.stderr)
        return 2

    workdir = Path(str(state.get("workdir", ""))).expanduser().resolve()
    final_status = git(workdir, "status", "--porcelain", check=False)
    if final_status.returncode != 0:
        print(final_status.stderr.strip() or "could not inspect final changed paths", file=sys.stderr)
        return 2
    changed_paths = porcelain_paths(final_status.stdout)
    allowed_paths = (state.get("manifest") or {}).get("allowed_paths")
    if state.get("permission_profile") == "edit" and isinstance(allowed_paths, list) and allowed_paths:
        out_of_scope = [
            path
            for path in changed_paths
            if not path_allowed(path, [item for item in allowed_paths if isinstance(item, str)])
        ]
        if out_of_scope:
            print(f"final diff contains paths outside manifest scope: {', '.join(out_of_scope)}", file=sys.stderr)
            state["state"] = "rejected"
            state["decision"] = "rejected"
            state["out_of_scope_paths"] = out_of_scope
            save_state(run_dir, state)
            return 2

    pre_review: dict[str, Any] | None = None
    if args.pre_review_run:
        try:
            pre_dir = resolve_run_dir(args.state_root, args.pre_review_run)
            pre_state = load_state(pre_dir / "state.json")
        except (FileNotFoundError, OSError, json.JSONDecodeError) as error:
            print(f"invalid pre-review run: {error}", file=sys.stderr)
            return 2
        if pre_state.get("state") != "worker-complete" or pre_state.get("task_type") != "review":
            print("pre-review run must be a completed review worker", file=sys.stderr)
            return 2
        if Path(str(pre_state.get("workdir", ""))).resolve() != Path(str(state.get("workdir", ""))).resolve():
            print("pre-review must inspect the implementation worktree", file=sys.stderr)
            return 2
        implementation_model = str(state.get("active_model") or (state.get("models") or [""])[0])
        reviewer_model = str(pre_state.get("active_model") or (pre_state.get("models") or [""])[0])
        if pre_state.get("tool") == state.get("tool") and model_family(reviewer_model) == model_family(implementation_model):
            print("pre-review must use an independent provider or model family", file=sys.stderr)
            return 2
        pre_review = {
            "run_id": pre_state.get("run_id", pre_dir.name),
            "tool": pre_state.get("tool"),
            "model": pre_state.get("active_model") or (pre_state.get("models") or [None])[0],
            "report": pre_state.get("report"),
        }
        state["state"] = "pre-review-complete"

    diff_path = run_dir / "final.diff"
    diff_path.write_text(diff, encoding="utf-8", errors="surrogateescape")
    diff_path.chmod(0o600)
    acceptance = (state.get("report") or {}).get("acceptance", [])
    packet_path = run_dir / "review-packet.md"
    packet = "\n".join(
        [
            "# Delegated Work Review Packet",
            "",
            f"- Run: `{state.get('run_id', run_dir.name)}`",
            f"- Tool/model: `{state.get('tool', 'unknown')}/{state.get('active_model') or (state.get('models') or ['unknown'])[0]}`",
            f"- Repository: `{state.get('repo', 'unknown')}`",
            f"- Worktree: `{state.get('workdir', 'unknown')}`",
            f"- Base commit: `{state.get('base_commit', 'unknown')}`",
            f"- Diff SHA-256: `{diff_hash}`",
            f"- Changed paths: {', '.join(f'`{path}`' for path in changed_paths) or 'none'}",
            f"- Pre-review: `{pre_review.get('run_id') if pre_review else 'not linked'}`",
            "",
            "## Acceptance evidence",
            "",
            "```json",
            json.dumps(acceptance, indent=2, sort_keys=True),
            "```",
            "",
            "## Pre-review evidence",
            "",
            "```json",
            json.dumps(pre_review, indent=2, sort_keys=True),
            "```",
            "",
            "## Residual risks",
            "",
            str((state.get("manifest") or {}).get("residual_risks", "none reported")),
            "",
            "## Complete final diff",
            "",
            "```diff",
            diff.rstrip(),
            "```",
            "",
        ]
    )
    packet_path.write_text(packet, encoding="utf-8", errors="surrogateescape")
    packet_path.chmod(0o600)
    state["review_packet"] = {
        "created_at": utc_now(),
        "path": str(packet_path),
        "diff_path": str(diff_path),
        "diff_hash": diff_hash,
        "pre_review": pre_review,
    }
    state["state"] = "codex-review-required"
    state["decision"] = "pending"
    state.pop("review", None)
    save_state(run_dir, state)
    print(packet_path)
    return 0


def record_review_command(args: argparse.Namespace) -> int:
    if args.reviewer != "codex":
        print("only reviewer 'codex' may record the final review", file=sys.stderr)
        return 2
    try:
        run_dir = resolve_run_dir(args.state_root, args.run)
        state = load_state(run_dir / "state.json")
    except (FileNotFoundError, OSError, json.JSONDecodeError) as error:
        print(error, file=sys.stderr)
        return 2
    packet = state.get("review_packet")
    if not isinstance(packet, dict):
        print("a current review packet is required before Codex review", file=sys.stderr)
        return 2
    try:
        _diff, current_hash = review_diff(state)
    except (OSError, RuntimeError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2
    if current_hash != packet.get("diff_hash"):
        print("review packet is stale because the final diff changed", file=sys.stderr)
        state["state"] = "codex-review-required"
        state["decision"] = "pending"
        save_state(run_dir, state)
        return 2

    review = {
        "reviewer": "codex",
        "reviewed_at": utc_now(),
        "decision": args.decision,
        "status": "current",
        "diff_hash": current_hash,
        "verification_summary": args.verification_summary,
        "residual_risk": args.residual_risk,
    }
    state["review"] = review
    if args.decision == "approved":
        state["state"] = "approved"
        state["decision"] = "approved"
    elif args.decision == "changes-required":
        cycles = int(state.get("repair_cycles", 0)) + 1
        state["repair_cycles"] = cycles
        state["external_repair_allowed"] = cycles <= 1
        state["state"] = "changes-required"
        state["decision"] = "changes-required"
    else:
        state["state"] = "blocked"
        state["decision"] = "blocked"
    save_state(run_dir, state)
    print(run_dir)
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
    executable = required_executable(args.tool)
    if shutil.which(executable) is None:
        print(f"{executable} is not installed", file=sys.stderr)
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
    if args.tool == "opencode" and any(model.startswith("omlx/") for model in models):
        print("local omlx models are disabled for delegated subagents", file=sys.stderr)
        return 2
    if args.tool == "devin":
        history_path = args.state_root.parent / "model-history.jsonl"
        configured_model = os.environ.get("DEVIN_SWE_MODEL")
        observed_models = observed_devin_models(history_path)
        models = dedupe(resolve_devin_model(model, configured_model, observed_models) for model in models)
    models = rank_models_by_history(
        models,
        args.state_root.parent / "model-history.jsonl",
        args.task,
        preserve_first=args.preserve_first,
    )[: args.max_attempts]

    original_repo = args.workdir
    base_result = git(original_repo, "rev-parse", "HEAD", check=False)
    base_commit = base_result.stdout.strip() if base_result.returncode == 0 else ""
    state: dict[str, Any] = {
        "schema_version": 1,
        "tool": args.tool,
        "task_type": args.task,
        "repo": str(original_repo),
        "base_commit": base_commit,
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

    if args.tool == "cursor":
        input_dir = run_dir / "input"
        input_dir.mkdir(mode=0o700)
        prompt_copy = input_dir / "prompt.txt"
    else:
        prompt_copy = run_dir / "prompt.txt"
    shutil.copyfile(args.prompt_file, prompt_copy)
    prompt_copy.chmod(0o400 if args.tool == "cursor" else 0o600)
    if args.tool == "cursor":
        input_dir.chmod(0o500)
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
            **model_identity(args.tool, model),
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
                env=worker_environment(args),
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
        attempt["usage"] = capture_attempt_usage(args.tool, model, log_text, run_dir)
        session_ids = provider_session_ids(log_text)
        if session_ids:
            attempt["provider_session_ids"] = session_ids

        def append_attempt_history(result: str) -> None:
            append_history(
                args.state_root,
                {
                    "at": utc_now(),
                    "tool": args.tool,
                    "model": model,
                    "task_type": args.task,
                    "result": result,
                    "duration_seconds": attempt["duration_seconds"],
                    "usage": attempt["usage"],
                },
            )

        if terminal_state in {"timeout", "idle-timeout", "resource-limit", "cancelled"}:
            attempt["state"] = terminal_state
            last_terminal_state = terminal_state
            append_attempt_history(terminal_state)
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
                append_attempt_history("died")
                save_state(run_dir, state)
                continue
            if is_availability_failure(log_text, return_code):
                attempt["state"] = "provider-unavailable"
                last_terminal_state = "provider-unavailable"
                append_attempt_history("provider-unavailable")
                save_state(run_dir, state)
                continue
            attempt["state"] = "failed"
            state["state"] = "failed"
            state["decision"] = "rejected"
            state["error"] = f"subagent exited with code {return_code}"
            append_attempt_history("failed")
            save_state(run_dir, state)
            return return_code or 1

        report = parse_report(report_text_from_log(args.tool, log_text), expected_model=model)
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
        append_attempt_history(final_decision)
        save_state(run_dir, state)
        if final_decision == "worker-complete":
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
    run.add_argument("--tool", choices=("opencode", "devin", "cursor"), required=True)
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
    run.add_argument("--max-attempts", type=int, default=int(os.environ.get("SUBAGENT_MAX_ATTEMPTS", "1")))
    run.add_argument("--max-rss-mb", type=float, default=float(os.environ.get("SUBAGENT_MAX_RSS_MB", "4096")))
    run.add_argument("--max-global", type=int, default=int(os.environ.get("SUBAGENT_MAX_GLOBAL", "1")))
    run.add_argument("--max-per-repo", type=int, default=int(os.environ.get("SUBAGENT_MAX_PER_REPO", "1")))
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

    usage = subparsers.add_parser("usage-report", help="summarize delegated worker token usage")
    usage.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    usage.add_argument("--run", help="limit the report to one run id")
    usage.add_argument("--codex-session", type=Path, help="optional Codex rollout JSONL for a supervising-session delta")
    usage.add_argument("--json", action="store_true")
    usage.set_defaults(func=usage_report_command)

    dashboard = subparsers.add_parser("dashboard-export", help="write a sanitized static dashboard snapshot")
    dashboard.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    dashboard.add_argument("--codex-session", type=Path, help="optional Codex rollout JSONL for a supervising-session delta")
    dashboard.add_argument("--output", type=Path, required=True)
    dashboard.set_defaults(func=dashboard_export_command)

    models = subparsers.add_parser("models", help="refresh the live OpenCode model snapshot")
    models.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    models.add_argument("--task", default="scout")
    models.add_argument("--json", action="store_true")
    models.set_defaults(func=models_command)

    packet = subparsers.add_parser("review-packet", help="prepare the final diff for mandatory Codex review")
    packet.add_argument("run")
    packet.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    packet.add_argument("--pre-review-run")
    packet.set_defaults(func=review_packet_command)

    review = subparsers.add_parser("record-review", help="record the mandatory final Codex review")
    review.add_argument("run")
    review.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    review.add_argument("--reviewer", required=True)
    review.add_argument("--decision", choices=("approved", "changes-required", "blocked"), required=True)
    review.add_argument("--verification-summary", required=True)
    review.add_argument("--residual-risk", default="none")
    review.set_defaults(func=record_review_command)

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
