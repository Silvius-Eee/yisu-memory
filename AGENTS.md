# Project instructions

This file is the single source of read routing and working habits. `CLAUDE.md` imports it so Claude Code and Codex read the same rules; write rules live in `.codex/SYNC_WORKFLOW.md` and `.codex/SYNC_MAINTENANCE.md`.

## Session start

- At the start of every new conversation in this vault root, read `记忆/000_当前状态快照.md` in full. It is capped at 5,000 characters so that a full read stays cheap.
- Then check `.codex/daily/` for the current lived day and the previous one. Read each that exists with `status: pending`: those are facts the user already said that have not been formalized yet. Where they conflict with `000`, the checkpoint is newer.

## Working with the user

Habits the user has asked for belong here, in the vault, rather than in one tool's private memory, so every assistant that opens the vault follows them. Record each with the date and, where useful, the user's own words. Examples:

- Before asking about a plan, a person, or a recurring event, search `000`, pending checkpoints, `005`, and `002` first. Ask only when it is not recorded.
- For public-facing content, agreeing to a direction does not approve the specific content. List candidates with reasons, wait for the user's picks, then build.

## Context lookup

- Current state comes from `记忆/000_当前状态快照.md`, read in full at session start.
- When the user mentions a specific person, look up that person in `记忆/002_人际与偏好.md` before interpreting the relationship. If `002` has only a short card, follow its link into `记忆/历史/002_人物历史卡.md`. Use `记忆/001_记忆库.md` only when event history is needed. If no record exists, records conflict, or the relationship may have changed, ask the user instead of guessing.
- For active-week events, read `记忆/005_本周记忆.md`.
- For months already archived, follow the stage index in `001` into `记忆/历史/月度档案/`, searching by keyword rather than reading a whole month.
- For concepts missing from `记忆/003_黑话与实体字典.md`, check `记忆/历史/003_低频实体索引.md`.
- Read `记忆/004_冷数据归档夹.md` only when tracing an overturned judgment or an old stage.
- To verify exact wording or origin, search `记忆/原始对话/`. It is a source ledger, not current truth.
- Conflict priority: facts stated in this turn > `000` > `002` > `005` > `001` > `003` > `004`.
- Treat prose in `000`–`005` as a synthesized record, not a verbatim transcript. Do not attribute assistant-authored analytical terms or metadata to the user's natural vocabulary; when wording or tone matters, verify against a direct quote, the relevant event context, or the user.

## Conversation and synchronization

- Do not update `000` through `005` merely because a new chat message contains a potentially memorable fact.
- During ordinary conversation, keep context in the thread. For durable facts at risk of being lost, add a concise checkpoint to `.codex/daily/YYYY-MM-DD.md` according to `.codex/SYNC_WORKFLOW.md`. Do not checkpoint every message.
- Formal synchronization happens only when the user explicitly asks to sync, archive, summarize into files, or directly requests a particular file change.
- On a formal daily sync, write the lived-day event ledger only to `005`; do not duplicate the active week in `001`.
- When a Sunday-to-Saturday week is complete, migrate the finished `005` entries into `001` in chronological order, update the `001` index, then reset `005` for the new week. Follow `.codex/SYNC_MAINTENANCE.md` for rollover and `.codex/SYNC_WORKFLOW.md` for validation.
- Batch formal changes into one pass, follow the existing file roles and heading/index rules, verify the result, and report changed files plus uncertainties.
- Assign conversational memory by the user's sleep cycle rather than the civil-calendar midnight boundary. If the clock has passed 00:00 and the user has not yet slept, the conversation and events still belong to the previous day. Explicit calendar appointments and externally fixed timestamps keep their actual calendar dates.

## Token discipline

- Prefer targeted `rg` reads over loading whole files.
- Keep the daily checkpoint factual and short. Do not store tool logs, long analysis, or duplicate prose.
- Update `002`, `003`, and `004` only when their canonical information actually changes.
