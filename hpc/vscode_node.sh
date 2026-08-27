#!/usr/bin/env bash
# hpc/vscode_node.sh — grab a main-redhat compute node and HOLD it (tmux + salloc)
# so you can attach desktop VSCode (Remote-SSH) to it and run the notebook + Claude
# Code on the node — never on the login node.
#
# After the node is ready, the sfincs env tarball (sfincs-env.tar.gz) is unpacked
# to /tmp/$USER/sfincs on the compute node so Python imports hit local disk instead
# of GPFS — pandas goes from ~16s → ~1s. A "Python (sfincs-local)" Jupyter kernel
# is registered pointing at that local env.
#
# ONE-TIME SETUP before first use:
#   ./hpc/pack-env.sh          # ~3 min; redo after any micromamba install into sfincs
#
# USAGE (run on an Amarel login node, from the repo root or anywhere):
#   ./hpc/vscode_node.sh                       # allocate w/ defaults, print connect info
#   ./hpc/vscode_node.sh -m 250G -t 12:00:00   # override memory / walltime
#   ./hpc/vscode_node.sh --status              # show the node you're holding (if any)
#   ./hpc/vscode_node.sh --stop                # release the allocation
#
# Defaults: -p main-redhat -c 32 --mem 128G -t 08:00:00
#   main-redhat node tiers: 192 GB / 256 GB / 512 GB (max single-node ~500G).
#
# ─────────────────────────────────────────────────────────────────────────────
# ONE-TIME laptop setup — put this in your laptop's ~/.ssh/config (replace <netid>):
#
#   Host amarel
#     HostName amarel-new.hpc.rutgers.edu
#     User tpj8
#
#   # Option A (simple): paste the node this script prints into HostName each session
#   Host amarel-job
#     HostName halXXXX
#     User <netid>
#     ProxyJump amarel
#
#   # Option B (zero edits ever): auto-resolve to whatever node your job is on.
#   # NOTE: -n vscode is required — without it, head -1 grabs whatever job SLURM
#   # lists first, so an unrelated running sbatch (e.g. sfincs_run) will hijack
#   # the ProxyCommand and point VSCode at the wrong node.
#   # NOTE: in the real config the %N must be written %%N (ssh percent-expands
#   # the whole ProxyCommand first; a lone %N dies with "unknown key %N").
#   Host amarel-job
#     User <netid>
#     ProxyCommand ssh amarel "nc \$(squeue -u <netid> -h -t R -n vscode -o %N | head -1) 22"
#
# Then in VSCode:  Remote-SSH → Connect to Host → amarel-job
# ─────────────────────────────────────────────────────────────────────────────
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PART="${VSCODE_PART:-main-redhat}"
CORES="${VSCODE_CORES:-32}"
MEM="${VSCODE_MEM:-128G}"
TIME="${VSCODE_TIME:-08:00:00}"
JOB="vscode"
SESS="vscode"
ACTION="start"

usage(){ sed -n '2,18p' "${BASH_SOURCE[0]}"; exit 0; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p)            PART="$2";  shift 2;;
    -c)            CORES="$2"; shift 2;;
    -m|--mem)      MEM="$2";   shift 2;;
    -t)            TIME="$2";  shift 2;;
    --status)      ACTION="status"; shift;;
    --stop)        ACTION="stop";   shift;;
    -h|--help)     usage;;
    *) echo "unknown arg: $1"; usage;;
  esac
done

current_node(){
  local nl
  nl=$(squeue -u "$USER" -n "$JOB" -h -t R -o "%N" 2>/dev/null | head -1)
  [[ -n "$nl" ]] && scontrol show hostnames "$nl" 2>/dev/null | head -1
}

if [[ "$ACTION" == "stop" ]]; then
  scancel -u "$USER" -n "$JOB" 2>/dev/null
  tmux kill-session -t "$SESS" 2>/dev/null
  echo "released the '$JOB' allocation."
  exit 0
fi

node="$(current_node)"

if [[ "$ACTION" == "status" ]]; then
  [[ -n "$node" ]] && echo "holding compute node: $node" || echo "no '$JOB' allocation running."
  exit 0
fi

