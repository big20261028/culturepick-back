from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "save_conversation_log.py"
)
SPEC = importlib.util.spec_from_file_location("save_conversation_log", SCRIPT_PATH)
assert SPEC and SPEC.loader
LOGGER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LOGGER)


def jsonl(*objects: dict) -> str:
    return "\n".join(json.dumps(value) for value in objects) + "\n"


class ConversationLogTests(unittest.TestCase):
    def test_keeps_visible_event_messages_and_filters_other_records(self):
        raw = jsonl(
            {"type": "session_meta", "payload": {"secret": "do-not-copy"}},
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "type": "event_msg",
                "payload": {"type": "user_message", "message": "질문입니다."},
            },
            {"type": "function_call", "payload": {"arguments": "private tool data"}},
            {
                "timestamp": "2026-01-01T00:00:01Z",
                "type": "event_msg",
                "payload": {
                    "type": "agent_message",
                    "phase": "commentary",
                    "message": "확인 중입니다.",
                },
            },
            {
                "timestamp": "2026-01-01T00:00:02Z",
                "type": "event_msg",
                "payload": {
                    "type": "agent_message",
                    "phase": "final_answer",
                    "message": "완료했습니다.",
                },
            },
        )

        entries = LOGGER.extract_visible_entries(raw.splitlines())

        self.assertEqual([entry["role"] for entry in entries], ["user", "assistant", "assistant"])
        self.assertEqual(entries[-1]["phase"], "final_answer")
        self.assertNotIn("private tool data", json.dumps(entries, ensure_ascii=False))
        self.assertNotIn("do-not-copy", json.dumps(entries, ensure_ascii=False))

    def test_redacts_credentials_without_redacting_plain_variable_discussion(self):
        message = (
            "API_KEY 검증 필요\n"
            "OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz\n"
            "DATABASE_URL=postgresql://admin:supersecret@example.test/db\n"
            "Authorization: Bearer eyJheader123456.payload123456.signature123456"
        )

        redacted = LOGGER.redact_secrets(message)

        self.assertIn("API_KEY 검증 필요", redacted)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", redacted)
        self.assertNotIn("supersecret", redacted)
        self.assertNotIn("eyJheader", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_uses_response_items_only_as_a_fallback_and_skips_system_context(self):
        raw = jsonl(
            {
                "type": "response_item",
                "payload": {
                    "role": "user",
                    "content": [{"type": "input_text", "text": "<environment_context>hidden"}],
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "role": "user",
                    "content": [{"type": "input_text", "text": "실제 요청"}],
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "실제 응답"}],
                },
            },
        )

        entries = LOGGER.extract_visible_entries(raw.splitlines())

        self.assertEqual([entry["message"] for entry in entries], ["실제 요청", "실제 응답"])

    def test_invalid_or_empty_transcript_fails_closed(self):
        self.assertEqual(LOGGER.extract_visible_entries(["not-json", "{}"]), [])
        with tempfile.TemporaryDirectory() as temporary:
            project_root = Path(temporary)
            result = LOGGER.write_entries_atomically([], project_root, "session")
            self.assertIsNone(result)
            self.assertFalse((project_root / ".codex" / "conversations").exists())

    def test_run_writes_normalised_jsonl_atomically_with_safe_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            transcript = root / "source.jsonl"
            transcript.write_text(
                jsonl(
                    {
                        "timestamp": "2026-01-01T00:00:00Z",
                        "type": "event_msg",
                        "payload": {"type": "user_message", "message": "hello"},
                    }
                ),
                encoding="utf-8",
            )

            LOGGER.run(
                {
                    "transcript_path": str(transcript),
                    "session_id": "../../unsafe session",
                },
                project_root=root,
            )

            files = list((root / ".codex" / "conversations").glob("*.jsonl"))
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0].name, "unsafe_session.jsonl")
            saved = [json.loads(line) for line in files[0].read_text(encoding="utf-8").splitlines()]
            self.assertEqual(saved[0]["message"], "hello")
            self.assertEqual(list((root / ".codex" / "conversations").glob("*.tmp")), [])

    def test_project_root_uses_nearest_git_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".git").mkdir()
            nested = root / "apps" / "users"
            nested.mkdir(parents=True)

            detected = LOGGER.project_root_from_payload({"cwd": str(nested)})

            self.assertEqual(detected, root.resolve())

    def test_missing_payload_cwd_falls_back_to_process_cwd(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".git").mkdir()
            nested = root / "한글 경로"
            nested.mkdir()

            with patch.object(LOGGER.Path, "cwd", return_value=nested):
                detected = LOGGER.project_root_from_payload(
                    {"cwd": str(root / "깨진-존재하지-않는-경로")}
                )

            self.assertEqual(detected, root.resolve())

    def test_windows_replace_permission_error_uses_complete_temp_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination_dir = root / ".codex" / "conversations"
            destination_dir.mkdir(parents=True)
            destination = destination_dir / "locked-session.jsonl"
            destination.write_text('{"old":true}\n', encoding="utf-8")
            entries = [
                {
                    "timestamp": "",
                    "role": "user",
                    "phase": "message",
                    "message": "replacement",
                }
            ]

            with patch.object(LOGGER.os, "replace", side_effect=PermissionError):
                result = LOGGER.write_entries_atomically(
                    entries, root, "locked-session"
                )

            self.assertEqual(result, destination)
            saved = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(saved["message"], "replacement")
            self.assertEqual(list(destination_dir.glob("*.tmp")), [])

    def test_prunes_only_expired_session_jsonl_and_preserves_handoff(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination_dir = root / ".codex" / "conversations"
            destination_dir.mkdir(parents=True)
            old_log = destination_dir / "old-session.jsonl"
            recent_log = destination_dir / "recent-session.jsonl"
            ignored_file = destination_dir / "notes.txt"
            handoff = root / ".codex" / "conversation-log.md"
            for path in (old_log, recent_log, ignored_file):
                path.write_text("content\n", encoding="utf-8")
            handoff.write_text("# durable handoff\n", encoding="utf-8")

            now = time.time()
            expired = now - (91 * 24 * 60 * 60)
            os.utime(old_log, (expired, expired))
            os.utime(ignored_file, (expired, expired))

            deleted = LOGGER.prune_expired_conversation_logs(
                root,
                now_timestamp=now,
            )

            self.assertEqual(deleted, 1)
            self.assertFalse(old_log.exists())
            self.assertTrue(recent_log.exists())
            self.assertTrue(ignored_file.exists())
            self.assertEqual(
                handoff.read_text(encoding="utf-8"),
                "# durable handoff\n",
            )

    def test_retention_days_environment_is_bounded_and_invalid_value_is_safe(self):
        with patch.dict(
            LOGGER.os.environ,
            {"CODEX_CONVERSATION_LOG_RETENTION_DAYS": "0"},
        ):
            self.assertEqual(LOGGER._retention_days(), 1)
        with patch.dict(
            LOGGER.os.environ,
            {"CODEX_CONVERSATION_LOG_RETENTION_DAYS": "not-a-number"},
        ):
            self.assertEqual(
                LOGGER._retention_days(),
                LOGGER.DEFAULT_RETENTION_DAYS,
            )


if __name__ == "__main__":
    unittest.main()
