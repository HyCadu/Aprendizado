# Cortes de GTA em português

Transforma **lives** (Twitch, YouTube, Kick) e **vídeos do YouTube de qualquer duração** em clipes verticais
prontos para Shorts, TikTok e Reels: legenda palavra por palavra, título na tela e texto do post com
hashtags, tudo em português. Quem escolhe os melhores momentos é o Claude.

**Precisa de:** Windows 10 ou 11, assinatura paga do Claude (Pro ou Max) e 10 GB livres no disco.
Uma placa de vídeo NVIDIA deixa tudo de 5 a 10 vezes mais rápido, mas não é obrigatória.

---

## Antes de começar: use o PowerShell

Todos os comandos deste guia são digitados no **PowerShell**.

1. Aperte a tecla **Windows**, digite **PowerShell** e clique em **Windows PowerShell**.
2. Confira se a linha começa com **`PS C:\Users\...>`**. Sem o `PS` na frente, você abriu o Prompt de Comando: feche e abra o PowerShell.
3. Para colar um comando: copie, clique na janela e aperte o **botão direito do mouse**. Depois, **Enter**.

---

## Instalação (só uma vez)

### 1. Python
Baixe em **python.org/downloads** e abra o instalador.
**Marque a caixinha "Add python.exe to PATH"** antes de clicar em **Install Now**.

Feche e abra o PowerShell e confira: `python --version` → deve mostrar `Python 3.x.x`.

### 2. Git
Baixe em **git-scm.com/download/win** e instale clicando em **Next** em tudo.

Feche e abra o PowerShell e confira: `git --version` → deve mostrar `git version ...`.

### 3. Claude Code
```
irm https://claude.ai/install.ps1 | iex
```
Feche e abra o PowerShell e digite `claude`. Na primeira vez ele abre o navegador para você entrar na sua
conta do Claude. Para sair do Claude, digite `/exit`.

### 4. Baixar o projeto
Uma linha de cada vez:
```
cd $HOME\Documents
git clone -b ccr-60cf32d0-p6a8cl https://github.com/HyCadu/Aprendizado
cd Aprendizado
```

### 5. Instalar a skill de lives
```
powershell -ExecutionPolicy Bypass -File clipper-gta-br\instalar.ps1
```
Deve aparecer **"Patch pt-BR aplicado."**

### 6. Configurar
```
claude
```
Na caixa do Claude, digite **`configura o clipper`** e espere de 5 a 15 min.
Quando ele pedir permissão, escolha **Yes**.

Deve terminar com **READY**. Se aparecer **NOT READY**, digite: `conserta o que faltou e roda de novo`.
O setup resolve sozinho três problemas comuns: Python da Microsoft Store (instala o do python.org e pede
para abrir o terminal de novo), versão do PyAV que quebra a transcrição, e download do modelo que trava
(tenta de novo por outro caminho; se a internet cair, rodar de novo continua de onde parou).

---

## Como usar

Sempre que for usar, abra o PowerShell e digite:
```
cd $HOME\Documents\Aprendizado
claude
```
Depois digite um destes comandos na caixa do Claude:

| Quero cortar... | Digite |
|---|---|
| Um vídeo do YouTube (qualquer duração) | `/cortes-youtube LINK` |
| Um vídeo, com menos clipes (1 a 5) | `/cortes-youtube LINK --top 3` |
| Um vídeo, já dizendo o idioma da legenda | `/cortes-youtube LINK --legenda en` (ou `pt`) |
| Uma live que já terminou (brasileira ou gringa) | `/clipar-gta-br LINK` |
| Uma live, já dizendo o idioma da legenda | `/clipar-gta-br LINK --legenda en` (ou `pt`) |
| As lives novas dos streamers da lista | `/clipar-gta-br` |

