"""Shared settings for the sync scripts.

Each value comes from, in order: a command-line flag, `vault.json` next to the
skill's SKILL.md, then the defaults below. The scripts themselves stay identical
in every vault; anything vault-specific belongs in `vault.json`.
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULTS: dict[str, object] = {
    "memory_dir": "记忆",
    "checkpoint_dir": ".codex/daily",
    "user_label": "用户",
    "utc_offset_hours": 8,
}

SKILL_DIR = Path(__file__).resolve().parents[1]
CONFIG_NAME = "vault.json"


def default_vault() -> Path:
    """The vault root: four levels above this file (.agents/skills/<skill>/scripts)."""
    return Path(__file__).resolve().parents[4]


def load(path: Path | None = None) -> dict[str, object]:
    path = path or SKILL_DIR / CONFIG_NAME
    settings = dict(DEFAULTS)
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path.name}: expected a JSON object")
        if unknown := sorted(set(data) - set(DEFAULTS)):
            raise ValueError(f"{path.name}: unknown keys {unknown}")
        settings.update(data)
    return settings
