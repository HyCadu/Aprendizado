---
name: clipar-gta-br
description: Fluxo automático de cortes de lives de GTA. Acha as lives (VODs) novas de GTA dos streamers listados em clipper-gta-br/streamers.json (brasileiros ou gringos) e transforma cada uma em até 10 clipes verticais (3 por padrão) com a skill ai-stream-clipper (facecam em cima, legendas, hook e texto de post), com legenda em português ou inglês e tradução nos dois sentidos. Use quando o usuário disser "clipar lives de GTA", "faz os cortes de hoje", "roda o fluxo de cortes", "/clipar-gta-br", ou quando a tarefa agendada rodar.
---

# Cortes automáticos de lives de GTA

Depende da skill **ai-stream-clipper** instalada com o patch pt-BR (`clipper-gta-br/instalar.sh` ou
`instalar.ps1`). Siga as instruções dela para cada live; aqui fica só a orquestração. Fale em português.

`REPO` = a raiz deste repositório. `CLIPPER` = `~/.claude/skills/ai-stream-clipper` (Windows:
`%USERPROFILE%\.claude\skills\ai-stream-clipper`). Rode Python sempre com `PYTHONUTF8=1 PYTHONIOENCODING=utf-8`
e `python -I` (Mac/Linux: `python3`).

## 1. Pré-checagem
Se `CLIPPER/SKILL.md` não existir ou não mencionar "Portuguese", pare e diga para rodar o instalador.
Se `~/.ai-stream-clipper/config.json` não existir, rode `CLIPPER/scripts/clipper.py setup` primeiro.

## 2. Achar lives novas
**Se o usuário passou um ou mais links** (ex.: `/clipar-gta-br https://www.twitch.tv/videos/123`), use só
esses links, mesmo que não estejam em `streamers.json` ou já tenham sido processados, e pule para o passo 3.
Se ele pediu um número de clipes ("só 1 corte"), use `--top N` (1 a 10); `--legenda pt|en` diz a legenda.
Sem links:
```
python -I REPO/clipper-gta-br/novas_lives.py
```
Retorna um JSON com as lives pendentes (no máximo `max_lives_por_rodada`), cada uma com `idioma` (falado
na live) e `legenda` (idioma da legenda) do streamer. Lista vazia: diga "nenhuma live nova" e termine.
Avisos `[aviso]` de um canal não impedem os outros: cite-os no resumo.

## 2b. Idiomas
- **Idioma falado** (`--lang` do prepare): o `idioma` do item; com link, o `idioma` do streamer se ele está em
  `streamers.json`, senão decida pelo canal e título (brasileiro = `pt`, gringo = `en`, sem certeza = `auto`).
- **Idioma da legenda:** o `legenda` do item ou o `--legenda` do pedido. Se não veio e há alguém para
  responder, pergunte uma vez para todas as lives (AskUserQuestion: "Legenda em português ou em inglês?",
  opções Português (pt-BR), Inglês). Sem ninguém para responder (`claude -p`, `rodar_automatico`, GTA Clipper
  Studio, tarefa agendada): `pt`.
- Todos os textos do clipe (legenda, hook, title, caption) saem no idioma da legenda.

## 3. Para cada live, uma de cada vez
1. `clipper.py prepare <url> --lang <idioma falado> --top 3` (demora: rode em background e espere terminar).
   Se aparecer `WARN: o áudio parece ser <x>`, rode o prepare de novo com `--lang <x>`.
2. Escolha os momentos exatamente como manda o SKILL.md do ai-stream-clipper (índice → chunks →
   `moments.json` → `check`), seguindo a seção de GTA RP. Todos os textos (hook, title, caption) no idioma da
   legenda, naturais (pt-BR de canal de cortes ou inglês de canal de clipes). Hashtags: `#GTARP` (ou `#GTA6`
   se for GTA 6), nome do streamer sem espaços, `#cortes` (em inglês: `#clips`).
3. Se nenhum candidato passar de nota 6, não renderize: marque como `pulada` e explique por quê.
4. `clipper.py translate <job> --to <idioma da legenda>` e, se ele pedir, escreva `translation.json`
   (passo 4b do SKILL.md do ai-stream-clipper). Legenda no idioma falado: ele só avisa e segue.
5. `clipper.py render <job>` e confira cada `sheet.jpg` (rosto inteiro em cima, legenda legível, sem
   caractere quebrado). Refaça com `--facecam` se o rosto estiver errado.
6. Registre: `python -I REPO/clipper-gta-br/novas_lives.py --marcar <url> --status ok`
   (ou `--status erro --nota "<motivo curto>"` se falhou — assim não fica tentando para sempre;
   para tentar de novo depois, apague a linha em `~/StreamClipper/processadas.json`).

## 4. Resumo final
Para cada live: streamer, título, quantos clipes, caminho de cada `.mp4` e `post.md`, nota de cada clipe.
Termine com: "Só publique cortes de streamers que permitem cortes, e assista cada clipe antes de postar."
Nunca publique nada automaticamente.
