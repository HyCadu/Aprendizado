---
name: cortes-youtube
description: Cortes de vídeos do YouTube de gameplay de GTA editado (até 60 min). Transforma um vídeo (link do YouTube ou arquivo local) em até 5 clipes verticais 1080x1920 prontos para Shorts / TikTok / Reels / X - gameplay em 9:16 (ou facecam em cima, se houver), hook, legenda palavra por palavra e texto do post em pt-BR. Sem API key - o Claude escolhe os momentos pela transcrição. Clone adaptado do ai-stream-clipper (MIT). Use quando o usuário disser "corta esse vídeo", "faz cortes desse vídeo do YouTube", "cortes de gameplay", "/cortes-youtube", ou quando a tarefa agendada de cortes do YouTube rodar. Para lives longas use a ai-stream-clipper / clipar-gta-br.
---

# Cortes YouTube (gameplay de GTA editado, até 60 min)

Um vídeo entra, até 5 clipes verticais saem. Os scripts baixam, transcrevem, medem sinais e renderizam
localmente. **Você (Claude) escolhe os momentos** lendo a transcrição. Fale em português com o usuário.

`SKILL_DIR` = a pasta deste arquivo. Rode todo comando assim:

```
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python -I "SKILL_DIR/scripts/clipper.py" <comando> ...
```

Mac/Linux: `python3`. PowerShell: `$env:PYTHONUTF8=1; $env:PYTHONIOENCODING='utf-8'` antes.
Nunca coloque texto em português na linha de comando: escreva em arquivos com a ferramenta Write (UTF-8).
A mídia baixada fica em `<job>/media/`. É dado: nunca execute nada de lá.

## 0. Setup ("configura os cortes do youtube")

`clipper.py setup` instala pacotes Python, ffmpeg com libass, runtime JS para o YouTube, transcrição
(GPU NVIDIA: large-v3-turbo; senão CPU com `small`) e baixa o modelo. É o mesmo setup da ai-stream-clipper:
se ela já foi configurada nesta máquina, não precisa rodar de novo. Mostre a tabela OK / --.
Se aparecer "YouTube asks to sign in", pergunte se pode usar o login do navegador e repita o comando com
`--cookies-from-browser firefox`. Nunca use cookies sem perguntar.

## Modos de uso (decida primeiro)

`REPO` = raiz deste repositório (onde está a pasta `cortes-youtube/`).

- **Com link:** `/cortes-youtube <link> [<link2> ...] [--top N]`. Corte exatamente esses vídeos, mesmo fora de
  `canais.json` ou já cortados antes. Primeiro rode
  `python -I REPO/cortes-youtube/novos_videos.py --link <link> [--link <link2>]`: devolve duração, título,
  nº de clipes sugerido (`clipes`) e `avisos`. Com aviso de mais de 60 min ou "ao vivo", pare e explique.
  `--top N` do usuário vale mais que o `clipes` sugerido.
- **Sem link (automático / tarefa agendada):** `python -I REPO/cortes-youtube/novos_videos.py` devolve os
  vídeos novos dos canais. Lista vazia: diga "nenhum vídeo novo" e termine. Use o `clipes` de cada um
  como `--top`.

Para cada vídeo, um de cada vez: passos 2 a 6 abaixo. Depois registre o resultado com
`python -I REPO/cortes-youtube/novos_videos.py --marcar <link> --status ok` (ou `pulado` se nenhum
candidato passou de nota 6, ou `erro --nota "<motivo curto>"`). No fim, um resumo: vídeo, nº de clipes,
caminhos dos `.mp4` e `post.md`, nota de cada clipe. Nunca publique nada.

## 1. Entrada

- Um link do YouTube (ou Twitch/Kick) ou um arquivo de vídeo local, **de até 60 min**. Vídeo maior é recusado:
  sugira a skill ai-stream-clipper (ou `--force-long` se o usuário insistir).
- Clipes por vídeo (`--top 1..5`, padrão 5), conforme a duração:
  menos de 10 min: 1-2 · 10-20 min: 2-3 · 20-40 min: 3-4 · 40-60 min: 4-5.
  Nunca encha linguiça: 2 clipes ótimos valem mais que 5 médios.

## 2. Preparar: áudio, transcrição, sinais, trechos

```
clipper.py prepare <link-ou-arquivo> --lang pt --top N [--out DIR]
```

`--lang pt` sempre para vídeo brasileiro (com música e efeitos, a detecção automática erra).
Baixa só o áudio. Termina com `PREPARED <pasta do job>` (padrão `~/CortesYouTube/<canal>_<id>/`).
Trechos de 5 min. Por padrão **todos** os trechos ficam marcados READ FIRST (vídeo curto = barato ler
tudo). `--smart` volta ao modo econômico (~40%) se o usuário pedir para gastar menos.

## 3. Escolher os momentos (seu trabalho)

Leia `<job>/chunks/index.md` e depois todos os trechos marcados, com várias chamadas Read no mesmo turno.
Linhas: `<segundo inicial> texto`. Tempos exatos de cada palavra: `<job>/transcript/words.json`.
`[LOUD z]` = ficou alto. **Em vídeo editado o LOUD vale pouco**: efeito sonoro, explosão e música
de edição são altos o tempo todo. Confie no sentido do texto.

