# Sobre este clone

Baseado em [arcticloud/ai-stream-clipper](https://github.com/arcticloud/ai-stream-clipper), commit
`b3546b7e1ce3347dd253a627ccb9e25e5ae32f7a`, licença MIT (veja `LICENSE`, que deve ser mantido).

Mudanças em relação ao original:
- Português (pt-BR): o mesmo conteúdo do patch `clipper-gta-br/ai-stream-clipper-pt-br.patch`.
- Até 5 clipes por vídeo, em vez de 3 (`scripts/clipper.py`, `scripts/cl_moments.py`).
- Qualquer duração: até 60 min, trechos de 5 min e leitura completa; mais longo, trechos de 10 min e leitura
  econômica (~40%). `--smart` / `--read-all` forçam um ou outro.
- O idioma do áudio é sempre detectado, mesmo com `--lang` forçado, e o `prepare` avisa quando o palpite parece errado.
- `setup`: recusa o Python da Microsoft Store (explica e instala o do python.org), testa a leitura de áudio e
  instala `av<17` se o PyAV quebrar o faster-whisper, e baixa o modelo para `~/.ai-stream-clipper/models/<nome>`
  com download vigiado e plano B direto (curl). A transcrição carrega dessa pasta, sem rede.
  `cl_setup.py` e `cl_transcribe.py` também são idênticos nas duas skills (vão no patch da de lives).
- Saída em `~/CortesYouTube` (o original usa `~/StreamClipper`).
- Palavras-chave e hashtags pt-BR para gameplay de GTA editado.
- `SKILL.md` reescrito para vídeos editados (música, efeitos, cutscenes, vinhetas).
- Legenda em português ou inglês, traduzida nos dois sentidos: comando `translate --to pt|en` e `scripts/cl_translate.py`
  (também no patch da skill de lives; `cl_render.py`, `cl_captions.py` e `cl_translate.py` são idênticos nas duas).
