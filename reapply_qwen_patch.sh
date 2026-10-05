#!/usr/bin/env bash
# reapply_qwen_patch.sh
# Re-applies the one-line patch that fixes Qwen Code 0.23.x when talking to
# strict OpenAI-compatible endpoints (e.g. TokenRouter, some LiteLLM/Rust
# backends) that require the "parameters" field on every tool.
#
# The bug: Qwen Code omits "parameters" for parameterless tools
# (e.g. cron_list / list_agents), which breaks strict backends with 400
# "missing field parameters".
#
# The patch: send {"type":"object","properties":{}} instead of dropping it.
#
# Usage:
#   bash reapply_qwen_patch.sh          # re-apply (needs write access)
#   bash reapply_qwen_patch.sh show     # show the diff vs the original backup
#   bash reapply_qwen_patch.sh diff     # same as "show"
#
# Requirement: the backup must exist at
#   <qwen-code>/lib/chunks/chunk-NPKCVSXX.js.bak-0.23.2
# (created on first run; re-created automatically from /dev/null if missing)
#
# This script is NOT included in the Qwen Code install — keep a copy of it
# somewhere safe (e.g. your dotfiles) and run it AFTER every `qwen upgrade`
# or reinstall, because the patched chunk gets overwritten on install.

set -euo pipefail

QWEN_BIN="$(command -v qwen || true)"
if [[ -z "${QWEN_BIN}" ]]; then
  echo "❌ qwen no encontrado en PATH. Ejecuta: bash reapply_qwen_patch.sh" >&2
  exit 1
fi

INSTALLED_DIR="$(cd "$(dirname "${QWEN_BIN}")" && pwd)"
CHUNK="${INSTALLED_DIR}/lib/chunks/chunk-NPKCVSXX.js"
BACKUP="${CHUNK}.bak-0.23.2"

if [[ ! -f "${CHUNK}" ]]; then
  echo "❌ No encontre el chunk: ${CHUNK}" >&2
  echo "   Reinstala Qwen Code e intenta de nuevo." >&2
  exit 1
fi

# First run (or after an uninstall/install swapped the files): re-use a
# directory-wide backup from the same user home, else create one from the
# pristine chunk.
if [[ ! -f "${BACKUP}" ]]; then
  for CANDIDATE in \
    "${HOME}/.local/lib/qwen-code/lib/chunks/chunk-NPKCVSXX.js.bak-0.23.2" \
    "${HOME}/.local/share/qwen-code/lib/chunks/chunk-NPKCVSXX.js.bak-0.23.2" \
  ; do
    if [[ -f "${CANDIDATE}" ]]; then
      cp "${CANDIDATE}" "${BACKUP}"
      echo "ℹ️  Backup restaurado desde ${CANDIDATE} -> ${BACKUP}"
      break
    fi
  done
fi

if [[ ! -f "${BACKUP}" ]]; then
  cp "${CHUNK}" "${BACKUP}"
  echo "ℹ️  Backup creado desde el chunk actual -> ${BACKUP}"
fi

# Replace the "drop parameters" line with a minimal valid empty schema.
if grep -q 'parameters = void 0;' "${CHUNK}"; then
  sed -i 's/parameters = void 0;/parameters = { type: "object", properties: {} };/' "${CHUNK}"
  echo "✅ Patch reaplicado en ${CHUNK}"
else
  echo "✅ Ya aplica el patch (no estaba necesario)."
fi

# Syntax check so a broken install never surprises you.
if command -v node >/dev/null 2>&1; then
  node --check "${CHUNK}" && echo "✓ Syntax OK"
else
  echo "⚠️  node no disponible: omito chequeo de sintaxis."
fi

echo "⚠️  Recuerda: esta carpeta no sale de la instalacion; ejecuta el patch"
echo "   despues de cada actualizacion (qwen upgrade) si este error reaparece."
