# Sobre este clone

Baseado em [arcticloud/ai-stream-clipper](https://github.com/arcticloud/ai-stream-clipper), commit
`b3546b7e1ce3347dd253a627ccb9e25e5ae32f7a`, licença MIT (veja `LICENSE`, que deve ser mantido).

Mudanças em relação ao original:
- Português (pt-BR): o mesmo conteúdo do patch `clipper-gta-br/ai-stream-clipper-pt-br.patch`.
- Até 5 clipes por vídeo, em vez de 3 (`scripts/clipper.py`, `scripts/cl_moments.py`).
- Recusa vídeos com mais de 60 min, a menos que se passe `--force-long`.
- Trechos de 5 min e leitura completa por padrão; `--smart` volta ao modo econômico.
- Saída em `~/CortesYouTube` (o original usa `~/StreamClipper`).
- Palavras-chave e hashtags pt-BR para gameplay de GTA editado.
- `SKILL.md` reescrito para vídeos editados (música, efeitos, cutscenes, vinhetas).
- Legenda traduzida para pt-BR em vídeo estrangeiro: comando `translate` e `scripts/cl_translate.py`
  (também no patch da skill de lives; `cl_render.py`, `cl_captions.py` e `cl_translate.py` são idênticos nas duas).
