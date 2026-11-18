---
name: clipar-gta-br
description: Fluxo automático de cortes de GTA em português. Acha as lives (VODs) novas de GTA dos streamers brasileiros listados em clipper-gta-br/streamers.json e transforma cada uma em até 3 clipes verticais com a skill ai-stream-clipper (facecam em cima, legendas, hook e texto de post em pt-BR). Use quando o usuário disser "clipar lives de GTA", "faz os cortes de hoje", "roda o fluxo de cortes", "/clipar-gta-br", ou quando a tarefa agendada rodar.
---

# Cortes automáticos de GTA (pt-BR)

Depende da skill **ai-stream-clipper** instalada com o patch pt-BR (`clipper-gta-br/instalar.sh` ou
`instalar.ps1`). Siga as instruções dela para cada live; aqui fica só a orquestração. Fale em português.

`REPO` = a raiz deste repositório. `CLIPPER` = `~/.claude/skills/ai-stream-clipper` (Windows:
`%USERPROFILE%\.claude\skills\ai-stream-clipper`). Rode Python sempre com `PYTHONUTF8=1 PYTHONIOENCODING=utf-8`
e `python -I` (Mac/Linux: `python3`).

## 1. Pré-checagem
Se `CLIPPER/SKILL.md` não existir ou não mencionar "Portuguese", pare e diga para rodar o instalador.
Se `~/.ai-stream-clipper/config.json` não existir, rode `CLIPPER/scripts/clipper.py setup` primeiro.

## 2. Achar lives novas
```
python -I REPO/clipper-gta-br/novas_lives.py
```
Retorna um JSON com as lives pendentes (no máximo `max_lives_por_rodada`). Lista vazia: diga
"nenhuma live nova" e termine. Avisos `[aviso]` de um canal não impedem os outros: cite-os no resumo.

## 3. Para cada live, uma de cada vez
1. `clipper.py prepare <url> --lang pt --top 3` (demora: rode em background e espere terminar).
2. Escolha os momentos exatamente como manda o SKILL.md do ai-stream-clipper (índice → chunks →
   `moments.json` → `check`), seguindo a seção de GTA RP. Todos os textos (hook, title, caption) em pt-BR
   natural. Hashtags: `#GTARP` (ou `#GTA6` se for GTA 6), nome do streamer sem espaços, `#cortes`.
3. Se nenhum candidato passar de nota 6, não renderize: marque como `pulada` e explique por quê.
4. `clipper.py render <job>` e confira cada `sheet.jpg` (rosto inteiro em cima, legenda legível, sem
   caractere quebrado). Refaça com `--facecam` se o rosto estiver errado.
5. Registre: `python -I REPO/clipper-gta-br/novas_lives.py --marcar <url> --status ok`
   (ou `--status erro --nota "<motivo curto>"` se falhou — assim não fica tentando para sempre;
   para tentar de novo depois, apague a linha em `~/StreamClipper/processadas.json`).

## 4. Resumo final
Para cada live: streamer, título, quantos clipes, caminho de cada `.mp4` e `post.md`, nota de cada clipe.
Termine com: "Só publique cortes de streamers que permitem cortes, e assista cada clipe antes de postar."
Nunca publique nada automaticamente.
