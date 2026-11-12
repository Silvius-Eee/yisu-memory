"""Tests for export_transcripts.py, using fake session logs under a temporary HOME."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / ".agents/skills/obsidian-daily-sync/scripts/export_transcripts.py"


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")


class ExportCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name).resolve()
        self.home = root / "home"
        self.vault = root / "vault"
        (self.vault / "记忆").mkdir(parents=True)
        self.claude_dir = self.home / ".claude/projects" / re.sub(r"[^A-Za-z0-9]", "-", str(self.vault))
        self.output = self.vault / "记忆/原始对话"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def claude_session(self, name: str, turns: list[tuple[str, str]], **extra) -> None:
        records = []
        for minute, (role, text) in enumerate(turns):
            records.append(
                {
                    "type": role,
                    "timestamp": f"2026-11-10T02:0{minute}:00Z",
                    "message": {"content": [{"type": "text", "text": text}]},
                    **extra,
                }
            )
        write_jsonl(self.claude_dir / f"{name}.jsonl", records)

    def run_export(self, *extra: str) -> subprocess.CompletedProcess:
        env = dict(os.environ, HOME=str(self.home))
        args = [sys.executable, str(SCRIPT), "--vault", str(self.vault), *extra]
        return subprocess.run(args, capture_output=True, text=True, env=env)

    def exported(self) -> list[Path]:
        return sorted(self.output.rglob("*.md")) if self.output.exists() else []


class ClaudeSessions(ExportCase):
    def test_exports_user_and_assistant_text(self) -> None:
        self.claude_session("abcdef12-0000", [("user", "今天去游泳了"), ("assistant", "浮起来了吗？")])
        result = self.run_export()
        self.assertEqual(result.returncode, 0, result.stderr)
        (path,) = self.exported()
        self.assertEqual(path.relative_to(self.output).as_posix(), "2026-11/2026-11-10_claude_abcdef12.md")
        text = path.read_text(encoding="utf-8")
        self.assertIn("## 用户 · 11-10 10:00", text)
        self.assertIn("今天去游泳了", text)
        self.assertIn("## 助手 · 11-10 10:01", text)

    def test_user_label_and_timezone_come_from_config(self) -> None:
        config = Path(self.tmp.name) / "vault.json"
        config.write_text(json.dumps({"user_label": "小北", "utc_offset_hours": 0}), encoding="utf-8")
        self.claude_session("abcdef12-0000", [("user", "你好")])
        self.run_export("--config", str(config))
        text = self.exported()[0].read_text(encoding="utf-8")
        self.assertIn("## 小北 · 11-10 02:00", text)

    def test_flag_overrides_config(self) -> None:
        config = Path(self.tmp.name) / "vault.json"
        config.write_text(json.dumps({"user_label": "小北"}), encoding="utf-8")
        self.claude_session("abcdef12-0000", [("user", "你好")])
        self.run_export("--config", str(config), "--user-label", "阿栗")
        self.assertIn("## 阿栗 ·", self.exported()[0].read_text(encoding="utf-8"))

    def test_unknown_config_key_is_rejected(self) -> None:
        config = Path(self.tmp.name) / "vault.json"
        config.write_text(json.dumps({"user_lable": "小北"}), encoding="utf-8")
        result = self.run_export("--config", str(config))
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown keys ['user_lable']", result.stderr)

    def test_system_reminders_and_injected_turns_are_dropped(self) -> None:
        self.claude_session(
            "abcdef12-0000",
            [
                ("user", "<system-reminder>内部提示</system-reminder>真正的话"),
                ("user", "<command-name>/model</command-name>"),
            ],
        )
        self.run_export()
        text = self.exported()[0].read_text(encoding="utf-8")
        self.assertIn("真正的话", text)
        self.assertNotIn("内部提示", text)
        self.assertNotIn("/model", text)

    def test_sidechain_sessions_are_skipped(self) -> None:
        self.claude_session("abcdef12-0000", [("user", "子任务")], isSidechain=True)
        self.run_export()
        self.assertEqual(self.exported(), [])

    def test_excluded_session_is_not_exported(self) -> None:
        self.output.mkdir(parents=True)
        (self.output / "排除清单.txt").write_text("abcdef12 重复会话\n", encoding="utf-8")
        self.claude_session("abcdef12-0000", [("user", "不要导出")])
        self.assertIn("'excluded': 1", self.run_export().stdout)
        self.assertEqual(self.exported(), [])

    def test_second_run_is_unchanged(self) -> None:
        self.claude_session("abcdef12-0000", [("user", "你好")])
        self.run_export()
        self.assertIn("'unchanged': 1", self.run_export().stdout)

    def test_shorter_export_does_not_replace_longer_one(self) -> None:
        self.claude_session("abcdef12-0000", [("user", "你好"), ("assistant", "在呢")])
        self.run_export()
        self.claude_session("abcdef12-0000", [("user", "你好")])
        self.assertIn("'kept_longer_export': 1", self.run_export().stdout)
        self.assertIn("在呢", self.exported()[0].read_text(encoding="utf-8"))
        self.run_export("--rebuild")
        self.assertNotIn("在呢", self.exported()[0].read_text(encoding="utf-8"))

    def test_dry_run_writes_nothing(self) -> None:
        self.claude_session("abcdef12-0000", [("user", "你好")])
        self.assertIn("DRY RUN", self.run_export("--dry-run").stdout)
        self.assertEqual(self.exported(), [])


class CodexSessions(ExportCase):
    def codex_session(self, cwd: Path, **meta) -> None:
        write_jsonl(
            self.home / ".codex/sessions/2026/11/10/rollout.jsonl",
            [
                {
                    "type": "session_meta",
                    "payload": {
                        "id": "fedcba98-1111",
                        "cwd": str(cwd),
                        "timestamp": "2026-11-10T03:00:00Z",
                        **meta,
                    },
                },
                {
                    "type": "response_item",
                    "timestamp": "2026-11-10T03:01:00Z",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "Codex 里说的话"}],
                    },
                },
            ],
        )

    def test_session_in_vault_root_is_exported(self) -> None:
        self.codex_session(self.vault)
        self.run_export()
        (path,) = self.exported()
        self.assertEqual(path.name, "2026-11-10_codex_fedcba98.md")
        self.assertIn("Codex 里说的话", path.read_text(encoding="utf-8"))

    def test_session_in_project_subfolder_is_skipped(self) -> None:
        self.codex_session(self.vault / "项目")
        self.run_export()
        self.assertEqual(self.exported(), [])

    def test_child_thread_is_skipped(self) -> None:
        self.codex_session(self.vault, parent_thread_id="parent")
        self.run_export()
        self.assertEqual(self.exported(), [])


if __name__ == "__main__":
    unittest.main()
