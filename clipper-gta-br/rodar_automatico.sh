#!/usr/bin/env bash
# Roda o fluxo de cortes de lives sem interação (para agendar no cron / launchd).
#   Automático (streamers de streamers.json):  clipper-gta-br/rodar_automatico.sh
#   Live(s) específica(s):                     clipper-gta-br/rodar_automatico.sh --link URL [--link URL2] [--top 2] [--legenda en]
#   --legenda pt|en: idioma da legenda (padrão pt; no automático, o "legenda" do streamer em streamers.json)
# Cron (todo dia às 4h17):  17 4 * * * /caminho/Aprendizado/clipper-gta-br/rodar_automatico.sh
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LINKS=(); TOP=""; LEGENDA=""
while [ $# -gt 0 ]; do
  case "$1" in
    --link) [ $# -ge 2 ] || { echo "falta a URL depois de --link" >&2; exit 2; }; LINKS+=("$2"); shift 2 ;;
    --top)  [ $# -ge 2 ] || { echo "falta o número depois de --top" >&2; exit 2; }; TOP="$2"; shift 2 ;;
    --legenda) [ $# -ge 2 ] || { echo "falta pt ou en depois de --legenda" >&2; exit 2; }; LEGENDA="$2"; shift 2 ;;
    -h|--help) sed -n 2,6p "$0"; exit 0 ;;
    *) echo "opção desconhecida: $1 (use --link URL, --top N ou --legenda pt|en)" >&2; exit 2 ;;
  esac
done
case "$TOP" in ""|[1-9]|10) ;; *) echo "--top deve ser de 1 a 10" >&2; exit 2 ;; esac
case "$LEGENDA" in ""|pt|en) ;; *) echo "--legenda deve ser pt ou en" >&2; exit 2 ;; esac

PROMPT="/clipar-gta-br"
[ ${#LINKS[@]} -gt 0 ] && PROMPT="$PROMPT ${LINKS[*]}"
[ -n "$TOP" ] && PROMPT="$PROMPT (só $TOP cortes por live)"
[ -n "$LEGENDA" ] && PROMPT="$PROMPT --legenda $LEGENDA"

LOG_DIR="$HOME/StreamClipper/logs"; mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/$(date +%Y-%m-%d_%H%M%S).log"
cd "$REPO"
echo "Rodando: $PROMPT  (log em $LOG)"
# Libera só o necessário: python (scripts da skill), leitura/escrita de arquivos. Nada de publicar.
claude -p "$PROMPT" \
  --allowedTools "Bash(python3:*)" "Bash(PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python3:*)" "Read" "Write" "Glob" \
  --add-dir "$HOME/StreamClipper" --add-dir "$HOME/.claude/skills/ai-stream-clipper" \
  > "$LOG" 2>&1
