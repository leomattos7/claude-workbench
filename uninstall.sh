#!/usr/bin/env bash
# Remove what workbench installed. Same flags as install.sh: --dry-run, --with <optionals>.
# Without --with, every installed optional and then the core are removed.
exec bash "$(dirname "${BASH_SOURCE[0]}")/install.sh" --uninstall "$@"
