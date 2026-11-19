# GTA CLIPPER STUDIO

Programa para Windows (janela própria, feito em Python + PySide6) que faz pela interface o que o
`/cortes-youtube` e o `/clipar-gta-br` fazem no terminal.

Funciona com a mesma instalação do projeto. Se você já cortou um vídeo pelo Claude seguindo o
[README principal](../README.md), não precisa instalar mais nada.

## Abrir

Dê dois cliques em **`GTA Clipper Studio.exe`** (nesta pasta). Se o `.exe` ainda não existir, use
**`Abrir GTA Clipper Studio.bat`**: na primeira vez ele instala o PySide6 sozinho (~1 min).

### Gerar o executável

```
python -m pip install pyinstaller PySide6
python gta-clipper-studio\build_exe.py
```
Isso cria `gta-clipper-studio\GTA Clipper Studio.exe`, um arquivo só (~60 MB), sem janela de console. Ele fica
fora do git. Rode de novo sempre que atualizar o projeto.
O `.exe` precisa continuar **dentro da pasta do projeto**, porque usa as skills de `.claude\skills`. Para
abrir de outro lugar, use o atalho (abaixo) em vez de mover o arquivo. O processamento continua usando o
Python e o Claude Code instalados no computador.

Para ter um atalho na Área de Trabalho, rode isto uma vez no PowerShell, na pasta `Aprendizado`:
```
powershell -ExecutionPolicy Bypass -File gta-clipper-studio\criar_atalho.ps1
```

Pelo terminal também funciona: `python gta-clipper-studio\main.py`.

## Telas

| Tela | O que faz |
|---|---|
| **Dashboard** | Total de cortes, vídeos processados, últimos 7 dias, status do sistema (Claude, skills, GPU, transcrição, FFmpeg), últimos processamentos e cortes recentes. |
| **Novo corte** | Cole o link, escolha **YouTube** (até 5 cortes) ou **Twitch** (até 3) e clique em **INICIAR PROCESSAMENTO**. |
| **Processamento** | Barra de progresso, etapas, logs em tempo real, tempo decorrido e botão **CANCELAR**. No fim, mostra a resposta do Claude com os caminhos dos clipes. |
| **Biblioteca** | Todos os `.mp4` gerados, com miniatura, nota, duração e a sincronia da legenda. Busca, filtro, player embutido, texto do post (com botão de copiar) e botão para abrir a pasta. |
| **Configurações** | Pastas de saída, caminho do Claude Code, verificação das dependências e informações da placa de vídeo (atualizadas a cada 4 s). |

## Como funciona por dentro

O app **não refaz o processamento**. Ele roda o mesmo comando dos `rodar_automatico.ps1`, em outro
processo (a janela não trava):

```
claude -p "/cortes-youtube LINK --top N"              (YouTube)
claude -p "/clipar-gta-br LINK (só N cortes por live)" (Twitch)
```

As permissões também são as mesmas: só `python`, `Read`, `Write` e `Glob`. Nenhuma ferramenta que
publique alguma coisa fica liberada. O app só acrescenta `--output-format stream-json` para ler cada
passo e mostrar os logs e as etapas na hora.

| Arquivo | Para quê |
|---|---|
| `studio/core.py` | Valida o link, monta o comando, lê os eventos do Claude, define a etapa e mascara credenciais |
| `studio/runner.py` | Processo separado, leitura dos logs e cancelamento (encerra o Claude e todos os scripts filhos) |
| `studio/storage.py` | Configurações, histórico e leitura das pastas de cortes (somente leitura) |
| `studio/system.py` | Verificação das dependências e da GPU (`nvidia-smi`). Só lê, não instala nada |
| `studio/pages/` | As telas |
| `tests/` | Testes: `python -m unittest discover -s tests` |

## Segurança

- **Nada é publicado.** Os clipes ficam só no seu computador.
- **Nada é apagado.** Cancelar encerra os processos, e o que já foi baixado ou transcrito continua na
  pasta do job. A biblioteca só lê os arquivos.
- O link precisa ser um vídeo do YouTube ou um VOD da Twitch, sem espaços nem símbolos. Assim, nenhum
  texto extra entra no comando.
- Tokens, senhas e chaves aparecem como `••••••` nos logs da tela e no arquivo de log.
- Logs, histórico e configurações do app ficam em `%APPDATA%\GTAClipperStudio`.

## Detalhe do Windows: `python` e a Microsoft Store

Em algumas máquinas, o comando `python` abre o atalho da Microsoft Store em vez do Python de verdade.
No modo sem interação, os scripts das skills falham com "Python was not found". O app resolve isso
sozinho: coloca a pasta do Python instalado na frente do PATH, só no processo do corte. Ele não muda nada
no sistema. A tela **Configurações** avisa quando isso acontece.

## Deu problema?

| O que aparece | O que fazer |
|---|---|
| "Claude Code não encontrado" | Instale o Claude Code (README principal, passo 3) ou indique o `claude.exe` em **Configurações**. |
| Dependência com **FALTA** | Abra o PowerShell na pasta `Aprendizado`, digite `claude` e peça `configura o clipper`. |
| O processamento termina com erro | Leia a resposta do Claude no fim da tela **Processamento** ou abra o log (ícone de documento). |
| O vídeo não toca no player embutido | Clique em **Player do Windows**. |
