#!/usr/bin/env bash
# Thin wrapper — all nj_*_sfincs repos share ONE sfincs env and ONE packed tarball
# (~/nj_sandy_sfincs/micromamba/sfincs-env.tar.gz). Edit ~/.local/bin/pack-sfincs-env.sh.
exec "$HOME/.local/bin/pack-sfincs-env.sh" "$@"
