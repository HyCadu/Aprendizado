# Cortes automáticos de GTA em português

Fluxo que pega as lives de GTA dos maiores streamers brasileiros e transforma cada uma em até 3 clipes
verticais (1080x1920) prontos para Shorts / TikTok / Reels: facecam em cima, gameplay embaixo, hook,
legenda palavra por palavra e texto do post, tudo em pt-BR. Usa a skill
[ai-stream-clipper](https://github.com/arcticloud/ai-stream-clipper) com um patch que adiciona português.
Sem API key: o próprio Claude Code escolhe os momentos.

## O que tem aqui

| Arquivo | Para quê |
|---|---|
| `clipper-gta-br/instalar.sh` / `instalar.ps1` | Clona a skill em `~/.claude/skills/ai-stream-clipper` e aplica o patch pt-BR |
| `clipper-gta-br/ai-stream-clipper-pt-br.patch` | Português: palavras de reação/enrolação, censura de palavrões (P\*RRA), regras de GTA RP, `--lang pt` |
| `clipper-gta-br/streamers.json` | Canais monitorados (edite à vontade) |
| `clipper-gta-br/novas_lives.py` | Acha VODs novas de GTA que ainda não viraram cortes |
| `.claude/skills/clipar-gta-br/` | O comando `/clipar-gta-br`, que roda o fluxo inteiro |
| `clipper-gta-br/rodar_automatico.sh` / `.ps1` | Roda sem você estar olhando (para agendar) |

## Instalação (uma vez, no seu PC)

Precisa de: Claude Code, Python 3.9+, git, ~5 GB livres. Placa NVIDIA deixa a transcrição de 5 a 10 vezes mais rápida.

```bash
git clone https://github.com/HyCadu/Aprendizado && cd Aprendizado
bash clipper-gta-br/instalar.sh                                         # Mac/Linux
powershell -ExecutionPolicy Bypass -File clipper-gta-br\instalar.ps1    # Windows
```

Depois abra o Claude Code **dentro da pasta `Aprendizado`** e digite:

1. `configura o clipper`: instala ffmpeg, yt-dlp e o modelo de transcrição (5 a 15 min na primeira vez).
2. `python -I clipper-gta-br/novas_lives.py --verificar`: confere se os canais da lista existem.
   Corrija em `streamers.json` o link que der `[--]`.

## Uso

- **Manual:** no Claude Code, na pasta do repositório: `/clipar-gta-br`
- **Uma live específica:** `/clipar-gta-br https://www.twitch.tv/videos/...` (aceita vários links; funciona com YouTube e Kick, mesmo fora da lista)
- **Automático (todo dia):**
  - Mac/Linux: `crontab -e` e adicione `17 4 * * * /caminho/Aprendizado/clipper-gta-br/rodar_automatico.sh`
  - Windows: veja o comando `schtasks` no topo de `rodar_automatico.ps1`

Os clipes ficam em `~/StreamClipper/<canal>_<id>/clips/`: o `.mp4`, o `post.md` com títulos e hashtags e
um `sheet.jpg` para conferir rápido. Logs da execução automática ficam em `~/StreamClipper/logs/`.
O fluxo **nunca publica nada sozinho**.

## Regras do fluxo

- Até 2 lives novas por rodada (`max_lives_por_rodada`), só dos últimos 3 dias, só lives de 30 min ou mais.
- Com `"so_gta": true`, só entram lives cujo título tem "gta", "rp", "cidade" etc. (`palavras_gta`).
- Cada live é processada uma vez só (histórico em `~/StreamClipper/processadas.json`).
- Live ainda ao vivo é ignorada até virar VOD.

## Importante

Só publique cortes de streamers que **permitem cortes** (muitos têm programa oficial de cortes, com regras de
crédito e monetização). Confira as regras de cada um e assista cada clipe antes de postar.
