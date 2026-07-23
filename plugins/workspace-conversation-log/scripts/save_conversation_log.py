#!/usr/bin/env python3
"""Save visible Codex conversation turns without copying the raw transcript.

The Codex Stop hook supplies a small JSON object on stdin.  This program reads the
referenced JSONL transcript, keeps only user/assistant messages, redacts common
credential shapes, and atomically rewrites the session log in
``.codex/conversations``.  Logging is deliberately fail-closed: an unknown or
unparseable transcript is never copied verbatim.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time
from typing import Any, Iterable


DEFAULT_MAX_TRANSCRIPT_BYTES = 100 * 1024 * 1024
DEFAULT_RETENTION_DAYS = 90
MAX_RETENTION_DAYS = 10 * 365
VISIBLE_CODEX_EVENTS = {"user_message": "user", "agent_message": "assistant"}
SYSTEM_PREFIXES = (
    "<permissions",
    "<environment_context",
    "<developer",
    "<system",
    "<user_instructions",
    "<apps_instructions",
    "<plugins_instructions",
    "<skills_instructions",
    "<recommended_plugins",
)

ASSIGNMENT_SECRET_RE = re.compile(
    r"(?im)\b("
    r"(?:[A-Z][A-Z0-9_]*(?:API_KEY|SECRET|PASSWORD|TOKEN))|"
    r"OPENAI_API_KEY|AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN|"
    r"DATABASE_URL|REDIS_URL|CELERY_BROKER_URL|AUTHORIZATION|COOKIE"
    r")\b(\s*(?:=|:)\s*)"
    r"(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;\r\n]+)",
)
URL_CREDENTIAL_RE = re.compile(
    r"(?i)\b([a-z][a-z0-9+.-]*://)([^\s/:@]+):([^\s/@]+)@"
)
BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}")
OPENAI_KEY_RE = re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b")
AWS_KEY_RE = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
JWT_RE = re.compile(
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"
)
SAFE_SESSION_RE = re.compile(r"[^A-Za-z0-9._-]+")


def redact_secrets(text: str) -> str:
    """Redact common credential formats while leaving ordinary discussion intact."""

    text = ASSIGNMENT_SECRET_RE.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", text
    )
    text = URL_CREDENTIAL_RE.sub(r"\1[REDACTED]:[REDACTED]@", text)
    text = BEARER_RE.sub("Bearer [REDACTED]", text)
    text = OPENAI_KEY_RE.sub("[REDACTED_OPENAI_KEY]", text)
    text = AWS_KEY_RE.sub("[REDACTED_AWS_KEY]", text)
    return JWT_RE.sub("[REDACTED_JWT]", text)


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") not in {"text", "input_text", "output_text"}:
            continue
        value = block.get("text")
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    return "\n".join(parts).strip()


def _normalise_entry(
    *, timestamp: Any, role: str, phase: Any, message: str
) -> dict[str, str]:
    entry = {
        "timestamp": timestamp if isinstance(timestamp, str) else "",
        "role": role,
        "phase": phase if isinstance(phase, str) and phase else "message",
        "message": redact_secrets(message.strip()),
    }
    return entry


def _event_entry(obj: Any) -> dict[str, str] | None:
    if not isinstance(obj, dict) or obj.get("type") != "event_msg":
        return None
    payload = obj.get("payload")
    if not isinstance(payload, dict):
        return None
    role = VISIBLE_CODEX_EVENTS.get(payload.get("type"))
    message = payload.get("message")
    if not role or not isinstance(message, str) or not message.strip():
        return None
    return _normalise_entry(
        timestamp=obj.get("timestamp"),
        role=role,
        phase=payload.get("phase"),
        message=message,
    )


def _response_entry(obj: Any) -> dict[str, str] | None:
    if not isinstance(obj, dict) or obj.get("type") != "response_item":
        return None
    payload = obj.get("payload")
    if not isinstance(payload, dict) or payload.get("role") not in {"user", "assistant"}:
        return None
    message = _content_text(payload.get("content"))
    if not message or message.lstrip().lower().startswith(SYSTEM_PREFIXES):
        return None
    return _normalise_entry(
        timestamp=obj.get("timestamp"),
        role=payload["role"],
        phase=payload.get("phase"),
        message=message,
    )


def extract_visible_entries(lines: Iterable[str]) -> list[dict[str, str]]:
    """Extract one schema only; prefer event messages to avoid duplicate turns."""

    parsed: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(value, dict):
            parsed.append(value)

    event_entries = [entry for obj in parsed if (entry := _event_entry(obj))]
    if event_entries:
        return event_entries
    return [entry for obj in parsed if (entry := _response_entry(obj))]


def safe_session_id(value: Any, fallback: str = "session") -> str:
    candidate = SAFE_SESSION_RE.sub("_", str(value or "")).strip("._-")[:120]
    if not candidate:
        candidate = SAFE_SESSION_RE.sub("_", fallback).strip("._-")[:120]
    return candidate or "session"


def write_entries_atomically(
    entries: list[dict[str, str]], project_root: Path, session_id: str
) -> Path | None:
    if not entries:
        return None

    destination_dir = project_root / ".codex" / "conversations"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{safe_session_id(session_id)}.jsonl"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=destination_dir,
            prefix=f".{destination.stem}.",
            suffix=".tmp",
            delete=False,
        ) as output:
            temporary_path = Path(output.name)
            for entry in entries:
                output.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")))
                output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        try:
            os.replace(temporary_path, destination)
        except PermissionError:
            # Some Windows file watchers open an existing JSONL without delete
            # sharing, which blocks atomic replacement even though normal writes
            # are allowed. Retry briefly, then use the already-fsynced temp file
            # as the source for an in-place rewrite instead of losing the turn.
            replaced = False
            for _ in range(3):
                time.sleep(0.05)
                try:
                    os.replace(temporary_path, destination)
                    replaced = True
                    break
                except PermissionError:
                    continue
            if not replaced:
                with temporary_path.open("rb") as source, destination.open("wb") as output:
                    shutil.copyfileobj(source, output)
                    output.flush()
                    os.fsync(output.fileno())
        return destination
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def project_root_from_payload(payload: dict[str, Any]) -> Path:
    """Use the nearest Git root so an installed plugin writes into the project."""

    cwd_value = payload.get("cwd")
    cwd = Path(cwd_value) if isinstance(cwd_value, str) and cwd_value else Path.cwd()
    if not cwd.is_dir():
        # Hook commands run with the session cwd. This also recovers from an
        # incorrectly encoded cwd passed by an older Windows shell.
        cwd = Path.cwd()
    cwd = cwd.resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / ".git").exists():
            return candidate
    return cwd


def _max_transcript_bytes() -> int:
    raw = os.getenv("CODEX_CONVERSATION_LOG_MAX_BYTES", "")
    if not raw:
        return DEFAULT_MAX_TRANSCRIPT_BYTES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_TRANSCRIPT_BYTES
    return max(1, min(value, DEFAULT_MAX_TRANSCRIPT_BYTES))


def _retention_days() -> int:
    raw = os.getenv("CODEX_CONVERSATION_LOG_RETENTION_DAYS", "")
    if not raw:
        return DEFAULT_RETENTION_DAYS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_RETENTION_DAYS
    return max(1, min(value, MAX_RETENTION_DAYS))


def prune_expired_conversation_logs(
    project_root: Path,
    *,
    now_timestamp: float | None = None,
) -> int:
    """Delete only expired session JSONL files inside the managed directory."""

    directory = project_root.resolve() / ".codex" / "conversations"
    if not directory.is_dir() or directory.is_symlink():
        return 0

    current_timestamp = time.time() if now_timestamp is None else now_timestamp
    cutoff = current_timestamp - (_retention_days() * 24 * 60 * 60)
    deleted = 0
    for path in directory.iterdir():
        if (
            path.suffix.lower() != ".jsonl"
            or path.is_symlink()
            or not path.is_file()
        ):
            continue
        try:
            resolved = path.resolve(strict=True)
            if resolved.parent != directory or resolved.stat().st_mtime >= cutoff:
                continue
            resolved.unlink()
            deleted += 1
        except OSError:
            # A locked or concurrently replaced log is retried on a later hook.
            continue
    return deleted


def run(payload: Any, project_root: Path | None = None) -> None:
    if not isinstance(payload, dict):
        return
    transcript_value = payload.get("transcript_path")
    if not isinstance(transcript_value, str) or not transcript_value:
        return

    transcript = Path(transcript_value)
    try:
        if not transcript.is_file() or transcript.stat().st_size > _max_transcript_bytes():
            return
        with transcript.open("r", encoding="utf-8", errors="replace") as source:
            entries = extract_visible_entries(source)
        session_id = safe_session_id(payload.get("session_id"), transcript.stem)
        resolved_project_root = project_root or project_root_from_payload(payload)
        write_entries_atomically(
            entries,
            resolved_project_root,
            session_id,
        )
        prune_expired_conversation_logs(resolved_project_root)
    except (OSError, ValueError) as exc:
        # Never print the payload or transcript contents; they may contain secrets.
        print(f"conversation-log: logging skipped ({type(exc).__name__})", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool", choices=["codex"], default="codex")
    parser.parse_args()
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError, TypeError):
        print("conversation-log: invalid hook input; logging skipped", file=sys.stderr)
        return 0
    run(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
