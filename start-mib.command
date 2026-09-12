#!/bin/zsh
set -eu
cd "${0:A:h}"
exec python3 scripts/run_mib.py
