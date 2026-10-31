# V014 — formato gancho 2.0 (primeiro teste)

**Status:** entregue (31/10/2026). MP4 enviado no chat; capa (quadro 0), `.srt` e texto do post em `entrega/`. QC: sem pretos/congelamentos/cortes secos. Roteiro: `roteiros/DIA-007-dicas.md` (aprovado em 31/10/2026).

- **Voz:** Vinicius Messer (`eleven_multilingual_v2`), take 1 de 2; transcrição conferida palavra por palavra.
- **Gancho 2.0:** o quadro 0 já tem o desafio escrito na tela, com impacto sonoro em 0 s. O selo "FALTAM 7 DIAS" e a legenda da fala ficam queimados na tela (`shared/hook2.js`). A cena de comentário vem antes do CTA, e o CTA fala do e-book no perfil.
- **Capa:** quadro 0, que já mostra o título completo.
- **Composição:** `motion/video.tpl.html`; o `video.html` final é gerado com `tools/build_tpl.py`, que insere as palavras da narração.
