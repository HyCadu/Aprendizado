#!/usr/bin/env bash
# Instala a skill ai-stream-clipper em ~/.claude/skills e aplica o patch de português (pt-BR).
# Uso (Mac/Linux): bash clipper-gta-br/instalar.sh
set -euo pipefail

REPO="https://github.com/arcticloud/ai-stream-clipper"
COMMIT="b3546b7e1ce3347dd253a627ccb9e25e5ae32f7a"   # versão em que o patch foi testado
DEST="$HOME/.claude/skills/ai-stream-clipper"
PATCH_ORIG="$(cd "$(dirname "$0")" && pwd)/ai-stream-clipper-pt-br.patch"
# Se o .patch veio com CRLF (cópia do Windows), ele não aplica: usa uma cópia só com LF.
PATCH="$(mktemp)"; trap 'rm -f "$PATCH"' EXIT
tr -d '\r' < "$PATCH_ORIG" > "$PATCH"

if [ ! -d "$DEST/.git" ]; then
  echo "Clonando $REPO em $DEST ..."
  mkdir -p "$(dirname "$DEST")"
  git -c core.autocrlf=false clone "$REPO" "$DEST"
fi

cd "$DEST"
if git apply --reverse --check "$PATCH" 2>/dev/null; then
  echo "Patch pt-BR já estava aplicado."
else
  # Volta a skill para a versão original (desfaz um patch antigo, se houver) antes de aplicar o novo.
  git reset -q --hard "$COMMIT"
  git apply "$PATCH"
  echo "Patch pt-BR aplicado."
fi

echo
echo "Pronto. Agora abra o Claude Code e digite:  configura o clipper"
