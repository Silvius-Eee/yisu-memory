# Lightweight synchronization workflow

## Purpose

Separate temporary conversational memory from canonical Obsidian records. The active Sunday-to-Saturday week lives only in `005`; completed weeks migrate into `001` once, avoiding duplicate daily ledgers.

Write rules for the vault live in two files. This one covers every sync. `.codex/SYNC_MAINTENANCE.md` covers jobs that come up weekly or less: weekly rollover, person card moves, monthly archive, checkpoint rotation, the source ledger, and version history; read it only when one of those is due. `AGENTS.md` owns read routing. File headers in `001`–`004` state only the file's role and point here.

## Memory architecture

| Layer | Holds | Files |
| --- | --- | --- |
| Rules | How to read and write | `CLAUDE.md`, `AGENTS.md`, this file, `SYNC_MAINTENANCE.md`, sync scripts |
| Current | Read in normal use | `000`, `002`, `003`, `005` |
| History | Read only when tracing back | `001`, `记忆/历史/月度档案/`, `记忆/历史/002_人物历史卡.md`, `记忆/历史/003_低频实体索引.md`, `004` |
| Source ledger | Verifying wording and origin | `记忆/原始对话/`, `.codex/daily/` |
| History | Recovery only | Local git in the vault root, one commit per sync; never pushed |

`000`–`005` and the memory history live under `记忆/`; `归档/` keeps system history; recovery points are git commits, not folders. Project outputs belong in `项目/`, including assets and version history.

New facts enter the current layer, inactive content moves down to history, and content that becomes active again moves back up. The source ledger is never treated as current truth. Do not add a new top-level memory file without the user's approval.

## Layer 1: thread context

Ordinary conversation remains in the current task context. Routine meals, temporary moods, jokes, and tentative ideas do not require a file write by default.

## Layer 2: daily checkpoint

Use `.codex/daily/YYYY-MM-DD.md` only for durable, explicit information that may matter at formal sync:

- appointments, purchases, commitments, deadlines, and completed actions;
- confirmed relationship facts or corrections;
- material changes to work, job search, health, finance, or ongoing projects;
- facts the user explicitly asks the assistant to remember;
- compact checkpoints before a long context is likely to become difficult to retain.

A checkpoint with `status: pending` is read at the start of every new conversation (see `AGENTS.md`), so a fact recorded here is available to the next chat before any formal sync.

Do not update the checkpoint after every message. Batch related facts after a meaningful milestone. Each entry should be one compact bullet and distinguish fact, plan, interpretation, and formalization state.

Use consistent frontmatter:

```yaml
---
lived_day: YYYY-MM-DD
status: pending | finalized
formal_sync_completed: YYYY-MM-DD  # optional when the exact completion date is unknown
---
```

Suggested entry format:

```text
- [domain][fact|plan|interpretation][pending|already-formal] concise statement. -> 000/002/003/004/005
```

`already-formal` means the fact has entered the canonical vault, including the active-week ledger in `005`; it does not imply that the week has already migrated into `001`.

Do not include tool operations, recovery logs, long reasoning, repeated conversation, or unsupported inference.

## Language provenance and user voice

The canonical vault is a synthesized record, not a verbatim transcript. Preserve this provenance whenever writing or later interpreting it.

- **Surface voice, structured foundation:** keep the underlying fact / plan / interpretation / unknown distinctions, while making narrative prose sound as close as practical to how the user actually speaks. Prefer his concrete phrases, scenes, contrasts, and degree words over replacing them all with abstract analytical terminology.
- **Do not manufacture user vocabulary:** terms introduced by the assistant for indexing or analysis (for example status labels, relationship temperatures, weighting, bandwidth, ROI, or monitoring states) remain assistant-authored metadata unless the conversation directly shows that the user uses and accepts them. Do not later cite those archived terms as evidence of his natural language, personality, or way of seeing people.
- **Separate quote, paraphrase, and analysis:** quotation marks are only for exact or faithfully preserved user wording. A paraphrase must not be presented as the user's own phrase. New analytical concepts belong under interpretation or in compact metadata, not silently inside the user's voice.
- **Prefer situated observations over global labels:** write “在目前几次线上互动里，对方较少接梗或回推话题” rather than turning limited evidence into “对方表达能力弱”. Preserve the scene, sample limit, and possibility of change.
- **Keep original wording beside useful abstractions:** when an analytical concept materially improves retrieval, retain the user-facing phrase or concrete event that grounded it. The abstraction must not erase the lived expression it summarizes.
- **Metadata stays metadata:** compact fields such as current positioning, status, confidence, or routing may remain standardized for retrieval, but should not spread into every narrative sentence or flatten a person into a configuration sheet.
- **Read-back boundary:** when a later interpretation depends on wording or tone, return to the relevant event record or current conversation. Treat prose in `000`–`005` as a prior synthesis unless it is explicitly marked as a direct quote; do not create a self-confirming loop from assistant-authored archive language.

Operational shorthand: **表层尽量像用户会说的话；底层继续守住事实、推断、计划与未知。**

### Sleep-cycle date boundary

Daily memory follows the user's lived day rather than switching mechanically at 00:00. If a conversation continues past midnight before the user sleeps, keep those messages and events in the previous day's checkpoint. Start the new daily checkpoint only after the user has slept and woken up. This rule applies to conversation summaries, `005` staged day entries, later `001` migration, and relationship “recent changes”. Calendar appointments, deadlines, medical bookings, work schedules, and other externally fixed dates retain their actual calendar dates.

## Layer 3: formal daily synchronization

Trigger only when the user explicitly requests synchronization or directly asks for a file change.

