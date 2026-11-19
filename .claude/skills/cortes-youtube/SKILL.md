---
name: cortes-youtube
description: Cortes de vídeos do YouTube de gameplay de GTA (qualquer duração). Transforma um vídeo (link do YouTube ou arquivo local) em até 5 clipes verticais 1080x1920 prontos para Shorts / TikTok / Reels / X - gameplay em 9:16 (ou facecam em cima, se houver), hook, legenda palavra por palavra e texto do post. Pergunta a cada vídeo se a legenda sai em português ou em inglês e traduz nos dois sentidos (vídeo gringo com legenda pt-BR, vídeo brasileiro com legenda em inglês). Sem API key - o Claude escolhe os momentos pela transcrição. Clone adaptado do ai-stream-clipper (MIT). Use quando o usuário disser "corta esse vídeo", "faz cortes desse vídeo do YouTube", "cortes de gameplay", "/cortes-youtube", ou quando a tarefa agendada de cortes do YouTube rodar. Para lives longas use a ai-stream-clipper / clipar-gta-br.
---

# Cortes YouTube (gameplay de GTA, qualquer duração)

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

- **Com link:** `/cortes-youtube <link> [<link2> ...] [--top N] [--legenda pt|en]`. Corte exatamente esses
  vídeos, mesmo fora de `canais.json` ou já cortados antes. Primeiro rode
  `python -I REPO/cortes-youtube/novos_videos.py --link <link> [--link <link2>]`: devolve duração, título,
  nº de clipes sugerido (`clipes`) e `avisos`. Com aviso "ao vivo", pare e explique; aviso de vídeo longo é só
  informação. `--top N` do usuário vale mais que o `clipes` sugerido.
- **Sem link (automático / tarefa agendada):** `python -I REPO/cortes-youtube/novos_videos.py` devolve os
  vídeos novos dos canais. Lista vazia: diga "nenhum vídeo novo" e termine. Use o `clipes` de cada um
  como `--top` e o `legenda` de cada um como idioma da legenda.

