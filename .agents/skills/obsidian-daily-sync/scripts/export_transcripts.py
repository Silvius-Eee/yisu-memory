#!/usr/bin/env python3
"""Export the raw text of vault-root conversations into the vault's source ledger.

Reads local Claude Code and Codex session logs, keeps only user and assistant text,
and writes one Markdown file per session. Nothing leaves the machine.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import vault_config

SYSTEM_BLOCK = re.compile(
    r"<(system-reminder|recommended_plugins|external_codex_apps_open_page)>.*?</\1>", re.DOTALL
)
INJECTED_PREFIXES = (
    "<environment_context",
    "<user_instructions",
    "<permissions",
    "<local-command",
    "<command-",
    "<task-notification",
    "<side-sessions-event",
    "<ci-monitor-event",
    "# AGENTS.md instructions",
)


def clean(text: str) -> str:
    text = SYSTEM_BLOCK.sub("", text).strip()
    return "" if text.startswith(INJECTED_PREFIXES) else text


def local_time(stamp: str, zone: timezone) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(zone)


def read_lines(path: Path) -> list[str]:
    if path.suffix != ".zst":
        return path.read_text(encoding="utf-8").splitlines()
    zstd = shutil.which("zstd")
    if not zstd:
        raise RuntimeError("zstd is required for archived Codex sessions")
    result = subprocess.run([zstd, "-dc", str(path)], capture_output=True, check=True)
    return result.stdout.decode("utf-8").splitlines()


def parse_codex(path: Path, vault: Path) -> tuple[str, str, list[tuple[str, str, str]]] | None:
    session_id = ""
    started = ""
    turns: list[tuple[str, str, str]] = []
    for line in read_lines(path):
        record = json.loads(line)
        payload = record.get("payload") or {}
        if record.get("type") == "session_meta":
            if payload.get("cwd") != str(vault) or payload.get("parent_thread_id"):
                return None
            session_id = payload.get("id") or payload.get("session_id") or path.stem
            started = payload.get("timestamp") or record.get("timestamp") or ""
        elif record.get("type") == "response_item" and payload.get("type") == "message":
            role = payload.get("role")
            if role not in ("user", "assistant"):
                continue
            text = "\n".join(
                part.get("text", "")
                for part in payload.get("content") or []
                if part.get("type") in ("input_text", "output_text", "text")
            )
            text = clean(text)
            if text:
                turns.append((role, record.get("timestamp") or started, text))
    if not session_id or not turns:
        return None
    return session_id, started, turns


def parse_claude(path: Path) -> tuple[str, str, list[tuple[str, str, str]]] | None:
    turns: list[tuple[str, str, str]] = []
    for line in read_lines(path):
        record = json.loads(line)
        if record.get("type") not in ("user", "assistant"):
            continue
        if record.get("isSidechain") or record.get("isMeta"):
            continue
        content = (record.get("message") or {}).get("content")
        if isinstance(content, str):
            text = content
        else:
            text = "\n".join(
                part.get("text", "")
                for part in content or []
                if isinstance(part, dict) and part.get("type") == "text"
            )
        text = clean(text)
        if text and record.get("timestamp"):
            turns.append((record["type"], record["timestamp"], text))
    if not turns:
        return None
    return path.stem, turns[0][1], turns


def render(
    source: str,
    session_id: str,
    started: str,
    turns: list[tuple[str, str, str]],
    user_label: str,
    zone: timezone,
) -> str:
    lines = [
        "---",
        f"source: {source}",
        f"session_id: {session_id}",
        f"started: {local_time(started, zone).isoformat(timespec='minutes')}",
        "---",
        "",
    ]
    for role, stamp, text in turns:
        speaker = user_label if role == "user" else "助手"
        lines += [f"## {speaker} · {local_time(stamp, zone).strftime('%m-%d %H:%M')}", "", text, ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, help="Vault root; defaults to this skill's repo")
    parser.add_argument("--dry-run", action="store_true", help="Report without writing")
    parser.add_argument(
        "--rebuild", action="store_true", help="Replace exports even when the new text is shorter"
    )
    parser.add_argument("--config", type=Path, help="Settings file; defaults to the skill's vault.json")
    parser.add_argument("--memory-dir", help="Memory folder inside the vault")
    parser.add_argument("--user-label", help="Heading label for user turns")
    args = parser.parse_args()

    try:
        settings = vault_config.load(args.config)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    memory_dir = str(args.memory_dir or settings["memory_dir"])
    user_label = str(args.user_label or settings["user_label"])
    zone = timezone(timedelta(hours=float(settings["utc_offset_hours"])))

    vault = (args.vault or vault_config.default_vault()).resolve()
    output = vault / memory_dir / "原始对话"
    home = Path.home()
    claude_dir = home / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(vault))

    sources: list[tuple[str, Path]] = []
    sources += [("codex", p) for p in sorted((home / ".codex" / "sessions").rglob("*.jsonl"))]
    sources += [
        ("codex", p)
        for p in sorted((home / ".codex" / "archived_sessions").glob("*.jsonl*"))
    ]
    sources += [("claude", p) for p in sorted(claude_dir.glob("*.jsonl"))]

    excluded_list = output / "排除清单.txt"
    excluded = (
        {line.split()[0] for line in excluded_list.read_text(encoding="utf-8").splitlines() if line.strip()}
        if excluded_list.is_file()
        else set()
    )

    stats: Counter[str] = Counter()
    months: Counter[str] = Counter()
    for source, path in sources:
        try:
            parsed = parse_codex(path, vault) if source == "codex" else parse_claude(path)
        except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as error:
            print(f"SKIPPED {path.name}: {error}", file=sys.stderr)
            stats["failed"] += 1
            continue
        if parsed is None:
            stats["not_this_vault_or_empty"] += 1
            continue

        session_id, started, turns = parsed
        if session_id[:8] in excluded:
            stats["excluded"] += 1
            continue
        day = local_time(started, zone).date().isoformat()
        target = output / day[:7] / f"{day}_{source}_{session_id[:8]}.md"
        body = render(source, session_id, started, turns, user_label, zone)
        existing = target.read_text(encoding="utf-8") if target.is_file() else ""
        if body == existing:
            stats["unchanged"] += 1
        elif len(body) < len(existing) and not args.rebuild:
            stats["kept_longer_export"] += 1
        else:
            stats["written"] += 1
            months[day[:7]] += 1
            if not args.dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(body, encoding="utf-8")

    print(f"EXPORT {'DRY RUN ' if args.dry_run else ''}{dict(stats)} months={dict(sorted(months.items()))}")
    return 1 if stats["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