**Idioma da legenda:** a cada vídeo ou live o Claude pergunta se a legenda sai em **português** ou em
**inglês**, e traduz nos dois sentidos: vídeo/live gringo com legenda em português, ou brasileiro com
legenda em inglês. Hook, título e post saem no mesmo idioma da legenda. O Claude traduz só as frases dos
clipes escolhidos, no mesmo estilo palavra por palavra. O idioma falado no vídeo ele descobre sozinho (e
confere pelo áudio). Sem ninguém para responder (automático, GTA Clipper Studio) a legenda sai em português.
No automático, cada canal pode ter `"legenda": "en"` em `canais.json`, e cada streamer `"idioma": "en"`
(gringo) e `"legenda"` em `streamers.json`. Já tinha instalado a skill de lives antes? Rode o passo 5 de novo.

Troque `LINK` pelo endereço do vídeo, por exemplo `https://www.youtube.com/watch?v=abc123`.
Quando o Claude pedir permissão, escolha **Yes**.

**Quanto tempo leva:**

| | Com placa NVIDIA | Sem placa NVIDIA |
|---|---|---|
| Vídeo de 20 min | ~3 min | ~10 a 15 min |
| Vídeo de 60 min | ~5 min | ~20 a 30 min |
| Vídeo de 3 horas | ~10 min | ~1 a 1,5 hora |
| Live de 4 horas | ~10 a 15 min | ~1 a 2,5 horas |

A parte mais demorada é a transcrição. Para ver o andamento, pergunte ao Claude: `como está a transcrição?`
Não feche a janela enquanto ele trabalha.

---

## Usar pelo programa (GTA CLIPPER STUDIO)

Também dá para cortar sem digitar comandos. Abra a pasta `gta-clipper-studio` e dê dois cliques em
**`GTA Clipper Studio.exe`** (ou em **`Abrir GTA Clipper Studio.bat`**, se o `.exe` ainda não foi gerado). Cole o link, escolha YouTube ou Twitch e a quantidade de cortes e clique
em **INICIAR PROCESSAMENTO**. O programa mostra o andamento, os logs e a biblioteca de vídeos. Ele usa as
mesmas skills e nunca publica nada. Detalhes em [`gta-clipper-studio/README.md`](gta-clipper-studio/README.md).

---

## Onde ficam os vídeos

Aperte **Windows + R**, digite um destes e aperte Enter:

- Vídeos do YouTube: `%USERPROFILE%\CortesYouTube`
- Lives: `%USERPROFILE%\StreamClipper`

Entre na pasta do canal e depois em **clips**. Em cada clipe:

- **`.mp4`**: o vídeo pronto.
- **`post.md`**: título, descrição e hashtags para cada rede. Abra com o Bloco de Notas, copie e cole.

### Conferir a legenda

Cada clipe (de vídeo ou de live) é conferido sozinho: o programa mede se a fala e a legenda estão no tempo
certo. O resultado fica no **`report.md`**, na pasta do vídeo, numa linha que começa com `sync`:

| Aparece | Significa |
|---|---|
| `sync ok` | Fala e legenda no tempo certo. Pode usar. |
| `sync check` | Uma parte não deu para medir (pouca fala, música alta ou vídeo do seu computador). Se aparecer `captions ok`, a legenda está certa; senão, assista e confira. |
| `sync FAIL` | Fora de sincronia. Não use. Peça ao Claude: `o clipe 2 deu FAIL na sincronia, refaz` |

Se a legenda parecer adiantada ou atrasada mesmo com `sync ok`, peça ao Claude:
`a legenda do clipe 2 está atrasada, ajusta` (ou `adiantada`).

**Assista cada clipe antes de postar.** Só poste cortes de quem permite cortes e dê crédito.

---

## Deixar automático (opcional)

Faça só depois que o uso normal já funcionou uma vez. Cole no PowerShell (é uma linha só):
```
schtasks /Create /SC DAILY /ST 04:17 /TN "Cortes GTA" /TR "powershell -ExecutionPolicy Bypass -File $HOME\Documents\Aprendizado\clipper-gta-br\rodar_automatico.ps1"
```
Todo dia às 4h17, se o computador estiver ligado, ele corta as lives novas sozinho e nunca publica nada.
O registro fica em `%USERPROFILE%\StreamClipper\logs`. Para desligar: `schtasks /Delete /TN "Cortes GTA" /F`