1. Run `git status`. If the working tree is not clean, commit those changes first as `同步前：<what they are>`. The last commit is the restore point for this sync; do not create backup folders.
2. Identify the user's current sleep-cycle day, then read that day's checkpoint and the relevant conversation context.
3. Resolve corrections and remove duplicates. Ask the user about genuine ambiguity before writing.
4. If the lived day has entered a new Sunday while `005` still contains the completed prior week, perform weekly rollover before writing the new day (see `SYNC_MAINTENANCE.md`).
5. Use targeted reads for the destination sections.
6. Apply one batched patch where practical:
   - `000`: current state and next actions; replace stale current information with targeted edits, and apply the `000` size and eviction rules below on every sync.
   - `005`: the only chronological ledger for the active Sunday-to-Saturday week. Write full day entries in the same `### day` / `#### event` / fact-inference-impact format used by `001`, and update the weekly index.
   - `001`: closed-week chronological archive for the active month. Do not write the active week here during a daily sync.
   - `002`: only confirmed relationship or preference changes, updated in the correct card, following the file rules below; card moves follow the person card lifecycle in `SYNC_MAINTENANCE.md`.
   - `003`: only reusable entities, concepts, tools, and shared shorthand.
   - `004`: only information that has become stale or should no longer be called by default.
   Preserve the language-provenance rules above across every destination, especially `001`, `002`, and `005`. Person cards may use compact metadata for routing, but their descriptive prose should preserve concrete interaction evidence and the user's recognizable expression rather than replacing a person with assistant-invented labels.
7. Verify dates, index links, heading levels, duplicate entries, contradictions, and that no lived day appears in both `001` and `005`.
8. Mark checkpoint entries as `already-formal` and set the file status to `finalized`. Later same-day facts start a new pending section rather than rewriting completed history.
9. Run the validator in `daily` mode and report changed files plus unresolved uncertainty. Pass on every warning; list person demotion candidates and monthly archive reminders for the user to confirm, and do not act on them unprompted. When the user confirms one, follow `SYNC_MAINTENANCE.md`.
10. Run `export_transcripts.py` to refresh the source ledger.
11. Commit everything as `同步 YYYY-MM-DD：<topics>` and report the commit hash. The repository has no remote and a `pre-push` hook refuses pushes; never add one.

## `000` size and eviction rules

`000` is a snapshot, not a ledger. Each sync must replace or remove as well as add.

- **Size:** target at most 5,000 characters; the validator warns above 5,000 and fails above 6,000. When a sync would exceed the target, evict before adding.
- **One item, one place:** each topic appears once as current state plus next step. Do not restate it across sections.
- **Eviction:** remove an item when it is resolved, or when it has had no new progress for 14 days and no pending next step. Keep a one-line pointer only if it can still affect a current decision.
- **No day-by-day records:** chronology belongs in `005`/`001`, and person evidence, interaction samples, and relationship interpretation belong in `002`. `000` keeps only a person's current position and active next step.
- **Risk reminders:** keep a reminder only while it can still cause a misjudgment on an active item. Remove it when that item closes.
- **Recent index:** keep exactly the latest three lived days.
- **Fixed schedule:** weekly or monthly recurring arrangements (classes, work hours, rent and pay days) live once in `#### 固定日程`. They are exempt from the 14-day eviction rule because they recur without new progress; remove an item only when it stops recurring. Other sections refer to it instead of restating the time.
- **Before removing:** confirm the fact exists in its owning file. If it does not, write it there first. Evicted facts do not go to `004` unless they are genuinely stale.

## File rules

- **`001`:** event chronology only: what happened, how it was read at the time, and whether it changed anything. It holds only closed weeks of the active month. Entry format lives in the template inside `001`.
- **`002`:** facts come before interpretation, recent facts before old labels, and the user's current statement before all history. Judgments about another person's motive, liking, hostility, or closeness stay revocable and carry a confidence level. Active person cards use five fields: 当前定位、已确认事实、可撤销判断、相处边界、最近两次关键变化. “已确认事实” keeps necessary background, shared history, direct evaluation, and stable behavior, with no speculation about motives or outcomes. “最近两次关键变化” keeps only the two latest changes to position, closeness, judgment, or boundaries. Update a card only when an event changes a person's position, closeness, stable preference, or boundary. Cards never hold day-by-day logs; a card over 2,500 characters triggers a validator warning. Compression removes repetition and old logs: it must not reduce a person to a context-free label or delete boundaries that still affect current judgment.
- **`003`:** stable definitions, necessary origin, ownership, and usage boundaries only, in a short “含义 + 使用边界” form. An entry enters only if it is expected to be used independently at least twice. Dates explain how a term formed and are not current state. Project progress returns to `000` or the project's source, person detail to `002`, stale judgments to `004`, and low-frequency entries to `记忆/历史/003_低频实体索引.md`.
- **`004`:** when a judgment in `001`/`002` is overturned, downgraded, or should stop being called, move it here with the historical content, the evidence and date of invalidation, and when it may be called. Entries explain why an old judgment failed and do not maintain later conclusions. Person cards keep no tombstone for it.

## Safety rules

- Never write canonical files for ordinary conversation or a chat-only summary.
- Never maintain the same lived-day block in both `001` and `005`; `005` owns the active week and `001` owns closed weeks.
- Before a recovery, migration, or large rewrite, commit the current state first so it can be restored from git (see Version history in `SYNC_MAINTENANCE.md`).
- A formal sync must not treat plans or possibilities as completed facts.
- Current reality comes from `000`, current people/preferences from `002`, active-week events from `005`, and older chronology from `001`.