if [[ -z "$node" ]]; then
  command -v tmux >/dev/null || { echo "ERROR: tmux not found on this login node — install it or use 'screen'."; exit 1; }
  tmux has-session -t "$SESS" 2>/dev/null && tmux kill-session -t "$SESS"
  echo "Allocating: -p $PART -c $CORES --mem $MEM -t $TIME  (held in tmux session '$SESS')..."
  tmux new-session -d -s "$SESS" \
    "salloc -p '$PART' -J '$JOB' -c '$CORES' --mem='$MEM' -t '$TIME' sleep infinity"
  for _ in $(seq 1 90); do
    node="$(current_node)"; [[ -n "$node" ]] && break; sleep 2
  done
fi

if [[ -z "$node" ]]; then
  echo "Still pending in the queue. Check again with:  $0 --status   (or: squeue -u $USER -n $JOB)"
  exit 0
fi

# ── Deploy sfincs env to compute node local /tmp ──────────────────────────────
TARBALL="$REPO/sfincs-env.tar.gz"
LOCAL_ENV="/tmp/$USER/sfincs"

if [[ ! -f "$TARBALL" ]]; then
  echo "WARNING: $TARBALL not found — skipping local env deploy."
  echo "         Run ./hpc/pack-env.sh once to enable fast imports."
else
  echo "Deploying sfincs env to $node:$LOCAL_ENV ..."
  ssh -o StrictHostKeyChecking=no "$node" bash <<ENDSSH
    set -euo pipefail
    if [[ -d "$LOCAL_ENV" ]]; then
      echo "  local env already present, skipping unpack."
    else
      mkdir -p "$LOCAL_ENV"
      echo "  unpacking $(du -sh "$TARBALL" | cut -f1) tarball..."
      tar -xzf "$TARBALL" -C "$LOCAL_ENV"
      # Fix hardcoded paths left by conda-pack
      "$LOCAL_ENV/bin/conda-unpack"
      # Wire in the editable hydromt_sfincs (skipped by conda-pack) via a .pth file
      SITELIB=\$("$LOCAL_ENV/bin/python" -c "import sysconfig; print(sysconfig.get_path('purelib'))")
      echo "$REPO/hydromt_sfincs" > "\$SITELIB/hydromt_sfincs_editable.pth"
      echo "  registering Jupyter kernel..."
      "$LOCAL_ENV/bin/python" -m ipykernel install --user \
        --name sfincs-local --display-name "Python (sfincs-local)"
      echo "  done."
    fi
ENDSSH
  echo "Env ready on $node."
fi
# ─────────────────────────────────────────────────────────────────────────────

# ── Persist extensions + machine settings across allocations ─────────────────
# The laptop-side `remote.SSH.serverInstallPath: {"amarel-job": "/mnt/scratch/$USER"}`
# is what keeps the agent-host unpack under its hard 300 s timeout — but it relocates
# the ENTIRE .vscode-server tree to node-local disk, not just the server binaries.
# So every fresh allocation starts with `extensions.json == []` (all 15 extensions
# re-download from the marketplace, ~880 MB) and an empty data/Machine (git.path
# disappears, so the git integration dies). Symlink exactly those two back to the
# GPFS home copy — every node mounts it, so they now survive a new node for free.
# Server binaries and logs stay node-local, which is the part that has to be fast.
#
# NOTE: this makes $HOME/.vscode-server/extensions load-bearing. Do not delete it
# when pruning the old GPFS server tree — extensions/ and data/Machine/ are now the
# masters; cli/ and data/logs/ there are the disposable leftovers.
echo "Linking persistent VSCode dirs on $node ..."
ssh -o StrictHostKeyChecking=no "$node" bash -s "$HOME/.vscode-server" "/mnt/scratch/$USER/.vscode-server" <<'ENDSSH'
  set -uo pipefail
  HOME_VSC="$1"; LOCAL_VSC="$2"

  link_one(){  # $1 = path relative to .vscode-server
    local rel="$1" src="$HOME_VSC/$1" dst="$LOCAL_VSC/$1"
    mkdir -p "$src" "$(dirname "$dst")" || return 1
    if [[ -L "$dst" ]]; then
      [[ "$(readlink -f "$dst")" == "$(readlink -f "$src")" ]] && { echo "  = $rel"; return 0; }
      rm -f "$dst"
    elif [[ -d "$dst" ]]; then
      # Re-running after a connect: fold anything the node installed back into the
      # GPFS master before replacing the dir, so a mid-session run can't lose an
      # extension. cp -n, so a half-written node copy never clobbers a good one.
      cp -an "$dst"/. "$src"/ 2>/dev/null
      rm -rf "$dst"
    fi
    ln -s "$src" "$dst" && echo "  → $rel"
  }

  link_one extensions      || echo "  ! could not link extensions — they will re-download"
  link_one data/Machine    || echo "  ! could not link data/Machine — git.path may be missing"
