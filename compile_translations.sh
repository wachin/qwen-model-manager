#!/bin/bash
# Compile .ts translation files to .qm binary files
# Usage: ./compile_translations.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TS_DIR="$SCRIPT_DIR/translations"

if [ ! -d "$TS_DIR" ]; then
    echo "Error: translations/ directory not found."
    exit 1
fi

echo "Compiling translations..."

for ts_file in "$TS_DIR"/*.ts; do
    [ -f "$ts_file" ] || continue
    basename=$(basename "$ts_file" .ts)
    qm_file="$TS_DIR/${basename}.qm"
    lrelease "$ts_file" -qm "$qm_file" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "  Compiled: $basename.ts -> $basename.qm"
    else
        echo "  Failed:   $basename.ts (is lrelease installed?)"
    fi
done

echo "Done."