**Idioma da legenda (pergunte em todo corte).** Antes do `prepare`, pergunte ao usuário, com a ferramenta
AskUserQuestion, uma pergunta só para todos os links do pedido: "Legenda em português ou em inglês?"
(opções: Português (pt-BR), Inglês). Não pergunte quando: o pedido já diz (`--legenda pt|en`, "com legenda em
inglês"...); é o modo automático (use o `legenda` do item, padrão `pt`); ou não há ninguém para responder
(rodando por `claude -p`, `rodar_automatico`, GTA Clipper Studio, tarefa agendada: use `pt`).
O idioma da legenda vale para **todos os textos do clipe**: legenda, hook, `title`, `caption` e hashtags.
Se a legenda é no idioma falado no vídeo, nada é traduzido; se é no outro, o passo 4b traduz.

Para cada vídeo, um de cada vez: passos 2 a 6 abaixo. Depois registre o resultado com
`python -I REPO/cortes-youtube/novos_videos.py --marcar <link> --status ok` (ou `pulado` se nenhum
candidato passou de nota 6, ou `erro --nota "<motivo curto>"`). No fim, um resumo: vídeo, nº de clipes,
caminhos dos `.mp4` e `post.md`, nota de cada clipe. Nunca publique nada.

## 1. Entrada

- Um link do YouTube (ou Twitch/Kick) ou um arquivo de vídeo local, de **qualquer duração**. Acima de 60 min o
  `prepare` usa trechos de 10 min e marca ~40% como READ FIRST (leitura econômica); `--read-all` lê tudo.
- Clipes por vídeo (`--top 1..5`, padrão 5), conforme a duração:
  menos de 10 min: 1-2 · 10-20 min: 2-3 · 20-40 min: 3-4 · 40 min ou mais: 4-5.
  Nunca encha linguiça: 2 clipes ótimos valem mais que 5 médios.

## 2. Preparar: áudio, transcrição, sinais, trechos

```
clipper.py prepare <link-ou-arquivo> --lang pt|en|auto --top N [--out DIR]
```

`--lang` é o **idioma falado no vídeo** (não o da legenda): a transcrição e os tempos saem do áudio original.
Decida pelo título, canal e descrição: canal/título brasileiro = `pt`; gringo = `en`; sem certeza = `auto`.
Com `pt`/`en` forçado o prepare também detecta o idioma pelo áudio e imprime
`whisper: language = pt (detectado: pt 92%)`. Se aparecer `WARN: o áudio parece ser <x>`, o palpite estava
errado: rode o `prepare` de novo com `--lang <x>` (ele refaz a transcrição). Em vídeo brasileiro com música e
efeitos o `auto` pode errar para espanhol, por isso prefira `--lang pt` quando o canal é brasileiro.
Baixa só o áudio. Termina com `PREPARED <pasta do job>` (padrão `~/CortesYouTube/<canal>_<id>/`).
Até 60 min: trechos de 5 min, **todos** marcados READ FIRST. Mais longo: trechos de 10 min, ~40% READ FIRST.
`--smart` força o modo econômico; `--read-all` força ler tudo.

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

`picks` = os N melhores por nota, sem sobreposição. Textos **no idioma da legenda**: pt-BR natural de canal de
cortes brasileiro, ou inglês natural de canal de clipes americano ("HE DID NOT EXPECT THAT", "Paulinho loses it
in the police chase"), nunca tradução palavra por palavra:
- `hook`: título na tela nos primeiros 2,8 s. 3-7 palavras, sem emoji, sem dar spoiler do desfecho.
- `title`: título do Shorts, até ~90 caracteres, nome do canal/criador + o momento.
- `caption`: 1-2 frases curtas + uma pergunta fácil para comentários. Emoji pode.
- `hashtags`: 4-6: `#GTA6` se for GTA 6, `#GTAV`/`#GTAOnline` conforme o jogo, nome do canal, sem spam.

## 4. Conferir

`clipper.py check <job>` ajusta os cortes às palavras (em `moments.checked.json`) e verifica duração,
sobreposição, começo com enrolação, frase cortada no meio, tamanho do hook. Corrija todo ERROR; para cada
WARN corrija ou tenha certeza de que está bom, e rode de novo. Leia `<job>/moments.check.md`: as primeiras
palavras precisam prender, as últimas precisam ser o desfecho.

## 4b. Legenda no idioma escolhido

Rode sempre `clipper.py translate <job> --to <pt|en>` (o idioma da legenda escolhido).
- Legenda no idioma falado (vídeo `pt` com legenda `pt`, vídeo `en` com legenda `en`): ele só avisa que não
  precisa traduzir (e tira do caminho um `translation.json` antigo). Vá para o render.
- Legenda no outro idioma (`en` → `pt` ou `pt` → `en`): ele divide a fala de cada clipe em frases curtas com
  tempo exato e escreve `<job>/translate.md` (para ler, já com o estilo de tradução do idioma de destino) e
  `<job>/translation.todo.json` (modelo).
  1. Leia `translate.md` e escreva `<job>/translation.json` com a ferramenta Write, no formato do modelo:
     por clipe, o mesmo `key` e `lines` com **exatamente uma linha por frase, na mesma ordem**
     (`""` para barulho ou frase sem sentido).
  2. Como traduzir: língua falada de canal de cortes, curta. Para pt-BR: "Puta merda!", "Bora, porra!",
     "Esse jogo é de outra geração". Para inglês: "Bro, no way!", "Let's go!", "This game is next gen"
     (mano = bro, porra = damn, caralho = holy sh*t). Adapte gíria e palavrão, nunca palavra por palavra.
     Mantenha nomes próprios (Lucia, Brian, condados). Cada linha aparece só enquanto a frase original é
     falada: frase de 1 s pede 2-4 palavras. A censura de palavrão vale nos dois idiomas.
Se mudar um corte depois, rode `check` e `translate` de novo: o render recusa `translation.json` velho.

## 5. Renderizar

`clipper.py render <job>` baixa só os minutos necessários (até 1440p), sincroniza com a transcrição,
detecta facecam se houver, monta o 1080x1920, queima legendas e codifica H.264/AAC. Por clipe, em
`<job>/clips/NN_titulo/`: `.mp4`, `post.md`, `sheet.jpg` (12 quadros), `layout_debug.jpg`.
`--only 2` refaz um clipe. Palavrões saem mascarados (P*RRA); `--no-censor` desliga.
Com `translation.json` o log mostra `captions: translated to pt`: cada frase traduzida fica na tela no
intervalo da frase original e as palavras acendem distribuídas nesse intervalo (não palavra a palavra com o
áudio, porque a ordem das palavras muda entre idiomas). O check de sincronia continua valendo.
**Sincronia fala x legenda (critério obrigatório).** Para cada clipe o render mede no `.mp4` pronto:
1. `speech`: onde o áudio do clipe cai no áudio original (que a transcrição cronometrou). Tolerância 40 ms;
   fora disso recodifica sozinho com o corte corrigido.
2. `captions`: quando o destaque amarelo de cada palavra muda na tela, comparado ao instante em que a palavra
   é falada. Tolerância 120 ms.
Sai no log (`sync: speech ok (+0 ms), captions ok (+0 ms)`), em `clip.json` e em `report.md`.
`FAIL` em qualquer um = clipe reprovado: não entregue, investigue (corte, timestamps do filtro) e renderize de novo.
`unclear` (pouca fala, música alta, tela sem destaque visível) = confira você mesmo extraindo um quadro no
instante de uma palavra (`words.json`) e vendo se a legenda destaca essa palavra.
Ajuste fino manual, só se tudo der ok e ainda parecer fora: `--caption-lead` (positivo adianta, negativo
atrasa; use `=` com negativo, ex. `--caption-lead=-0.1`).

Visual do render (padrão, sem precisar pedir): zoom de 12% nos trechos de narração mais forte (`--zoom 1.2` mais
forte, `--no-zoom` desliga) e identidade visual com moldura neon roxa e arroba do perfil, lidas de `brand` em
`~/.ai-stream-clipper/config.json` (`{"frame": true, "handle": "@perfil"}`; `--no-brand` desliga só neste render).
Só use `--no-zoom` / `--no-brand` quando o pedido disser.
Para trocar a arroba ou a moldura (quando o usuário pedir): `clipper.py brand --handle @perfil`
(`--handle ""` tira a arroba; `--frame off` tira a moldura). Sem arroba configurada, sai só a moldura.

Layouts: sem rosto (o mais comum em gameplay editado) = `gameplay`, um recorte 9:16 seguindo a ação;
com webcam no canto = `facecam`, rosto em cima e gameplay embaixo. Webcam errada: `--facecam x:y:w:h`
(pixels do vídeo original, veja `layout_debug.jpg`).

## 6. Olhe antes de entregar

Primeiro confira a linha `sync` de cada clipe no `report.md`: só entregue clipe com `sync ok` (ou `check`
já conferido à mão). Abra cada `sheet.jpg` com Read. Confira: a ação está dentro do recorte (carro / personagem não saiu do
quadro), gameplay sem esticar, legenda legível acima do terço inferior, sem caractere quebrado, sem
briga com legenda original. Depois passe ao usuário os caminhos dos `.mp4`, `post.md` e `report.md` e uma
linha: só publique cortes de criadores que permitem, com crédito, e assista cada clipe antes de postar.
