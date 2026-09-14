#!/bin/bash
# Commit and push ONE rendered notebook (and its dated GIFs) so it can be read on GitHub
# while Amarel is down. Written 2026-09-14 for the maintenance window; run as a SLURM job
# chained `afterok` the nbconvert job. Pushes over SSH (the user's key; HTTPS has no
# credential helper on this account), by explicit URL so the repo's remote config is not
# changed. Commits only the notebook paths given, never the working tree at large.
#
#   sbatch -t 0:10:00 --dependency=afterok:<render job> hpc/push_rendered_notebook.sh <notebook.ipynb> [gif glob]
#
# This is an AUTOMATED commit on the user's behalf, made at their request (STATUS 09-14).
set -euo pipefail
REPO=/cache/home/tpj8/nj_bight_sfincs
export PATH="$HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin:$PATH"
cd "$REPO"
NB="${1:?usage: push_rendered_notebook.sh <notebook> [gif-glob]}"
GIFS="${2:-}"
URL=git@github.com:tyfolino/nj_bight_sfincs.git

echo "host=$(hostname) job=${SLURM_JOB_ID:-none} $(date)"
git add -- "$NB"
if [ -n "$GIFS" ]; then
    # shellcheck disable=SC2086
    git add --ignore-errors -- $GIFS 2>/dev/null || true
fi
if git diff --cached --quiet; then
    echo "nothing to commit ($NB unchanged)"; exit 0
fi
git -c user.name="$(git config user.name)" -c user.email="$(git config user.email)" commit -q -m "Render $(basename "$NB") (automated push after SLURM job ${SLURM_JOB_ID:-?})

Executed by nbconvert on Amarel; committed and pushed by hpc/push_rendered_notebook.sh so
the rendered notebook is readable on GitHub during the 2026-09-15/16 maintenance window.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
echo "committed $(git rev-parse --short HEAD)"
if ! git push "$URL" HEAD:master; then
    echo "push rejected — rebasing onto the remote and retrying"
    git pull --rebase --autostash "$URL" master
    git push "$URL" HEAD:master
fi
echo "pushed $(git rev-parse --short HEAD) to $URL master"
