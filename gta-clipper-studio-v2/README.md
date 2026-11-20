# GTA CLIPPER STUDIO

Programa para Windows (janela própria, feito em Python + PySide6) que faz pela interface o que o
`/cortes-youtube` e o `/clipar-gta-br` fazem no terminal.

Funciona com a mesma instalação do projeto. Se você já cortou um vídeo pelo Claude seguindo o
[README principal](../README.md), não precisa instalar mais nada.

## Abrir

Dê dois cliques em **`GTA Clipper Studio.exe`** (nesta pasta). Se o `.exe` ainda não existir, use
**`Abrir GTA Clipper Studio.bat`**: na primeira vez ele instala as dependências listadas em `requirements.txt`.

### Gerar o executável

```
python -m pip install -r gta-clipper-studio-v2\requirements.txt pyinstaller
python gta-clipper-studio-v2\build_exe.py
```
Isso cria `gta-clipper-studio-v2\GTA Clipper Studio.exe`, um arquivo só (~60 MB), sem janela de console. Ele fica
fora do git. Rode de novo sempre que atualizar o projeto.
O `.exe` precisa continuar **dentro da pasta do projeto**, porque usa as skills de `.claude\skills`. Para
abrir de outro lugar, use o atalho (abaixo) em vez de mover o arquivo. O processamento continua usando o
Python e o Claude Code instalados no computador.

Para ter um atalho na Área de Trabalho, rode isto uma vez no PowerShell, na pasta `Aprendizado`:
```
powershell -ExecutionPolicy Bypass -File gta-clipper-studio-v2\criar_atalho.ps1
```

Pelo terminal também funciona: `python gta-clipper-studio-v2\main.py`.

## Telas

| Tela | O que faz |
|---|---|
| **Dashboard** | Total de cortes, vídeos processados, últimos 7 dias, status do sistema (Claude, skills, GPU, transcrição, FFmpeg), últimos processamentos e cortes recentes. |
| **Novo corte** | Cole o link, escolha **YouTube** (até 5 cortes) ou **Twitch** (até 3) e clique em **INICIAR PROCESSAMENTO**. |
| **Processamento** | Barra de progresso, etapas, logs em tempo real, tempo decorrido e botão **CANCELAR**. No fim, mostra a resposta do Claude com os caminhos dos clipes. |
| **Biblioteca** | Todos os `.mp4` gerados, com miniatura, nota, duração e a sincronia da legenda. Busca, filtro, player embutido, texto do post (com botão de copiar) e botão para abrir a pasta. Com um canal conectado, abre a revisão de metadados antes do envio ao YouTube. |
| **Integrações** | Conecta o YouTube por OAuth oficial, mostra os dados reais do canal e mantém o histórico local de envios e agendamentos. |
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

- **A geração não publica automaticamente.** Um envio ao YouTube só começa após a revisão dos metadados e uma confirmação explícita na tela individual do clipe.
- **Nada é apagado.** Cancelar encerra os processos, e o que já foi baixado ou transcrito continua na
  pasta do job. A biblioteca só lê os arquivos.
- O link precisa ser um vídeo do YouTube ou um VOD da Twitch, sem espaços nem símbolos. Assim, nenhum
  texto extra entra no comando.
- Tokens, senhas e chaves aparecem como `••••••` nos logs da tela e no arquivo de log.
- Logs, histórico e configurações do app ficam em `%APPDATA%\GTAClipperStudioV2`.
- O token OAuth e o arquivo de configuração do cliente ficam no cofre de credenciais do Windows via `keyring`; não são gravados no repositório nem dentro do executável.
- A integração só publica após a confirmação no diálogo de revisão. O modo inicial de visibilidade é **Privado**.

## Configurar publicação no YouTube

1. No [Google Cloud Console](https://console.cloud.google.com/), selecione ou crie o projeto **GTA Clipper Studio** e habilite **YouTube Data API v3** em APIs e serviços.
2. Abra **Google Auth Platform** e configure a tela de consentimento OAuth. Para uma conta pessoal, escolha o tipo de usuário apropriado; se o app estiver em modo de teste, adicione sua conta como usuário de teste. O Google pode exigir uma nova autorização quando o projeto externo estiver em teste.
3. Em **Data Access / Acesso aos dados**, inclua os escopos `https://www.googleapis.com/auth/youtube.upload` e `https://www.googleapis.com/auth/youtube.readonly`.
4. Em **Clients / Clientes**, crie um OAuth client ID do tipo **Desktop app / Aplicativo para computador** e baixe o JSON. Não crie um cliente Web nem configure callback OOB.
5. Instale as dependências atualizadas na pasta do projeto:

   ```powershell
   python -m pip install -r gta-clipper-studio-v2\requirements.txt
   ```

6. Abra o GTA Clipper Studio, entre em **Integrações**, importe o JSON baixado e escolha **Conectar conta**. O navegador padrão abre a autorização Google; após aceitar, o app valida o retorno em uma porta loopback temporária e consulta `channels.list` para mostrar o canal real.
7. Para criar o executável com suporte à publicação, gere novamente o app depois de instalar as dependências:

   ```powershell
   python gta-clipper-studio-v2\build_exe.py
   ```

O JSON importado e o token são mantidos fora do executável. O projeto usa `videos.insert` com upload retomável e `status.publishAt` para agendamentos; o vídeo é enviado imediatamente e permanece privado até o horário informado. A classificação final de Shorts é feita pelo próprio YouTube. A aplicação apenas indica se proporção vertical/quadrada e duração de até três minutos atendem ao critério de formato descrito na [ajuda oficial sobre Shorts de até três minutos](https://support.google.com/youtube/answer/15424877).

Um primeiro envio **Privado** é recomendado para conferir o processo e as permissões do canal. Não foram incluídos segredos nem executado upload real nos testes automatizados. Para os detalhes atuais de OAuth desktop, campos de vídeo, canal, upload e cotas, consulte a [documentação OAuth para apps desktop](https://developers.google.com/identity/protocols/oauth2/native-app), [videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert), [videos](https://developers.google.com/youtube/v3/docs/videos), [channels.list](https://developers.google.com/youtube/v3/docs/channels/list), [upload retomável](https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol) e [auditorias de cota e conformidade](https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits). Consulte a cota vigente no projeto Google Cloud, pois ela pode variar conforme o projeto e as políticas atuais.

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
