#!/usr/bin/env python3
"""Validate the structural invariants of a layered-memory vault after a sync.

The six canonical files are located by numeric prefix (``000_*.md`` ... ``005_*.md``)
inside the memory directory, so they can carry any descriptive name.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import vault_config


DAY_HEADING = re.compile(r"^### (\d{4}-\d{2}-\d{2})\b", re.MULTILINE)
BAD_DAY_HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2})\b", re.MULTILINE)
MONTH_HEADING = re.compile(r"^## (\d{4}-\d{2})$", re.MULTILINE)
CONFLICT_MARKER = re.compile(r"^(?:<<<<<<<|=======|>>>>>>>)", re.MULTILINE)
WEEK_RANGE = re.compile(
    r"本周日期：(\d{4}-\d{2}-\d{2})（周日）至 (\d{4}-\d{2}-\d{2})（周六）"
)
SNAPSHOT_TARGET_CHARS = 5000
SNAPSHOT_MAX_CHARS = 6000
CARD_WARN_CHARS = 2500
DICTIONARY_WARN_ENTRIES = 100
PERSON_INACTIVE_DAYS = 60
DEMOTABLE_SECTIONS = ("职场圈", "弱连接")
SHORT_DATE = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?![\d/])")
PEOPLE_END_HEADING = "## 基础画像"
HISTORY_SECTION = "历史档案"
HISTORY_DIR = "历史"
HISTORY_CARDS = "002_人物历史卡"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def duplicates(items: list[str]) -> list[str]:
    return sorted({item for item in items if items.count(item) > 1})


def validate_day_file(
    path: Path,
    *,
    require_date: str | None,
    require_months: bool,
) -> tuple[list[str], list[str]]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    days = DAY_HEADING.findall(text)

    if bad := BAD_DAY_HEADING.findall(text):
        errors.append(f"{path.name}: day headings must use ###, found ## for {bad}")
    if dupes := duplicates(days):
        errors.append(f"{path.name}: duplicate day headings {dupes}")
    if days != sorted(days):
        errors.append(f"{path.name}: day headings are not chronological")

    index_days = re.findall(r"\[\[#(\d{4}-\d{2}-\d{2})\b", text)
    if dupes := duplicates(index_days):
        errors.append(f"{path.name}: duplicate day-index links {dupes}")
    if set(days) != set(index_days):
        missing = sorted(set(days) - set(index_days))
        extra = sorted(set(index_days) - set(days))
        errors.append(
            f"{path.name}: body/index mismatch; missing links={missing}, extra links={extra}"
        )

    if require_months:
        months = set(MONTH_HEADING.findall(text))
        missing_months = sorted({day[:7] for day in days} - months)
        if missing_months:
            errors.append(f"{path.name}: missing month headings {missing_months}")

    if require_date:
        if days.count(require_date) != 1:
            errors.append(
                f"{path.name}: expected one body heading for {require_date}, "
                f"found {days.count(require_date)}"
            )
        if index_days.count(require_date) != 1:
            errors.append(
                f"{path.name}: expected one index link for {require_date}, "
                f"found {index_days.count(require_date)}"
            )

    positions = list(DAY_HEADING.finditer(text))
    for index, match in enumerate(positions):
        end = positions[index + 1].start() if index + 1 < len(positions) else len(text)
        if not re.search(r"^#### \S", text[match.end() : end], re.MULTILINE):
            errors.append(f"{path.name}: {match.group(1)} has no #### event section")

    return errors, days


def validate_markdown(paths: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if CONFLICT_MARKER.search(text):
            errors.append(f"{path.name}: contains a merge-conflict marker")
        trailing = [
            number
            for number, line in enumerate(text.splitlines(), start=1)
            if line.endswith((" ", "\t"))
        ]
        if trailing:
            preview = trailing[:10]
            suffix = "..." if len(trailing) > 10 else ""
            errors.append(f"{path.name}: trailing whitespace on lines {preview}{suffix}")
    return errors


def validate_week_range(path: Path, days: list[str]) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    match = WEEK_RANGE.search(text)
    if not match:
        return [f"{path.name}: missing Sunday-to-Saturday week range"]

    start = date.fromisoformat(match.group(1))
    end = date.fromisoformat(match.group(2))
    if start.weekday() != 6 or end != start + timedelta(days=6):
        errors.append(
            f"{path.name}: invalid week range {start.isoformat()} to {end.isoformat()}"
        )
    outside = sorted(day for day in days if not start <= date.fromisoformat(day) <= end)
    if outside:
        errors.append(f"{path.name}: day headings outside declared week {outside}")
    return errors


def validate_checkpoint(path: Path, lived_day: str) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    frontmatter = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not frontmatter:
        return [f"{path.name}: missing YAML frontmatter"]

    metadata = frontmatter.group(1)
    if not re.search(rf"^lived_day: {re.escape(lived_day)}$", metadata, re.MULTILINE):
        errors.append(f"{path.name}: lived_day does not match {lived_day}")
    if not re.search(r"^status: finalized$", metadata, re.MULTILINE):
        errors.append(f"{path.name}: status must be finalized after formal sync")
    if "[pending]" in text:
        errors.append(f"{path.name}: contains pending entries after formal sync")
    return errors


def last_mentioned(card: str, reference: date) -> date | None:
    """Return the newest M/D date in a card, reading it as the latest past occurrence."""
    newest: date | None = None
    for month, day in SHORT_DATE.findall(card):
        try:
            found = date(reference.year, int(month), int(day))
        except ValueError:
            continue
        if found > reference:
            found = found.replace(year=found.year - 1)
        if newest is None or found > newest:
            newest = found
    return newest


def validate_people(
    path_002: Path, path_history: Path, reference: date, memory_dir: str
) -> tuple[list[str], list[str]]:
    text = path_002.read_text(encoding="utf-8")
    errors: list[str] = []
    warnings: list[str] = []
    end = text.find(PEOPLE_END_HEADING)
    people = text if end == -1 else text[:end]
    sections = re.split(r"(?m)^## (.+)$", people)
    active: set[str] = set()
    for heading, body in zip(sections[1::2], sections[2::2]):
        if heading == HISTORY_SECTION:
            continue
        cards = re.split(r"(?m)^### (.+)$", body)
        for name, card in zip(cards[1::2], cards[2::2]):
            active.add(name)
            if len(card) > CARD_WARN_CHARS:
                warnings.append(f"{path_002.name}: card {name} has {len(card)} chars")
            seen = last_mentioned(card, reference)
            if (
                heading in DEMOTABLE_SECTIONS
                and seen
                and (reference - seen).days > PERSON_INACTIVE_DAYS
            ):
                warnings.append(
                    f"{path_002.name}: demotion candidate {name}, last dated {seen.isoformat()}"
                )

    if not path_history.is_file():
        return errors, warnings
    history = path_history.read_text(encoding="utf-8")
    history_cards = re.split(r"(?m)^### (.+)$", history)
    names = history_cards[1::2]
    if dupes := duplicates(names):
        errors.append(f"{path_history.name}: duplicate cards {dupes}")
    returned = {
        name for name, body in zip(names, history_cards[2::2]) if body.strip().startswith("已回迁")
    }
    history_link = re.compile(
        rf"\[\[{re.escape(memory_dir)}/{HISTORY_DIR}/{HISTORY_CARDS}#([^|\]]+)"
    )
    links = set(history_link.findall(text))
    anchors = set(re.findall(r"(?m)^#### (.+)$", history))
    if missing := sorted(links - set(names) - anchors):
        errors.append(f"{path_002.name}: short-card links without a history card {missing}")
    if orphaned := sorted(set(names) - returned - links):
        errors.append(f"{path_history.name}: cards without a short card {orphaned}")
    if both := sorted((set(names) - returned) & active):
        errors.append(f"{path_002.name}: full card exists in both files {both}")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("daily", "weekly-close"),
        default="daily",
        help="daily expects --date in 005; weekly-close expects it in 001",
    )
    parser.add_argument("--date", help="Lived-day date in YYYY-MM-DD format")
    parser.add_argument("--vault", type=Path, help="Vault root; defaults to this skill's repo")
    parser.add_argument("--config", type=Path, help="Settings file; defaults to the skill's vault.json")
    parser.add_argument("--expected-004-sha", help="Pre-edit SHA-256 for 004")
    parser.add_argument("--memory-dir", help="Memory folder inside the vault")
    parser.add_argument("--checkpoint-dir", help="Daily checkpoint folder inside the vault")
    args = parser.parse_args()

    if args.date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        parser.error("--date must use YYYY-MM-DD")

    try:
        settings = vault_config.load(args.config)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    memory_dir = str(args.memory_dir or settings["memory_dir"])
    checkpoint_dir = str(args.checkpoint_dir or settings["checkpoint_dir"])

    vault = (args.vault or vault_config.default_vault()).resolve()
    memory = vault / memory_dir
    files: dict[str, Path] = {}
    problems: list[str] = []
    for prefix in ("000", "001", "002", "003", "004", "005"):
        found = sorted(memory.glob(f"{prefix}_*.md"))
        if len(found) == 1:
            files[prefix] = found[0]
        elif not found:
            problems.append(f"missing required file: {memory / (prefix + '_*.md')}")
        else:
            names = [path.name for path in found]
            problems.append(f"expected one {prefix}_*.md in {memory}, found {names}")
    if problems:
        print("VALIDATION FAILED", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1

    errors: list[str] = []
    required_in_001 = args.date if args.mode == "weekly-close" else None
    required_in_005 = args.date if args.mode == "daily" else None
    errors_001, days_001 = validate_day_file(
        files["001"], require_date=required_in_001, require_months=True
    )
    errors_005, days_005 = validate_day_file(
        files["005"], require_date=required_in_005, require_months=False
    )
    errors.extend(errors_001)
    errors.extend(errors_005)
    overlap = sorted(set(days_001) & set(days_005))
    if overlap:
        errors.append(f"001/005: active-week dates must not be duplicated {overlap}")
    errors.extend(validate_week_range(files["005"], days_005))

    markdown_paths = list(files.values())
    checkpoints = vault / checkpoint_dir
    if args.date and (checkpoints / f"{args.date}.md").is_file():
        checkpoint = checkpoints / f"{args.date}.md"
        markdown_paths.append(checkpoint)
        errors.extend(validate_checkpoint(checkpoint, args.date))
    errors.extend(validate_markdown(markdown_paths))

    snapshot_chars = len(files["000"].read_text(encoding="utf-8"))
    if snapshot_chars > SNAPSHOT_MAX_CHARS:
        errors.append(
            f"{files['000'].name}: {snapshot_chars} chars exceeds limit {SNAPSHOT_MAX_CHARS}; "
            "apply the 000 eviction rules"
        )
    elif snapshot_chars > SNAPSHOT_TARGET_CHARS:
        print(
            f"WARNING {files['000'].name}: {snapshot_chars} chars exceeds target "
            f"{SNAPSHOT_TARGET_CHARS}"
        )

    reference = date.fromisoformat(args.date) if args.date else date.today()
    people_errors, people_warnings = validate_people(
        files["002"], memory / HISTORY_DIR / f"{HISTORY_CARDS}.md", reference, memory_dir
    )
    errors.extend(people_errors)
    for warning in people_warnings:
        print(f"WARNING {warning}")
    dictionary_entries = len(re.findall(r"(?m)^### ", files["003"].read_text(encoding="utf-8")))
    if dictionary_entries > DICTIONARY_WARN_ENTRIES:
        print(
            f"WARNING {files['003'].name}: {dictionary_entries} entries exceeds "
            f"{DICTIONARY_WARN_ENTRIES}; move entries unused for two months to the low-frequency index"
        )
    closed_months = sorted({day[:7] for day in days_001 if day[:7] < reference.strftime("%Y-%m")})
    if closed_months:
        print(f"WARNING {files['001'].name}: closed months ready to archive {closed_months}")

    current_004_sha = sha256(files["004"])
    if args.expected_004_sha and current_004_sha != args.expected_004_sha:
        errors.append(
            f"{files['004'].name}: SHA-256 changed without matching the supplied pre-edit hash"
        )

    if errors:
        print("VALIDATION FAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "VALIDATION PASSED "
        f"mode={args.mode} 001_closed_days={len(days_001)} "
        f"005_staged_days={len(days_005)} "
        f"004_sha256={current_004_sha}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
