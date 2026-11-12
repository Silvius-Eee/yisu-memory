"""Tests for validate_sync.py, run against copies of the example vault."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / ".agents/skills/obsidian-daily-sync/scripts/validate_sync.py"
DATE = "2026-11-10"


class VaultCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name)
        shutil.copytree(REPO / "记忆", self.vault / "记忆")
        shutil.copytree(REPO / ".codex", self.vault / ".codex")
        self.memory = self.vault / "记忆"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def file(self, prefix: str) -> Path:
        (path,) = self.memory.glob(f"{prefix}_*.md")
        return path

    def edit(self, path: Path, old: str, new: str) -> None:
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def append(self, path: Path, text: str) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(text)

    def run_check(self, *extra: str, mode: str = "daily", date: str = DATE):
        args = [sys.executable, str(SCRIPT), "--vault", str(self.vault), "--mode", mode]
        if date:
            args += ["--date", date]
        return subprocess.run(args + list(extra), capture_output=True, text=True)

    def assert_passes(self, result) -> None:
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("VALIDATION PASSED", result.stdout)

    def assert_fails_with(self, result, fragment: str) -> None:
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(fragment, result.stderr)


class PassingVault(VaultCase):
    def test_example_vault_passes_daily(self) -> None:
        self.assert_passes(self.run_check())

    def test_example_vault_passes_weekly_close(self) -> None:
        self.assert_passes(self.run_check(mode="weekly-close", date="2026-11-07"))

    def test_inactive_weak_tie_is_a_warning_not_an_error(self) -> None:
        result = self.run_check()
        self.assert_passes(result)
        self.assertIn("demotion candidate 陈教练", result.stdout)

    def test_matching_004_hash_passes(self) -> None:
        digest = hashlib.sha256(self.file("004").read_bytes()).hexdigest()
        self.assert_passes(self.run_check("--expected-004-sha", digest))


class DayLedger(VaultCase):
    def test_same_day_in_001_and_005_fails(self) -> None:
        self.append(self.file("001"), "\n### 2026-11-08 周日｜重复\n\n#### 事件\n\n- 重复\n")
        self.edit(
            self.file("001"),
            "## 写入规则",
            "- [[#2026-11-08 周日｜重复|11-08]]\n\n## 写入规则",
        )
        self.assert_fails_with(self.run_check(), "active-week dates must not be duplicated")

    def test_day_without_index_link_fails(self) -> None:
        self.edit(self.file("005"), "- [[#2026-11-09 周一", "- [[#2026-11-19 周一")
        self.assert_fails_with(self.run_check(), "body/index mismatch")

    def test_day_without_event_section_fails(self) -> None:
        self.edit(self.file("005"), "#### 睡前：读书会选书\n", "睡前：读书会选书\n")
        self.edit(self.file("005"), "#### 晚上：游泳课\n", "晚上：游泳课\n")
        self.edit(self.file("005"), "#### 中午：周姐的第二轮意见\n", "中午：周姐的第二轮意见\n")
        self.assert_fails_with(self.run_check(), "2026-11-10 has no #### event section")

    def test_duplicate_day_heading_fails(self) -> None:
        self.append(self.file("005"), "\n### 2026-11-10 周二｜又写了一遍\n\n#### 事件\n\n- 重复\n")
        self.assert_fails_with(self.run_check(), "duplicate day headings ['2026-11-10']")

    def test_duplicate_index_link_fails(self) -> None:
        self.edit(
            self.file("005"),
            "\n---\n",
            "\n- [[#2026-11-10 周二｜重复链接|11-10]]\n\n---\n",
        )
        self.assert_fails_with(self.run_check(), "duplicate day-index links ['2026-11-10']")

    def test_missing_week_range_fails(self) -> None:
        self.edit(self.file("005"), "本周日期：", "日期：")
        self.assert_fails_with(self.run_check(), "missing Sunday-to-Saturday week range")

    def test_day_heading_at_level_two_fails(self) -> None:
        self.edit(self.file("005"), "### 2026-11-10", "## 2026-11-10")
        self.assert_fails_with(self.run_check(), "day headings must use ###")

    def test_days_out_of_order_fail(self) -> None:
        path = self.file("001")
        text = path.read_text(encoding="utf-8")
        first = text.index("### 2026-11-02")
        second = text.index("### 2026-11-05")
        third = text.index("### 2026-11-07")
        swapped = text[:first] + text[second:third] + text[first:second] + text[third:]
        path.write_text(swapped, encoding="utf-8")
        self.assert_fails_with(self.run_check(), "day headings are not chronological")

    def test_missing_month_heading_in_001_fails(self) -> None:
        self.edit(self.file("001"), "## 2026-11\n", "")
        self.assert_fails_with(self.run_check(), "missing month headings ['2026-11']")

    def test_requested_day_missing_from_005_fails(self) -> None:
        result = self.run_check(date="2026-11-12")
        self.assert_fails_with(result, "expected one body heading for 2026-11-12")
        self.assertIn("expected one index link for 2026-11-12", result.stderr)

    def test_week_range_must_start_on_sunday(self) -> None:
        self.edit(self.file("005"), "2026-11-08（周日）至 2026-11-14", "2026-11-09（周日）至 2026-11-15")
        self.assert_fails_with(self.run_check(), "invalid week range")

    def test_day_outside_declared_week_fails(self) -> None:
        self.edit(self.file("005"), "2026-11-08（周日）至 2026-11-14", "2026-11-15（周日）至 2026-11-21")
        self.assert_fails_with(self.run_check(), "day headings outside declared week")


class CheckpointAndMarkdown(VaultCase):
    def checkpoint(self) -> Path:
        return self.vault / ".codex/daily" / f"{DATE}.md"

    def test_pending_checkpoint_after_sync_fails(self) -> None:
        self.edit(self.checkpoint(), "status: finalized", "status: pending")
        self.assert_fails_with(self.run_check(), "status must be finalized")

    def test_checkpoint_without_frontmatter_fails(self) -> None:
        self.checkpoint().write_text("- [生活][fact][already-formal] 没有头信息。\n", encoding="utf-8")
        self.assert_fails_with(self.run_check(), "missing YAML frontmatter")

    def test_checkpoint_for_another_day_fails(self) -> None:
        self.edit(self.checkpoint(), "lived_day: 2026-11-10", "lived_day: 2026-11-09")
        self.assert_fails_with(self.run_check(), "lived_day does not match 2026-11-10")

    def test_pending_checkpoint_for_another_day_is_ignored(self) -> None:
        self.assertIn("status: pending", (self.vault / ".codex/daily/2026-11-11.md").read_text(encoding="utf-8"))
        self.assert_passes(self.run_check())

    def test_pending_entry_after_sync_fails(self) -> None:
        self.append(self.checkpoint(), "- [生活][fact][pending] 还没写进去的事。 -> 005\n")
        self.assert_fails_with(self.run_check(), "contains pending entries")

    def test_trailing_whitespace_fails(self) -> None:
        self.edit(self.file("003"), "## 工作与项目\n", "## 工作与项目  \n")
        self.assert_fails_with(self.run_check(), "trailing whitespace")

    def test_merge_conflict_marker_fails(self) -> None:
        self.append(self.file("002"), "\n<<<<<<< HEAD\n")
        self.assert_fails_with(self.run_check(), "merge-conflict marker")


class SnapshotAndSizes(VaultCase):
    def pad_snapshot_to(self, total: int) -> None:
        current = len(self.file("000").read_text(encoding="utf-8"))
        self.append(self.file("000"), "\n" + "字" * (total - current - 2) + "\n")

    def test_snapshot_over_target_warns(self) -> None:
        self.pad_snapshot_to(5500)
        result = self.run_check()
        self.assert_passes(result)
        self.assertIn("exceeds target 5000", result.stdout)

    def test_snapshot_over_limit_fails(self) -> None:
        self.pad_snapshot_to(6100)
        self.assert_fails_with(self.run_check(), "exceeds limit 6000")

    def test_long_person_card_warns(self) -> None:
        self.edit(self.file("002"), "- **当前定位**：大学同学", "- **当前定位**：" + "很" * 2600 + "大学同学")
        result = self.run_check()
        self.assert_passes(result)
        self.assertIn("card 阿栗 has", result.stdout)

    def test_large_dictionary_warns(self) -> None:
        entries = "".join(f"\n### 词条{n}\n\n- 含义：示例。\n" for n in range(101))
        self.append(self.file("003"), entries)
        result = self.run_check()
        self.assert_passes(result)
        self.assertIn("entries exceeds 100", result.stdout)

    def test_changed_004_with_old_hash_fails(self) -> None:
        digest = hashlib.sha256(self.file("004").read_bytes()).hexdigest()
        self.append(self.file("004"), "\n### 新的失效判断\n")
        self.assert_fails_with(self.run_check("--expected-004-sha", digest), "SHA-256 changed")


class PersonCards(VaultCase):
    def history(self) -> Path:
        return self.memory / "历史" / "002_人物历史卡.md"

    def test_short_card_link_without_history_card_fails(self) -> None:
        self.edit(self.file("002"), "002_人物历史卡#老秦", "002_人物历史卡#老王")
        result = self.run_check()
        self.assert_fails_with(result, "short-card links without a history card ['老王']")
        self.assertIn("cards without a short card ['老秦']", result.stderr)

    def test_full_card_in_both_files_fails(self) -> None:
        self.append(self.history(), "\n### 周姐\n\n- **当前定位**：重复的卡。\n")
        self.edit(
            self.file("002"),
            "## 基础画像",
            "- 周姐短卡。[[记忆/历史/002_人物历史卡#周姐|完整卡]]\n\n## 基础画像",
        )
        self.assert_fails_with(self.run_check(), "full card exists in both files ['周姐']")

    def test_duplicate_history_card_fails(self) -> None:
        self.append(self.history(), "\n### 老秦\n\n- **当前定位**：同一个人的第二张卡。\n")
        self.assert_fails_with(self.run_check(), "duplicate cards ['老秦']")

    def test_returned_card_needs_no_short_card(self) -> None:
        self.append(self.history(), "\n### 小林\n\n已回迁 2026-11-09\n")
        self.assert_passes(self.run_check())


class Layout(VaultCase):
    def test_two_files_with_one_prefix_fail(self) -> None:
        shutil.copy(self.file("003"), self.memory / "003_副本.md")
        self.assert_fails_with(self.run_check(), "expected one 003_*.md")

    def test_missing_file_fails(self) -> None:
        self.file("004").unlink()
        self.assert_fails_with(self.run_check(), "missing required file")

    def test_renamed_memory_folder_with_flag_passes(self) -> None:
        self.memory.rename(self.vault / "memory")
        for path in (self.vault / "memory").rglob("*.md"):
            text = path.read_text(encoding="utf-8").replace("[[记忆/", "[[memory/")
            path.write_text(text, encoding="utf-8")
        self.assert_passes(self.run_check("--memory-dir", "memory"))

    def test_closed_month_in_001_warns(self) -> None:
        result = self.run_check(date="2026-12-01", mode="weekly-close")
        self.assertIn("closed months ready to archive ['2026-11']", result.stdout)


if __name__ == "__main__":
    unittest.main()