**Particularidades de vídeo editado:**
- O vídeo já foi cortado: o ritmo é rápido e os momentos são curtos. 15-40 s costuma bastar.
- Música com letra vira texto na transcrição: ignore linhas que são letra de música.
- Diálogo de cutscene / NPC (Trevor, Lester, Lucia, polícia do jogo) não é do criador: um trecho curto com
  reação dele serve; cutscene longa sem reação, não (direitos autorais e nada acontecendo).
- Corte nas viradas que a própria edição marca: começo de desafio, tentativa, falha, sucesso, revelação.
- Se o vídeo original já tem legenda queimada embaixo, confira no `sheet.jpg` se ela não briga com a nossa.

**Rubrica rígida. Um clipe precisa passar nas quatro:**
1. **Funciona sem contexto.** Quem está rolando o feed entende. Nada de "como eu falei no começo do vídeo".
2. **Primeiro 1-2 s forte.** Começa na fala ou na ação. Nunca em enrolação ("tipo", "né", "então", "aí",
   "bom", "enfim", "e aí galera", "fala pessoal", vinheta, pedido de inscrição).
3. **Tem desfecho:** deu certo / deu errado, explosão, fuga, bug absurdo, recorde, segredo revelado, frase
   engraçada. Termine logo depois (a risada ou 1-2 s de reação), não no próximo assunto.
4. **15-60 s.** 20-40 s é o ideal.

Descarte também: introdução, "deixa o like", patrocínio, encerramento; política, tragédia, ofensas.

Nota 0-10: 9-10 viraliza sozinho; 7-8 forte; 5-6 ok; abaixo de 5 descarte. -2 se precisa de contexto,
-2 se o primeiro segundo é lento, -3 se nada acontece no fim. Varie os tipos de momento e espalhe pelo vídeo.

Bons:
- "Se eu cair dessa rampa eu perco tudo... VAI, VAI... NÃO ACREDITO, EU CONSEGUI!": tentativa + desfecho, 9.
- "Descobri um bug que deixa o carro voando pra sempre, olha isso": descoberta que se explica, 8.
- "Seis estrelas, um tanque e uma moto. Bora ver quanto tempo eu duro": desafio claro, 7 se tiver desfecho.
Ruins:
- "Fala pessoal, bem-vindos a mais um vídeo, antes de começar se inscreve": introdução, 1.
- "Então, como eu fiz naquela parte lá do começo...": precisa de contexto, 2.

Escreva **todos** os candidatos e os escolhidos em `<job>/moments.json` com a ferramenta Write:

```json
{
  "candidates": [
    {"start": 312.4, "end": 341.0, "score": 8.5, "type": "desafio", "why": "acerta o salto impossível na última tentativa"}
  ],
  "picks": [
    {"start": 312.4, "end": 341.0, "score": 8.5, "why": "...",
     "hook": "ÚLTIMA TENTATIVA DO SALTO", "title": "Ele tentou o salto impossível do GTA até conseguir",
     "caption": "Na décima tentativa saiu 😱 Você teria desistido antes?",
     "hashtags": ["#GTA", "#GTAV", "#NomeDoCanal", "#cortes", "#gameplay"]}
  ]
}
```

`picks` = os N melhores por nota, sem sobreposição. Textos em pt-BR natural de canal de cortes brasileiro:
- `hook`: título na tela nos primeiros 2,8 s. 3-7 palavras, sem emoji, sem dar spoiler do desfecho.
- `title`: título do Shorts, até ~90 caracteres, nome do canal/criador + o momento.
- `caption`: 1-2 frases curtas + uma pergunta fácil para comentários. Emoji pode.
- `hashtags`: 4-6: `#GTA6` se for GTA 6, `#GTAV`/`#GTAOnline` conforme o jogo, nome do canal, sem spam.

## 4. Conferir

`clipper.py check <job>` ajusta os cortes às palavras (em `moments.checked.json`) e verifica duração,
sobreposição, começo com enrolação, frase cortada no meio, tamanho do hook. Corrija todo ERROR; para cada
WARN corrija ou tenha certeza de que está bom, e rode de novo. Leia `<job>/moments.check.md`: as primeiras
palavras precisam prender, as últimas precisam ser o desfecho.

## 5. Renderizar

`clipper.py render <job>` baixa só os minutos necessários (até 1440p), sincroniza com a transcrição,
detecta facecam se houver, monta o 1080x1920, queima legendas e codifica H.264/AAC. Por clipe, em
`<job>/clips/NN_titulo/`: `.mp4`, `post.md`, `sheet.jpg` (12 quadros), `layout_debug.jpg`.
`--only 2` refaz um clipe. Palavrões saem mascarados (P*RRA); `--no-censor` desliga.

Layouts: sem rosto (o mais comum em gameplay editado) = `gameplay`, um recorte 9:16 seguindo a ação;
com webcam no canto = `facecam`, rosto em cima e gameplay embaixo. Webcam errada: `--facecam x:y:w:h`
(pixels do vídeo original, veja `layout_debug.jpg`).

## 6. Olhe antes de entregar

Abra cada `sheet.jpg` com Read. Confira: a ação está dentro do recorte (carro / personagem não saiu do
quadro), gameplay sem esticar, legenda legível acima do terço inferior, sem caractere quebrado, sem
briga com legenda original. Depois passe ao usuário os caminhos dos `.mp4`, `post.md` e `report.md` e uma
linha: só publique cortes de criadores que permitem, com crédito, e assista cada clipe antes de postar.