Para cortar sem abrir o Claude, também dá para passar o link direto no script:
```
.\cortes-youtube\rodar_automatico.ps1 -Link LINK -Top 3
.\clipper-gta-br\rodar_automatico.ps1 -Link LINK
```

**Mudar as listas** (peça ao Claude):

- Lives: `adiciona o streamer https://www.twitch.tv/NOME no streamers.json`
- YouTube: `adiciona o canal https://www.youtube.com/@NOME no canais.json e ativa`

---

## Deu problema?

| O que apareceu | O que fazer |
|---|---|
| A linha começa com `C:\Users\...>` sem `PS` | Você está no Prompt de Comando. Feche e abra o **Windows PowerShell**. |
| `python` "não é reconhecido" ou abre a Microsoft Store | Reinstale o Python marcando **"Add python.exe to PATH"**. Feche e abra o PowerShell. |
| `git` "não é reconhecido" | Feche e abra o PowerShell. Se continuar, reinstale o Git. |
| `claude` "não é reconhecido" | Digite `Test-Path $HOME\.local\bin\claude.exe`. Se der **False**, repita o passo 3. Se der **True**, cole `[Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path","User") + ";$HOME\.local\bin", "User")`, feche e abra o PowerShell. |
| "a execução de scripts foi desabilitada" | Copie o comando inteiro, com o `powershell -ExecutionPolicy Bypass -File` do começo. |
| `destination path 'Aprendizado' already exists` | Já foi baixado. Digite `cd Aprendizado` e siga. |
| O Claude não conhece `/cortes-youtube` ou `/clipar-gta-br` | Você abriu o Claude fora da pasta. Digite `/exit`, depois `cd $HOME\Documents\Aprendizado` e `claude`. |
| "YouTube asks to sign in" ou "not a bot" | Entre no YouTube pelo **Firefox** e diga ao Claude: `usa meus cookies do Firefox`. Ou espere 1 hora. |
| A legenda saiu sem sentido / em outro idioma | O Claude errou o idioma falado no vídeo. Diga: `o vídeo é em inglês, refaz a transcrição`. |
| "This stream is still live" | A live ainda não acabou. Espere o vídeo aparecer no canal. |
| Muito lento | Normal sem placa NVIDIA. Deixe rodando. |
| O rosto saiu cortado | Diga ao Claude: `o rosto ficou errado no clipe 2, arruma`. |
| Atualizar o projeto | Na pasta `Aprendizado`, digite `git pull` e depois rode de novo o instalador do passo 5 (atualiza a skill de lives). |
| Qualquer outro erro | Copie a mensagem e cole para o Claude com: `deu esse erro, resolve`. |

---

## Para quem quer saber como funciona

| Arquivo | Para quê |
|---|---|
| `.claude/skills/cortes-youtube/` | Skill de vídeos do YouTube (clone da [ai-stream-clipper](https://github.com/arcticloud/ai-stream-clipper), licença MIT; mudanças em `CLONE.md`) |
| `.claude/skills/clipar-gta-br/` | O comando `/clipar-gta-br` (lives) |
| `clipper-gta-br/instalar.ps1` | Instala a ai-stream-clipper e aplica o patch em português |
| `clipper-gta-br/streamers.json` | Streamers monitorados |
| `cortes-youtube/canais.json` | Canais do YouTube monitorados |
| `*/rodar_automatico.ps1` | Rodar sem abrir o Claude (agendamento ou `-Link`) |

**Regras dos cortes:**

- Até 3 clipes por live e até 5 por vídeo, conforme a duração.
- No automático: lives dos últimos 3 dias e vídeos dos últimos 7. Cada vídeo é cortado uma vez só.
- Palavrões aparecem mascarados na legenda (P\*RRA).
- Vídeo ou live em outro idioma: a transcrição e o tempo vêm do áudio original, e cada frase traduzida
  aparece na tela exatamente enquanto a frase original é falada.
