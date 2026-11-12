---
name: wrapup
description: End-of-day wrap-up for this repo. Stages the day's work (git add, and git rm for tracked files deleted or retired), rewrites docs/STATUS.md for the next session, tidies strays and the scripts index, checks running jobs and their md5 guards, hands the user scancel lines for idle allocations, updates the to-do panel and memory, and ends with a ready-to-paste commit command. Use when the user types /wrapup, says "wrap up", "let's wrap up", "closing housekeeping", or is stepping away for the day.
allowed-tools: Bash(/cache/home/tpj8/nj_bight_sfincs/.claude/skills/wrapup/gather.py *), Read
---

# Wrap-up

Facts collected when the command ran (git, strays, scripts index, today's campaign dirs,
STATUS, ruff, jobs, `scripts/campaign_check.py`):

!`/cache/home/tpj8/nj_bight_sfincs/.claude/skills/wrapup/gather.py`

If the block above is empty or shows the command instead of its output, run
`.claude/skills/wrapup/gather.py` yourself.

The user asked for this housekeeping, so do it — don't stop to ask about routine steps.
Ask (AskUserQuestion, a "(Recommended)" default) only for a real decision: deleting
something you did not create this session, retiring a run or arm, or a STATUS / FINDINGS
claim you're unsure of.

## 0. Before touching anything
- **Background agents still running?** Don't stage or tidy their files mid-edit. Wait for
  their reports, or leave their files out and say so.
- **md5-guarded files** (campaign_check's EXPECT_MD5 lists, pending AND running jobs): no edits
  there. The guard hook asks; the answer at wrap-up is no. Docs are rarely guarded, but check.

## 1. Git: stage, never commit (CLAUDE.md §6)
- `git add` each modified or new file that belongs in version control: code, tests, docs, skills,
  hooks, and small design-source data that `.gitignore` un-ignores. Name the files. Never use
  `git add -A` or `git add .`.
- `git rm` each tracked file deleted from disk ("deleted, still tracked"). For a file retired on
  purpose this session, use `git rm` (or `git rm --cached` to keep the disk copy) and say why.
- Untracked, not ignored: decide for each one. Add it (source), move it (a stray belongs in its
  `logs/<campaign>/`, which is gitignored), or list it for the user. Never stage a file ≥ 5 MB,
  a run output or a raster.
- Show `git diff --cached --stat` in the reply.

## 2. docs/STATUS.md: edit in place (CLAUDE.md §6; keep it ≤ ~300 lines)
- Rewrite the **▶ PICK UP** line for the next session, with today's date. Say what's done today
  (✅), what's running (job ids, what each one is for, its md5 guard: "no edits to X until it
  starts"), the decisions the user took today (attributed "user MM-DD"), and the next steps in order.
- **Running:** make it match the queue. Collapse finished items into one line each, with a pointer
  to their `logs/<dir>/README.md`. Delete superseded text: git has the history. Clean as you go.
- Fold any older PICK UP the new one supersedes. If the file is over ~300 lines, compress the
  oldest sections into pointers.
- **docs/FINDINGS.md** only for things now believed true, each with the conditions that make it
  true (estimator + radius on every HWM number). **CHANGELOG.md / docs/MODEL.md** only if a model
  version changed.
- Fix any line in CLAUDE.md or ARCHIVE.md that today's work made false.

## 3. Tidy
- Repo-root strays: move each into its campaign dir. A file you created this session and that is
  now pointless may be deleted. Ask about anything else.
- Every `logs/` dir touched today has a README.md that says what it is, what ran, and the result.
  Write the missing ones (short).
- `scripts/`: a new script there gets a line in `scripts/README.md` (the hygiene test enforces it).
  A one-off belongs in its `logs/<campaign>/`, not `scripts/`. Index entries with no file: fix them.
- `ruff check` and `ruff format` the changed .py files only (not the tree).
- Run `tests/test_repo_hygiene.py` (light), plus the full suite if code changed today. Run it
  through `srun --jobid=<holder> --overlap -n 1 …` if a holder is alive, else on the node if light.
  🔴 Always `-n 1` on Slurm 25.11.
- Scratchpad and temp files: leave them (session-scoped). Do NOT delete run dirs, data,
  floodmaps or metrics rows: flag them, never delete a computed number.

## 4. Jobs
- Idle holders or allocations (e.g. a `sleep` holder for agents): give the exact
  `scancel <id>` line. Claude can't scancel in auto mode.
- Jobs running or pending overnight: one line each in STATUS + the reply (what it's for, ETA, its
  guard). Is there a watcher? Only claim one that a tool result confirmed.
- A job that will start after the session ends and reads files edited today: its md5 must be
  current (re-write it deliberately, or say it will refuse).

## 5. To-do panel + memory
- `todo_set` with the FULL list. Mark today's items done, waiting with a note (job id), or pending.
  Put tomorrow's first item at the top.
- Memory: save only new user preferences / feedback / where-things-are learned today (no
  measurements; the repo owns those). Update an existing file, don't duplicate it.

## 6. Other sessions
- If today changed something the **sfincs-nj-agri** session reads (`~/nj_bight_sfincs/data`,
  shared conventions, cluster facts such as Slurm changes), send it a short note
  (`ListAgents`, then `SendMessage`). Skip it otherwise.

## Reply (plain language, short)
- **Staged**: `git diff --cached --stat` and one line per group of files.
- **Cleaned**: what moved or was deleted.
- **STATUS**: the new PICK UP in two or three lines.
- **Overnight**: running jobs + their guards. `scancel` lines for holders.
- **Needs you**: decisions, files you left alone, anything that refused.
- A fish-safe commit command for the user to paste (a message summarizing the day, ending with
  the attribution line from the system reminder if one is given), e.g.
  `git commit -m "…"`, then `git push`.
