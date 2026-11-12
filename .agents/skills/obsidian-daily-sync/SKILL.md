---
name: obsidian-daily-sync
description: Reliably synchronize a lived day's conversation into the 000–005 layered-memory vault. Use only when the user explicitly asks to archive, write into Obsidian, sync to files, or change a canonical vault file. Do not trigger for ordinary conversation, “同步一下今天”, chat-only summaries, or monthly archive restructuring.
---

# Obsidian daily sync

Treat `.codex/SYNC_WORKFLOW.md` as the detailed source of truth for every sync, and `.codex/SYNC_MAINTENANCE.md` for low-frequency jobs. Keep this skill as the execution router; do not duplicate the workflow in the skill.

1. Confirm explicit file-write authorization and the vault root. Stop before any write when the request is chat-only or ambiguous.
2. Read `AGENTS.md`, `CLAUDE.md`, `.codex/SYNC_WORKFLOW.md`, the relevant current-state sections, the current-week file, person cards named in the conversation, and the lived-day checkpoint when present. Read `001` history only when chronology is needed. Read `.codex/SYNC_MAINTENANCE.md` only when a weekly rollover is due or the user confirms a person card move, monthly archive, or checkpoint rotation.
3. Determine the lived day from the user's sleep boundary. Preserve civil dates for fixed appointments, deadlines, schedules, and external timestamps.
4. Before editing, run `git status` and commit any leftover changes first; then record the SHA-256 of the `004` file. Route facts once: `000` current state, `005` active-week chronology, `001` closed-week chronology, `002` canonical people/preferences, `003` reusable entities, and `004` confirmed stale judgments only.
5. For a daily sync, write the full day block and index only to `005`; do not duplicate it in `001`. If the lived day has entered a new Sunday and `005` still holds the completed prior week, close that week first by migrating its blocks verbatim into `001`, updating the `001` index, and resetting `005`.
6. Ask only about genuine factual ambiguity. Batch targeted edits, preserve fact versus inference, and update the owning file's body/index pair together. Anchor weekly migration in `001` on the exact preceding date heading.
7. Finalize the relevant `.codex/daily/YYYY-MM-DD.md` checkpoint as required by the local workflow.
8. For a daily sync, run `python3 .agents/skills/obsidian-daily-sync/scripts/validate_sync.py --mode daily --date YYYY-MM-DD --expected-004-sha SHA256`. For a weekly close, use `--mode weekly-close --date YYYY-MM-DD`, where the date is one migrated day. If confirmed stale information explicitly requires a 004 update, omit the expected hash, inspect that change directly, and report it. Fix every reported error before finishing.
9. Run `python3 .agents/skills/obsidian-daily-sync/scripts/export_transcripts.py` to refresh the source ledger, then commit the sync as `同步 YYYY-MM-DD：<topics>`. Never push; the repository is local only.
10. Re-read the user's original sync instruction and confirm every requested item landed. Report the commit hash, changed files, material contents, unresolved uncertainty, every validator warning, and that the changes are available in Obsidian.

Do not treat plans as completed facts, partial handoff as acceptance, tool output as business correctness, or uncertain social observations as established relationship facts.
