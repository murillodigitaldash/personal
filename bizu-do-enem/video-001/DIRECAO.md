# V001 — Você pode acertar mais e tirar nota menor?

**Status:** entregue para aprovação final. Arquivos em `entrega/`.

## 1. Roteiro final (narração)

> Você sabia que acertar mais questões nem sempre significa tirar nota maior? A TRI não transforma cada acerto em uma quantidade fixa de pontos. Ela estima proficiência considerando o padrão de respostas e as características dos itens. **O bizu: comece pelas questões que você domina e não deixe as fáceis escaparem por desatenção. Elas dão coerência ao seu padrão de respostas.** Quando o material estiver disponível, confira o guia gratuito no link da bio.

- O trecho em negrito substitui "O segredo é entender a ideia e aplicá-la na questão, não decorar uma frase solta". A troca foi autorizada pelo usuário em 26/10/2026.
- **Precisão:** no modelo de TRI do ENEM, acertar itens fáceis (em vez de errá-los) eleva a estimativa de proficiência. Erros em itens fáceis combinados com acertos em difíceis formam um padrão pouco provável. O bizu não promete pontuação.
- **Voz:** Vinicius Messer (ElevenLabs, `eleven_multilingual_v2`), take 1 de 2. As duas transcrições automáticas conferiram palavra por palavra.
- **Edição:** pausas de +1,2 s depois de "nota maior?" e de +1,0 s depois de "características dos itens", só no silêncio entre frases. Voz e texto não foram alterados.

## 2. Conceito visual: "o item é o protagonista"

Cada questão é um token (círculo roxo ✓ / contorno ✕). O mesmo objeto se transforma ao longo do vídeo: chão de tokens → folhas de resposta → tokens com etiquetas "+10 pts" que caem → fila ordenada por dificuldade → um token vira o cartão do Item 37 → prova com 15 questões → curvas de estimativa → guia.

## 3. Plano de motion (Etapa 3): tempos no áudio editado

| # | Tempo | Âncora na fala | Entrada | Durante | Saída / transição |
|---|---|---|---|---|---|
| 01 Gancho | 0,0–4,1 | "acertar mais" 0,69 · "nem sempre" 1,75 · "nota maior?" 3,0 | Chão de tokens sobe em perspectiva (expo.out); "Mais acertos" por máscara | "≠" cai com back.out em "nem sempre"; "maior?" fica amarelo com um pulso | O chão decola para cima (power3.in) e o tipo sai por máscara; whoosh |
| 02 Paradoxo | 3,95–6,8 | "A TRI" 5,3 | Cards A/B sobem com rotação X; 45 tokens surgem em ordem aleatória | Contadores 0→32 e 0→30; barras crescem e B ultrapassa A; chip "TRI = Teoria de Resposta ao Item" em "TRI" | Cards recuam com fade; varredura de luz |
| 03 A regra | 6,5–10,6 | "não" 6,5 · "cada acerto" 7,3 · "fixa" 8,8 · "pontos" 9,3 | 8 tokens caem de cima e encaixam na grade 3D | Etiquetas "+10 pts" se prendem; o traço amarelo corta "pontos fixos" em "fixa"; as etiquetas são riscadas e caem em "pontos" | A grade se achata e os 8 tokens pousam exatamente na linha B da cena 04 (troca invisível) |
| 04 Padrão | 10,3–13,9 | "estima proficiência" 10,1 · "padrão" 12,4 · "respostas" 12,8 | Eixo fácil→difícil se desenha; linhas completam | "Proficiência" rola para "Padrão de respostas"; rótulos COERENTE/INCOERENTE; anéis amarelos nas anomalias de A (ticks) | O card some e o último token de A cresce e vira o card do item |
| 05 Item | 13,75–16,6 | "características" 13,9 · "itens" 14,8 | Card emerge do token (escala + raio de borda) | Curva se desenha (stroke); c → b → a acendem; pílulas entram em sequência | Card tomba em X com fade; varredura |
| 06 O bizu | 16,6–22,0 | "comece" 17,3 · "domina" 17,7 · "fáceis" 19,9 · "escaparem" 20,3 · "desatenção" 21,05 | Prova com 15 questões sobe | As questões dominadas são marcadas em sequência; o título rola para "Não deixe as fáceis escaparem."; a questão fácil 06 escapa (desfoque/deriva); em "desatenção" o anel amarelo a captura de volta | Card recua; pílula "Atenção nas fáceis" sai |
| 07 Estimativa | 22,05–24,4 | "coerência" 22,5 · "padrão de respostas" 23,2 | Curva cinza "errando fáceis" se desenha | A curva amarela "garantindo as fáceis" surge mais estreita e à direita; "Uma estimativa, não uma soma." | Card sai pela esquerda; varredura |
| 08 CTA | 24,4–29,6 | "disponível" 25,4 · "gratuito" 26,8 · "link" 27,4 · "bio" 27,7 | O guia gira em 3D até a pose final | "gratuito" acende em amarelo; "Link na bio" surge (chime) e pulsa em "bio"; a assinatura pulsa | Respiro final de 1,4 s |

Contínuos: dolly global de 3,5 % ao longo do vídeo, luzes de fundo derivando, grão animado a 24 qps, capítulos rolando no canto (01–08).

## 4. Técnica

- Composição em HTML/SVG com camadas independentes, numa timeline GSAP (`motion/video.html`) que segue os tempos de cada palavra.
- Render em Chromium headless, 1080×1920. **Motion blur real:** 3 subquadros por quadro (obturador de 180°) com média no ffmpeg (`tools/render.js`).
- Áudio: voz com compressão leve, efeitos sonoros sintetizados (whoosh, pop, tick, swipe, chime) entre −13 e −20 dB, loudness em −14 LUFS e true peak em −1,5 dBTP.
- Entrega: H.264 High, yuv420p, BT.709, 30 fps, AAC 48 kHz e `entrega/BizuDoEnem_V001.srt`.

## 5. Pendências

- Guia "TRI sem mistério": título sugerido, aguardando confirmação.
- Marca: a proposta v1 foi aplicada (pasta `marca/`); continua provisória até aprovação.
- Trilha musical: não usada. O conector ElevenLabs desta conta não gera música, e a narração e os efeitos sonoros sustentam o ritmo.
