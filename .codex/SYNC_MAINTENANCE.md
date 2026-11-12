# Sync maintenance

Low-frequency jobs for the vault. Every sync follows `.codex/SYNC_WORKFLOW.md`; open this file only when one of the jobs below is due:

- a formal sync falls on a new Sunday while `005` still holds the completed prior week (weekly rollover);
- the user confirms a person card demotion or a returning person (person card lifecycle);
- the user asks to archive a closed month (monthly archive, then checkpoint rotation);
- the source ledger export fails or needs a rebuild (source ledger);
- an earlier version needs to be restored, or the git setup needs checking (version history).

The fact-routing, language-provenance, and safety rules in `SYNC_WORKFLOW.md` apply here as well.

## Weekly rollover: `005` to `001`

The week runs Sunday through Saturday. Perform rollover when the lived day enters a new Sunday and `005` still contains the completed prior week, or when the user explicitly requests a weekly close.

1. Start from a clean git working tree; commit any pending changes first. That commit is the restore point.
2. Confirm every `005` index link matches exactly one body heading and every day has at least one `####` event section.
3. Copy the completed `005` day blocks verbatim into `001` under the correct `## YYYY-MM` month heading, preserving chronological order and updating the `001` quick index.
4. Confirm the migrated dates appear once in `001`, no longer appear in `005`, and were not already present in `001` before migration.
5. Reset `005` to the new Sunday-to-Saturday range with an empty weekly index. The next formal daily sync writes the first new-week entry there.
6. Run the validator in `weekly-close` mode. Monthly archival happens only after any week containing that month's remaining days has been closed into `001`.

## Person card lifecycle

`记忆/历史/002_人物历史卡.md` holds the verbatim full cards of people who have left the active network.

- **Demote:** former colleagues and weak ties (`职场圈`, `弱连接`) with no new interaction for 60 days are listed by the validator during a sync. Move a card only after the user confirms. `好友圈` is exempt and never demoted by this rule.
- **How to move:** copy the card verbatim to the history file under its own `### name` heading, then replace it in `002` with a one- or two-line short card under `历史档案` that says who the person is and links to `[[记忆/历史/002_人物历史卡#name|完整卡]]`. Update the `002` table of contents and the history file's migration list.
- **Read:** not read in normal use. Follow the link only when the user mentions someone who has only a short card, or explicitly traces that person's history.
- **Promote:** when a demoted person has a new interaction, move the card back to the correct `002` section, update it, and leave only `已回迁 YYYY-MM-DD` under that heading in the history file.
- **Invariant:** one person has one full card. Every short-card link resolves, and every history heading not marked as returned has a short card. The validator checks this.

## Monthly archive

When every day of a month has been closed into `001`, the validator reminds at the next sync. Archive only when the user asks.

1. Start from a clean git working tree and record the SHA-256 of `001`.
2. Move the month's day blocks verbatim to `记忆/历史/月度档案/001_YYYY_MM_历史档案.md`, with a header and `日条目速查`, and store hash-only verification evidence in `月度档案/_验证/YYYY-MM/`, with no full file copies.
3. In `001`, replace that month with a stage-index link and remove its quick-index entries.
4. Rewrite links that point to moved headings in `000` and `002`.
5. Rotate that month's finalized checkpoints as described below.

## Finalized checkpoint rotation

After a calendar month has been completely archived from the active `001` file and every checkpoint for that month is `status: finalized` with no `[pending]` entries, move those checkpoints from `.codex/daily/` to `.codex/daily/archive/YYYY-MM/`.

- Rotation changes only the checkpoint location; it does not rewrite checkpoint content or reopen formalized facts.
- Keep the current active month at the top level so daily validation can inspect it directly.
- Before moving, record file hashes; after moving, confirm every hash is unchanged and the top-level daily validator still passes for the current lived day.
- Archived checkpoints are recovery evidence, not an additional canonical event ledger. Current chronology remains in `001/005`.

## Source ledger

`记忆/原始对话/` is the only place to verify exact wording. Formal syncs refresh it with `python3 .agents/skills/obsidian-daily-sync/scripts/export_transcripts.py`, which exports user and assistant text from sessions whose working directory is this vault root and skips tool calls, reasoning, images, and project subfolder sessions. Exports are idempotent and never replace a longer export with a shorter one unless run with `--rebuild`. `记忆/原始对话/排除清单.txt` lists session id prefixes that must not be exported again: duplicates and empty sessions. Claude Code session retention is set by `cleanupPeriodDays` in `~/.claude/settings.json`.

## Version history

The vault root is a local git repository covering the memory system: `CLAUDE.md`, `AGENTS.md`, `.codex/`, `.agents/`, `记忆/`, `归档/`, and `项目/README.md`. The rest of `项目/` is excluded in `.gitignore`, because projects keep their own media, dependencies, and repositories.

- **Local only.** The repository has no remote, and `.git/hooks/pre-push` refuses every push. Never add a remote. Hooks are not versioned; if the hook is missing, recreate it.
- **One sync, one commit.** A formal sync starts from a clean tree and ends with a commit named `同步 YYYY-MM-DD：<topics>`. Other rule or structure changes get their own commit.
- **Restore** a file with `git show <commit>:<path>` or `git checkout <commit> -- <path>`, after confirming with the user. Review what a sync changed with `git show --stat <commit>`.
- **No backup folders.** Do not create folders under `归档/数据备份/`. If the vault had backup folders before it used git, commit them once as they are, then remove them from the working tree.
- `.tmp/` holds only regenerable files and is ignored.
