#!/usr/bin/env bash
# Thin wrapper — the real script is shared by all nj_*_sfincs repos so they cannot drift
# apart again. Edit ~/.local/bin/vscode_node.sh, not this. Run with -h for usage.
exec "$HOME/.local/bin/vscode_node.sh" "$@"
