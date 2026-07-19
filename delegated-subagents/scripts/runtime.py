#!/usr/bin/env python3
"""Shared runtime primitives for delegated CLI subagents."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


TERMINAL_STATES = {
    "approved",
    "accepted",
    "rejected",
    "blocked",
    "failed",
    "cancelled",
    "timeout",
    "idle-timeout",
    "resource-limit",
}

FREE_MODEL_TASK_FIT = {
    "north-mini-code-free": {"code-small", "debug", "review"},
    "deepseek-v4-flash-free": {"scout", "bulk", "review", "closure-validation"},
    "nemotron-3-ultra-free": {"scout", "review", "closure-validation"},
    "mimo-v2.5-free": {"scout", "bulk", "review", "closure-validation"},
    "hy3-free": {"scout", "bulk", "review"},
}

HARD_MODEL_FAILURES = {
    "rejected",
    "failed",
    "timeout",
    "idle-timeout",
    "resource-limit",
    "died",
}


@dataclass(frozen=True)
class ParsedReport:
    valid: bool
    status: str
    model: str
    task_type: str
    repo: str
    decision: str
    closure_recommendation: str
    acceptance: list[dict[str, str]]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def free_opencode_models(models: Iterable[str]) -> list[str]:
    """Return every currently visible OpenCode model explicitly marked free."""
    return dedupe(
        model.strip()
        for model in models
        if re.match(r"(?i)^opencode/.*free", model.strip())
    )


def assess_free_models(
    models: Iterable[str], task_type: str, history_path: Path | None = None
) -> list[dict[str, Any]]:
    """Classify live free routes conservatively for one delegated task type."""
    history: dict[str, list[str]] = {}
    if history_path is not None and history_path.exists():
        for line in history_path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            model = record.get("model")
            if not isinstance(model, str) or record.get("task_type") != task_type:
                continue
            history.setdefault(model, []).append(str(record.get("result", "unknown")))

    assessed = []
    for model in free_opencode_models(models):
        slug = model.split("/", 1)[1].lower()
        outcomes = history.get(model, [])
        hard_failures = sum(result in HARD_MODEL_FAILURES for result in outcomes[-5:])
        successes = sum(result in {"worker-complete", "accepted", "approved"} for result in outcomes)
        known_fit = FREE_MODEL_TASK_FIT.get(slug)
        if hard_failures >= 3 and successes == 0:
            status = "excluded"
            reason = f"{hard_failures} recent comparable hard failures"
        elif known_fit is None:
            status = "probe-only"
            reason = "new free model requires a bounded smoke run"
        elif task_type not in known_fit:
            status = "probe-only"
            reason = f"known model is not established for {task_type}"
        else:
            status = "usable"
            reason = "live, task-fit free route"
        assessed.append(
            {
                "model": model,
                "status": status,
                "reason": reason,
                "task_type": task_type,
                "runs": len(outcomes),
                "successes": successes,
                "hard_failures": hard_failures,
            }
        )
    return assessed


def rank_models_by_history(
    models: list[str],
    history_path: Path,
    task_type: str,
    preserve_first: bool,
    minimum_runs: int = 3,
) -> list[str]:
    stats = {model: {"runs": 0, "accepted": 0} for model in models}
    if history_path.exists():
        for line in history_path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            model = record.get("model")
            if model not in stats or record.get("task_type") != task_type:
                continue
            stats[model]["runs"] += 1
            stats[model]["accepted"] += int(
                record.get("result") in {"accepted", "worker-complete", "approved"}
            )

    def sort_key(item: tuple[int, str]) -> tuple[float, float, int]:
        index, model = item
        runs = stats[model]["runs"]
        if runs < minimum_runs:
            return (1, 0, index)
        rate = stats[model]["accepted"] / runs
        bucket = 0 if rate >= 0.5 else 2
        return (bucket, -rate, index)

    if preserve_first and models:
        return [models[0], *[model for _, model in sorted(enumerate(models[1:], start=1), key=sort_key)]]
    return [model for _, model in sorted(enumerate(models), key=sort_key)]


def create_run_dir(root: Path, tool: str) -> Path:
    root = root.expanduser().resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    run_dir = root / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{tool}-{uuid.uuid4().hex[:12]}"
    run_dir.mkdir(mode=0o700)
    return run_dir


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _field(text: str, name: str) -> str:
    matches = re.findall(rf"(?im)^{re.escape(name)}:\s*(.+?)\s*$", text)
    return matches[-1].strip() if matches else ""


def parse_report(text: str, expected_model: str) -> ParsedReport:
    status = _field(text, "STATUS").lower()
    model = _field(text, "MODEL")
    task_type = _field(text, "TASK_TYPE")
    repo = _field(text, "REPO")
    closure = _field(text, "CLOSURE_RECOMMENDATION").lower()
    errors: list[str] = []

    if status not in {"success", "partial", "blocked", "failed"}:
        errors.append("missing or invalid STATUS")
    if not model:
        errors.append("missing MODEL")
    elif model != expected_model:
        errors.append(f"reported model {model!r} does not match launched model {expected_model!r}")
    if not task_type:
        errors.append("missing TASK_TYPE")
    if not repo:
        errors.append("missing REPO")
    if closure not in {
        "ready-for-pr",
        "ready-for-review",
        "needs-fix",
        "blocked",
        "not-implemented",
        "not-applicable",
    }:
        errors.append("missing or invalid CLOSURE_RECOMMENDATION")

    acceptance = []
    for match in re.finditer(r"(?im)^-\s*\[(pass|fail|unknown)\]\s*(.*?)\s*(?:->\s*(.*))?$", text):
        acceptance.append(
            {
                "status": match.group(1).lower(),
                "criterion": match.group(2).strip(),
                "evidence": (match.group(3) or "").strip(),
            }
        )
    if not acceptance:
        errors.append("missing ACCEPTANCE_CRITERIA entries")

    valid = not errors
    if not valid or status == "failed" or any(item["status"] == "fail" for item in acceptance):
        decision = "rejected"
    elif status in {"partial", "blocked"} or any(item["status"] == "unknown" for item in acceptance):
        decision = "needs-follow-up"
    else:
        decision = "worker-complete"

    return ParsedReport(
        valid=valid,
        status=status or "invalid",
        model=model,
        task_type=task_type,
        repo=repo,
        decision=decision,
        closure_recommendation=closure,
        acceptance=acceptance,
        errors=errors,
    )


def is_availability_failure(log_text: str, return_code: int) -> bool:
    if return_code == 0:
        return False
    tail = "\n".join(log_text.splitlines()[-80:])
    explicit_patterns = (
        r"(?i)(provider|model|api).{0,80}(unavailable|overloaded|capacity exhausted)",
        r"(?i)(rate.?limit|quota exhausted|insufficient quota)",
        r"(?i)(provider|model).{0,80}(not found|does not exist|unknown model)",
        r"(?i)(provider|api).{0,80}(http\s*)?(429|502|503|504)\b",
        r"(?i)(authentication|credential).{0,40}(temporarily unavailable)",
    )
    return any(re.search(pattern, tail) for pattern in explicit_patterns)


def capture_process_identity(pid: int) -> dict[str, Any] | None:
    try:
        started = subprocess.check_output(
            ["ps", "-p", str(pid), "-o", "lstart="],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        command = subprocess.check_output(
            ["ps", "-p", str(pid), "-o", "command="],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        pgid = os.getpgid(pid)
    except (OSError, subprocess.CalledProcessError, ProcessLookupError):
        return None
    if not started:
        return None
    start_signature = hashlib.sha256(started.encode("utf-8", errors="replace")).hexdigest()
    command_fingerprint = hashlib.sha256(command.encode("utf-8", errors="replace")).hexdigest()
    return {
        "pid": pid,
        "pgid": pgid,
        "started": started,
        "start_signature": start_signature,
        "command": command,
        "command_fingerprint": command_fingerprint,
    }


def process_matches(identity: dict[str, Any]) -> bool:
    pid = identity.get("pid")
    signature = identity.get("start_signature")
    if not isinstance(pid, int) or pid <= 1 or not isinstance(signature, str):
        return False
    current = capture_process_identity(pid)
    return bool(current and current["start_signature"] == signature and current["pgid"] == identity.get("pgid"))