ENDSSH
# ─────────────────────────────────────────────────────────────────────────────

# ── Validate the VSCode remote server install ────────────────────────────────
# An extraction interrupted by a job ending (download finishes, tar never
# completes) leaves a truncated non-executable `node` and no bin/ under
# ~/.vscode-server/cli/servers/Stable-<commit>/. After that, every Remote-SSH
# connect hangs on "Waiting for server log...", then reports a connection that
# has no remote filesystem — the window says "SSH: amarel-job" but shows your
# LOCAL directory. Validate and repair here, on the login node, which has no
# walltime and so cannot be killed halfway through a re-download.
VSC="$HOME/.vscode-server"

vsc_install_ok(){  # $1 = .../Stable-<commit>
  local s="$1/server"
  [[ -x "$s/node" && -d "$s/bin" && -f "$s/out/server-main.js" ]] || return 1
  (( $(stat -c %s "$s/node" 2>/dev/null || echo 0) > 50000000 )) || return 1
}

if [[ -d "$VSC/cli/servers" ]]; then
  # *.staging dirs are the fingerprint of an interrupted extraction — always junk
  find "$VSC/cli/servers" -maxdepth 1 -name '*.staging' -mmin +5 -exec rm -rf {} + 2>/dev/null

  bad=()
  for d in "$VSC/cli/servers"/Stable-*; do
    [[ -d "$d" ]] || continue
    vsc_install_ok "$d" || bad+=("$d")
  done

  # Nothing runs on the healthy path — just a few stat calls, no processes started.
  if (( ${#bad[@]} )); then
    echo "Repairing ${#bad[@]} corrupt VSCode server install(s):"
    for d in "${bad[@]}"; do echo "  ✗ removing $(basename "$d")"; rm -rf "$d"; done

    cli="$(ls -t "$VSC"/code-* 2>/dev/null | head -1)"   # commit your desktop last used
    if [[ -n "$cli" ]]; then
      commit="${cli##*/code-}"
      echo "  ↓ pre-warming $commit ..."
      "$cli" command-shell --cli-data-dir "$VSC/cli" --on-host=127.0.0.1 --on-port >/dev/null 2>&1 &
      for _ in $(seq 1 60); do
        vsc_install_ok "$VSC/cli/servers/Stable-$commit" && break
        sleep 2
      done
      pkill -u "$USER" -f "code-$commit" 2>/dev/null
      if vsc_install_ok "$VSC/cli/servers/Stable-$commit"; then
        echo "  ✔ server reinstalled and verified."
      else
        echo "  ! pre-warm did not finish — VSCode will retry on connect."
      fi
    fi
  fi
fi
# ─────────────────────────────────────────────────────────────────────────────

cat <<EOF

  ✔ compute node ready:  $node
    ($CORES cores · $MEM · walltime $TIME · partition $PART)

  → Desktop VSCode:  Remote-SSH: Connect to Host…  →  amarel-job
    (Option-A ssh config: set  HostName $node  first; Option-B resolves it automatically.)

  In VSCode, select the "Python (sfincs-local)" kernel — it runs from local /tmp
  on the compute node so imports are fast (no GPFS metadata overhead).

  The GPFS-backed "Python (sfincs)" kernel still works if you need it, but will
  be slow. Re-run this script if you switch to a new compute node mid-session.

  Heavy SFINCS solves still go to a batch job:  sbatch hpc/sfincs_run.slurm <model_dir>
  When finished, free the node:  $0 --stop
EOF
