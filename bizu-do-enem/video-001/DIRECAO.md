# V001 — Você pode acertar mais e tirar nota menor?

**Status:** Etapa 2 (styleframes) aguardando aprovação. Nenhuma animação foi produzida.

## 1. Análise do roteiro

- **Mensagem central:** na TRI, a nota é uma *estimativa de proficiência*, não uma soma de pontos por acerto.
- **Gancho:** contraste "mais acertos ≠ nota maior". É contraintuitivo e dá para mostrar em menos de 2 s.
- **Risco pedagógico evitado:** nunca mostrar "X pontos por questão" como verdade. O único "+10 pts" que aparece está riscado. As notas são barras sem escala numérica, marcadas como "exemplo ilustrativo".
- **Validação do exemplo:** os padrões A (32 acertos) e B (30 acertos) foram testados num modelo logístico de 3 parâmetros (a família usada no ENEM). A estimativa de A ficou em θ ≈ −0,64 e a de B em θ ≈ +0,82. O exemplo é coerente.

## 2. Conceito visual: "o item é o protagonista"

Cada questão é um **token** (círculo roxo ✓ / contorno ✕). O mesmo conjunto de tokens atravessa o vídeo inteiro e se transforma:
folha de respostas → etiquetas de pontos que quebram → fila ordenada por dificuldade → um token vira o cartão do Item 37 (curva característica) → as curvas viram distribuições de proficiência → CTA.
Esse objeto contínuo é o que tira o vídeo da estética de slides: não há "troca de tela", há **transformação de um mesmo objeto**.

- Base azul-marinho com luz roxa volumétrica, grade técnica sutil, grão e vinheta.
- O amarelo #FFC400 aparece só em ênfase: a palavra-chave, a resposta certa e o estudante B.
- Tipografia: Inter Display Black/ExtraBold para os títulos, Inter para o texto e JetBrains Mono para rótulos técnicos (tom de "dado").
- Profundidade em 2.5D: cartões em perspectiva, sombras longas, plano de tokens inclinado no gancho.

## 3. Sequência de cenas (tempos estimados; o áudio final define)

| # | Narração | Tempo | Intenção visual | Movimento previsto | Transição para a próxima |
|---|---|---|---|---|---|
| 01 | "Você sabia que acertar mais questões nem sempre significa tirar nota maior?" | 0–4 s | Choque tipográfico | Plano de tokens sobe em perspectiva; "Mais acertos" entra por máscara; o "≠" cai com overshoot no "nem sempre"; "maior?" fica amarelo no fim da frase | Os tokens do chão sobem e se organizam nas duas folhas |
| 02 | (continuação / respiro) | 4–7 s | O paradoxo concreto | Contadores 32 e 30 sobem rolando; barras de nota crescem; a de B passa a de A (inversão) | As folhas colapsam em 8 tokens |
| 03 | "A TRI não transforma cada acerto em uma quantidade fixa de pontos." | 7–11 s | Desmontar o modelo mental errado | Etiquetas "+10 pts" se prendem aos tokens; o traço amarelo corta "pontos fixos" exatamente em "fixa de pontos"; etiquetas caem e se desfazem | Os tokens se alinham num eixo |
| 04 | "Ela estima proficiência considerando o padrão de respostas…" | 11–14 s | Coerência do padrão | O eixo fácil→difícil se desenha; tokens se ordenam com stagger; anéis amarelos marcam os erros fáceis e os acertos difíceis de A | Câmera mergulha no token 37 |
| 05 | "…e as características dos itens." | 14–17 s | O item tem perfil | O token expande e vira o cartão; a curva se desenha (stroke); b, a e c acendem em sequência com as pílulas | A curva se achata e vira as distribuições |
| 06 | (fecho da frase / respiro) | 17–19 s | Resultado = estimativa | A curva de A abre larga (incerta), a de B estreita e mais à direita; marcadores A e B pousam | Card sai pela esquerda; luz roxa varre a tela |
| 07 | "O segredo é entender a ideia e aplicá-la na questão, não decorar uma frase solta." | 19–24 s | Do conceito à prática | "Entenda." / "Aplique." batem nas palavras; a seta leva a ideia até a questão; a alternativa C acende; a frase decorada desfoca e é riscada em "não decorar" | A questão se fecha num livro (o guia) |
| 08 | "Quando o material estiver disponível, confira o guia gratuito no link da bio." | 24–28 s | CTA com marca | O guia gira em 3D até a pose final; pílula "Link na bio" pulsa uma vez; assinatura de marca | Fim (loop limpo para o 01) |

## 4. Pontos para o editorial / aprovação

1. **Título do guia ("TRI sem mistério") é provisório.** Preciso do nome real ou de autorização para manter.
2. **Logo:** o "B!" e a assinatura são provisórios até receber a marca oficial.
3. **Frase 4 do roteiro** ("O segredo é entender a ideia…") é genérica para o tema TRI. Visualmente, conecto com a prática "acertar as questões que você domina com atenção". Sugiro ao editorial considerar um bizu mais específico; não alterei o texto.
4. **Duração:** ~28 s estimados para cerca de 65 palavras. Será ajustada ao áudio real.

## 5. Técnica de produção (Etapa 4)

Composição em HTML/SVG com camadas independentes, animadas com GSAP (timeline controlada por tempo). Render quadro a quadro em Chromium headless a 1080×1920 / 30 fps e montagem em ffmpeg (H.264 + AAC). Os tempos vêm do alinhamento palavra a palavra da narração.
