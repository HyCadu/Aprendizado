#!/usr/bin/env bash
# Roda o fluxo de cortes sem interação (para agendar no cron / launchd).
# Exemplo de cron (todo dia às 4h17):  17 4 * * * /caminho/Aprendizado/clipper-gta-br/rodar_automatico.sh
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$HOME/StreamClipper/logs"; mkdir -p "$LOG_DIR"
cd "$REPO"
# Libera só o necessário: python (scripts da skill), leitura/escrita de arquivos. Nada de publicar.
claude -p "/clipar-gta-br" \
  --allowedTools "Bash(python3:*)" "Bash(PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python3:*)" "Read" "Write" "Glob" \
  --add-dir "$HOME/StreamClipper" --add-dir "$HOME/.claude/skills/ai-stream-clipper" \
  > "$LOG_DIR/$(date +%Y-%m-%d_%H%M).log" 2>&1
