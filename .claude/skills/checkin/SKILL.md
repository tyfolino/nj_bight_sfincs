---
name: checkin
description: Morning check-in for this repo. Covers what ran on SLURM since the last session (finished, failed, queued, EXPECT_MD5 guards, halk, maintenance, quota), where the previous session left off, uncommitted work, and today's to-do list from STATUS.md. Use when the user types /checkin, or opens with a status update / "what came in overnight" / "where did we leave off" / "today's to-do list".
allowed-tools: Bash(/cache/home/tpj8/nj_bight_sfincs/.claude/skills/checkin/gather.py *), Read
---

# Morning check-in

Facts collected when the command ran (node, scratch, `scripts/campaign_check.py`, failed-job
log tails, git, how the last session ended):

!`/cache/home/tpj8/nj_bight_sfincs/.claude/skills/checkin/gather.py ${CLAUDE_SESSION_ID}`

If the block above is empty or shows the command instead of its output, run
`.claude/skills/checkin/gather.py` yourself.

## Steps
1. Read [docs/STATUS.md](../../../docs/STATUS.md) — the PICK UP line and "Running" first.
   Open FINDINGS or a campaign `logs/<dir>/` only if a step needs detail STATUS doesn't give.
2. For each job of this repo that ended: say what it was for (match the job name or log to a
   STATUS item). Before anything reads a finished solve, the next step is the CLAUDE.md §5
   checks, not a resubmit: `sacct` NodeList (halk = late-write trap), `python -m
   nj_sfincs.premier` says `output WHOLE`, `restart_history.txt` (a resumed rain-on run says
   "soil state RESET"; a resumed waves-on run is a different run). Failed or preempted: give
   the log lines and the likely cause; read more of the log only when the tail does not say.
3. Jobs from other repos (`[sfincs-nj-agri]` etc.): one line, no digging.
4. A 🔴 from campaign_check (an EXPECT_MD5 that now fails, `DependencyNeverSatisfied`, a job
   running into maintenance) blocks work: say it first. Claude cannot `scancel` or
   `scontrol update` — give the user the exact lines.
5. Where we left off: the previous session's last user asks and Claude's last message, plus
   uncommitted changes in git. If that session stopped mid-task (a wait that never reported,
   a half-done edit), say so plainly: that comes first today.
6. Flag anything else that blocks work: login node or under ~1 h left on the vscode job,
   `experiments/` missing, quota near 100 G, STATUS older than the work in git or the jobs.

## Reply (plain language, short; the user reads it over coffee)
- **Overnight**: finished / failed / still queued, one line each, grouped when they are siblings.
- **Where we left off**: 2-3 lines.
- **Today**: a numbered to-do list of 3-6 items from STATUS PICK UP / "Next", reordered by
  what came in. Mark the one you'd start with and why.
- **Waiting on / to nudge**: only if STATUS lists something, or something has waited a while.
- Proposed STATUS edits, if any, as a short list (don't edit STATUS until the user agrees).

This is read-only: don't submit, stage, score or edit anything until the user picks a task.
