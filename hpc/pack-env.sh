#!/usr/bin/env bash
# hpc/pack-env.sh — pack the sfincs conda env into a tarball for fast compute-node deploys.
#
# Run this once (and again after any "micromamba install" into the sfincs env):
#   ./hpc/pack-env.sh
#
# Output: $REPO/sfincs-env.tar.gz  (~900 MB)
# That tarball is unpacked to /tmp/$USER/sfincs on the compute node by vscode_node.sh.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MM="$REPO/micromamba/bin/micromamba"
OUT="$REPO/sfincs-env.tar.gz"

# conda-pack records the prefix string it is GIVEN, but the env's shebangs and embedded
# paths hold the *resolved* path. $REPO/micromamba is a symlink into ~/nj_sandy_sfincs, so
# passing the unresolved path makes conda-unpack search for a string that is not in the
# files: it exits 0 having rewritten nothing, and every console entry point (pip, jupyter,
# ipython) silently keeps pointing at the GPFS interpreter on the compute node. Resolve it
# so the recorded prefix matches what is actually inside the files.
ENV_PREFIX="$(realpath "$REPO/micromamba/envs/sfincs")"

echo "Packing sfincs env → $OUT"
echo "  prefix: $ENV_PREFIX"
echo "(this takes ~15-20 minutes; only needed again after 'micromamba install' into sfincs)"
echo ""

"$MM" run -n base conda-pack -p "$ENV_PREFIX" -o "$OUT" --force \
  --ignore-editable-packages

echo ""
echo "Done: $(du -sh "$OUT" | cut -f1)  →  $OUT"
echo "Next: run ./hpc/vscode_node.sh — it will unpack this onto the compute node automatically."
