# Como usar: passo a passo do zero

Este guia leva você do computador "zerado" até o primeiro corte pronto. Não precisa saber programar.
Siga **na ordem** e não pule passos. Cada passo diz **o que fazer** e **o que você deve ver**.
Se aparecer algo diferente, vá até [Deu problema?](#deu-problema) no final.

> Tempo total na primeira vez: de 30 min a 1 hora (a maior parte é esperar downloads).
> Nas próximas vezes: é só o [Passo 8](#passo-8-fazer-cortes).

**Você vai precisar de:**
- Um computador com **Windows 10/11** ou **Mac**.
- Uma assinatura paga do **Claude** (Pro ou Max). O plano grátis não roda o Claude Code.
- Pelo menos **10 GB livres** no disco.
- Uma placa de vídeo **NVIDIA** deixa tudo de 5 a 10 vezes mais rápido, mas não é obrigatória.

Usa Mac? Pule para [Passo a passo no Mac](#passo-a-passo-no-mac).

---

## Passo a passo no Windows

### Como abrir o PowerShell (você vai usar várias vezes)

1. Aperte a tecla **Windows** do teclado.
2. Digite **PowerShell**.
3. Clique em **Windows PowerShell**.

Abre uma janela azul ou preta com um texto parecido com `PS C:\Users\SeuNome>`. É ali que você digita
os comandos deste guia.

**Para colar um comando:** copie aqui, clique na janela do PowerShell e aperte **o botão direito do mouse**
(ou Ctrl+V). Depois aperte **Enter**.

---

### Passo 1: instalar o Python

1. Entre em **https://www.python.org/downloads/** e clique no botão amarelo **Download Python**.
2. Abra o arquivo baixado.
3. ⚠️ **Antes de clicar em instalar**, marque a caixinha **"Add python.exe to PATH"** lá embaixo.
   Isso é o erro mais comum de todos: se esquecer, nada funciona.
4. Clique em **Install Now** e espere terminar. Clique em **Close**.

**Confira:** feche e abra o PowerShell de novo e digite:
```
python --version
```
✅ Deve aparecer algo como `Python 3.13.1`.
❌ Se abrir a Microsoft Store ou aparecer "não é reconhecido": desinstale o Python e repita o passo 1,
desta vez marcando a caixinha do item 3.

---

### Passo 2: instalar o Git

1. Entre em **https://git-scm.com/download/win** e baixe o instalador (**64-bit Git for Windows Setup**).
2. Abra o arquivo e vá clicando em **Next** em todas as telas, sem mudar nada. No fim, **Install** e **Finish**.

**Confira:** feche e abra o PowerShell de novo e digite:
```
git --version
```
✅ Deve aparecer algo como `git version 2.47.0.windows.1`.

---

### Passo 3: instalar o Claude Code

No PowerShell, cole e aperte Enter:
```
irm https://claude.ai/install.ps1 | iex
```
Espere terminar. Depois **feche e abra o PowerShell de novo** e digite:
```
claude
```
Na primeira vez ele abre o navegador para você **entrar na sua conta do Claude**. Entre, autorize e volte
para o PowerShell. Ele pode fazer algumas perguntas de configuração (tema, etc.): aperte **Enter** para
aceitar o padrão.

✅ Quando aparecer uma caixa para digitar mensagens, está funcionando.
Para sair do Claude Code, digite `/exit` e aperte Enter (ou aperte Ctrl+C duas vezes).

---

### Passo 4: baixar este projeto

No PowerShell (fora do Claude, com o `PS C:\...>` aparecendo), cole **uma linha de cada vez**:
```
cd $HOME\Documents
```
```
git clone -b ccr-60cf32d0-p6a8cl https://github.com/HyCadu/Aprendizado
```
```
cd Aprendizado
```
✅ Agora o começo da linha deve mostrar `...\Documents\Aprendizado>`.
Se o GitHub pedir login, entre com a sua conta do GitHub na janela que abrir.

> O projeto fica em **Documentos\Aprendizado**. Nas próximas vezes, para entrar nele, é só abrir o
> PowerShell e digitar `cd $HOME\Documents\Aprendizado`.

---

### Passo 5: instalar a skill de cortes

Ainda dentro da pasta `Aprendizado`, cole:
```
powershell -ExecutionPolicy Bypass -File clipper-gta-br\instalar.ps1
```
✅ No final deve aparecer **"Patch pt-BR aplicado."** e
**"Pronto. Agora abra o Claude Code e digite: configura o clipper"**.

---

### Passo 6: configurar (só uma vez)

Ainda dentro da pasta `Aprendizado`, abra o Claude Code:
```
claude
```
Na caixa de mensagem, digite e aperte Enter:
```
configura o clipper
```
O Claude vai instalar sozinho o que falta (ffmpeg, yt-dlp, o programa que transforma fala em texto).
**Isso demora de 5 a 15 minutos.** Não feche a janela.

**O Claude vai pedir permissão várias vezes** ("Do you want to proceed?" / "Quer continuar?").
Isso é normal: ele pede antes de rodar qualquer coisa no seu computador. Escolha **Yes** (Sim).
Se aparecer a opção "Yes, and don't ask again" para comandos `python`, pode escolher essa para ele parar de perguntar.

✅ No final ele mostra uma tabela com `[OK]` e a palavra **READY**.
❌ Se aparecer **NOT READY** com linhas `[--]`, escreva para ele: `conserta o que faltou e roda de novo`.

---

### Passo 7: conferir a lista de streamers (só para cortes de lives)

Se você só vai cortar vídeos do YouTube passando o link, pule este passo.

Ainda no Claude Code, digite:
```
roda python -I clipper-gta-br/novas_lives.py --verificar
```
✅ Cada streamer aparece com `[OK]`.
❌ Se algum aparecer com `[--]`, peça: `corrige o link desse streamer no streamers.json`.

---

### Passo 8: fazer cortes

Abra o PowerShell, entre na pasta e abra o Claude:
```
cd $HOME\Documents\Aprendizado
```
```
claude
```
Agora escolha **um** dos comandos abaixo e digite na caixa do Claude:

| Quero... | Digite |
|---|---|
| Cortar **um vídeo do YouTube** (até 60 min) | `/cortes-youtube https://www.youtube.com/watch?v=XXXX` |
| Cortar um vídeo com **menos clipes** | `/cortes-youtube https://www.youtube.com/watch?v=XXXX --top 3` |
| Cortar **uma live** que já terminou | `/clipar-gta-br https://www.twitch.tv/videos/XXXX` |
| Cortar **as lives novas** dos streamers da lista | `/clipar-gta-br` |

(Troque o `https://...XXXX` pelo link de verdade. No YouTube é o endereço que aparece no navegador
quando você abre o vídeo.)

Depois é só esperar e **dizer Yes** quando ele pedir permissão. Quanto tempo leva:

| | Com placa NVIDIA | Sem placa NVIDIA |
|---|---|---|
| Vídeo de 20 min | ~3 min | ~10 a 15 min |
| Vídeo de 60 min | ~5 min | ~20 a 30 min |
| Live de 4 horas | ~10 a 15 min | ~1 a 2,5 horas |

✅ No final o Claude mostra a lista dos clipes, com a nota de cada um.

---

### Passo 9: pegar os vídeos prontos

1. Aperte **Windows + R**.
2. Digite um destes e aperte Enter:
   - Vídeos do YouTube: `%USERPROFILE%\CortesYouTube`
   - Lives: `%USERPROFILE%\StreamClipper`
3. Abra a pasta com o nome do canal e depois a pasta **clips**.

Em cada clipe você encontra:
- o **vídeo** `.mp4`, pronto para postar;
- o **post.md**, com título, descrição e hashtags para YouTube Shorts, TikTok, Instagram e X
  (abra com o Bloco de Notas e copie e cole).

⚠️ **Assista cada clipe antes de postar.** E só poste cortes de quem permite cortes, dando crédito.

---

### Passo 10 (opcional): deixar automático todo dia

Só faça isso depois que o Passo 8 já funcionou pelo menos uma vez.

Abra o PowerShell e cole (é uma linha só, longa):
```
schtasks /Create /SC DAILY /ST 04:17 /TN "Cortes GTA" /TR "powershell -ExecutionPolicy Bypass -File $HOME\Documents\Aprendizado\clipper-gta-br\rodar_automatico.ps1"
```
Todo dia às 4h17 ele corta as lives novas sozinho, se o computador estiver ligado. O que aconteceu fica
anotado em `%USERPROFILE%\StreamClipper\logs`. Para desligar:
`schtasks /Delete /TN "Cortes GTA" /F`

Para vídeos do YouTube, primeiro coloque os canais em `cortes-youtube\canais.json` (peça ao Claude:
`adiciona o canal https://www.youtube.com/@NOME no canais.json e ativa`) e depois use o mesmo comando
trocando `clipper-gta-br` por `cortes-youtube` e `"Cortes GTA"` por `"Cortes YouTube"`.

---

## Passo a passo no Mac

Use o app **Terminal** (aperte Cmd+Espaço, digite *Terminal*, Enter) no lugar do PowerShell.

1. **Ferramentas básicas (inclui o Git):** cole `xcode-select --install` e clique em **Instalar** na janela que abrir.
2. **Homebrew** (usado para instalar o ffmpeg): cole o comando que está em **https://brew.sh** e siga
   o que ele pedir (vai pedir a senha do Mac; as letras não aparecem enquanto você digita, é normal).
3. **Python:** baixe em **https://www.python.org/downloads/** e instale clicando em Continuar.
   Confira com `python3 --version`.
4. **Claude Code:** cole `curl -fsSL https://claude.ai/install.sh | bash`, feche e abra o Terminal, digite
   `claude` e entre na sua conta.
5. **Baixar o projeto**, uma linha de cada vez:
   ```
   cd ~/Documents
   git clone -b ccr-60cf32d0-p6a8cl https://github.com/HyCadu/Aprendizado
   cd Aprendizado
   ```
6. **Instalar a skill:** `bash clipper-gta-br/instalar.sh`
7. A partir daqui é igual ao Windows: [Passo 6](#passo-6-configurar-só-uma-vez) em diante.
   Os clipes ficam em `~/CortesYouTube` e `~/StreamClipper`. No Finder: menu **Ir > Ir para a pasta…** e cole o caminho.
   Para deixar automático no Mac, peça ao Claude: `agenda o rodar_automatico.sh no cron todo dia às 4h17`.

---

## Deu problema?

| O que apareceu | O que fazer |
|---|---|
| `python` "não é reconhecido" ou abre a Microsoft Store | Reinstale o Python marcando **"Add python.exe to PATH"** (Passo 1). Depois feche e abra o PowerShell. |
| `git` ou `claude` "não é reconhecido" | Feche e abra o PowerShell. Se continuar, repita o passo de instalação desse programa. |
| "a execução de scripts foi desabilitada neste sistema" | Você esqueceu o começo `powershell -ExecutionPolicy Bypass -File` do comando. Copie o comando inteiro de novo. |
| `fatal: destination path 'Aprendizado' already exists` | O projeto já foi baixado antes. Só digite `cd Aprendizado` e siga. |
| O Claude diz que **não conhece** `/cortes-youtube` ou `/clipar-gta-br` | Você abriu o Claude fora da pasta. Saia (`/exit`), digite `cd $HOME\Documents\Aprendizado` e abra `claude` de novo. |
| **"YouTube asks to sign in"** / "confirm you're not a bot" | Entre na sua conta do YouTube no **Firefox** e diga ao Claude: `usa meus cookies do Firefox`. Ou espere 1 hora e tente de novo. |
| "O vídeo tem 1 h 10 min: esta skill é para vídeos de até 60 min" | Para vídeo longo, use `/clipar-gta-br LINK` (feito para lives longas). |
| "This stream is still live" | A live ainda está acontecendo. Espere acabar e o vídeo (VOD) aparecer no canal. |
| Muito lento | Normal sem placa NVIDIA. Deixe rodando; não feche a janela. |
| O rosto do streamer saiu cortado no clipe | Diga ao Claude: `o rosto ficou errado no clipe 2, arruma`. |
| O Passo 10 dá erro (comum se o seu nome de usuário do Windows tem espaço) | Abra o Claude na pasta do projeto e peça: `cria a tarefa agendada diária do rodar_automatico.ps1 pra mim`. |
| Qualquer outra mensagem de erro | Copie o erro e cole para o Claude com: `deu esse erro, resolve`. Ele consegue consertar a maioria sozinho. |

Ainda travado? Anote **em qual passo** parou e **o que apareceu na tela** (um print ajuda) e peça ajuda com isso.
