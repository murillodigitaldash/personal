# V002 — 3 erros que podem custar pontos no ENEM

**Status:** Etapa 2 (styleframes) aguardando aprovação. Nenhuma animação foi produzida.

## 1. Análise do roteiro

> Três erros podem custar pontos no ENEM. Leia o comando até o fim, não gaste todo o tempo numa questão e só mude uma resposta se houver motivo concreto. Na prática, confira o enunciado e justifique sua escolha antes de marcar. Salva esse bizu e segue o Bizu do Enem para aprender mais.

- **Mensagem central:** três hábitos de prova (ler o comando inteiro, distribuir o tempo, só trocar resposta com motivo) e uma rotina prática (conferir e justificar antes de marcar).
- **Inconsistência do briefing:** o "roteiro geral" cita "abertura sobre inglês: cognatos", o que não aparece no título, na legenda nem na narração. Tratei como resto de modelo do agente editorial e não incluí. Se cognatos devem entrar, precisa de nova narração.
- **Precisão:** sem tempos oficiais de prova (variam por edição), sem promessa de pontuação. "Travou? Pule e volte depois." foi preferido a "marque", que poderia soar como incentivo ao chute.
- **Voz:** Vinicius Messer (`eleven_multilingual_v2`), take 1 de 2. As duas transcrições automáticas conferiram palavra por palavra. A take 1 tem 16,9 s.

## 2. Conceito visual: "stepper" dos três erros

Mesmo universo do V001 (tokens de item, cards de vidro, tipografia cinética, roxo/amarelo sobre azul-marinho), sem repetir as cenas dele.
- Os três erros são falados numa só frase. Por isso não viram três cenas soltas: são **um indicador de etapas (01 Comando → 02 Tempo → 03 Troca)** que avança no ritmo da fala. Cada etapa concluída vira ✓ e o indicador termina como resumo.
- Cada erro tem um visual que explica o conceito:
  1. **Comando:** um marca-texto percorre o enunciado e revela "INCORRETO" no fim.
  2. **Tempo:** uma questão travada consome a barra de tempo, e as demais ficam esperando.
  3. **Troca:** a alternativa C quer virar D, mas passa pelo filtro "Motivo concreto?".
- **Na prática:** checklist (enunciado ✓, justificativa ✓) e só então a bolha é marcada.
- **CTA:** salvar + seguir, com a marca.

## 3. Pausas propostas (só silêncio entre frases; voz e texto inalterados)

| Depois de | Pausa | Motivo |
|---|---|---|
| "…pontos no ENEM." | +0,5 s | o "3" do gancho assenta |
| "…até o fim," | +1,0 s | ler o enunciado destacado |
| "…numa questão" | +1,0 s | ver a barra de tempo ser consumida |
| "…motivo concreto." | +0,6 s | resolver o filtro "manter/trocar" |

Duração estimada: cerca de 21 s.

## 4. Sequência de cenas (tempos com as pausas)

| # | Narração | Tempo | Movimento previsto |
|---|---|---|---|
| 01 | "Três erros podem custar pontos no ENEM." | 0–2,8 s | O "3" bate com overshoot em "Três"; três tokens ✕ caem em cascata; "pontos" acende em amarelo; chão de tokens em perspectiva |
| 02 | "Leia o comando até o fim," | 2,8–5,4 s | O "3" encolhe e vira o indicador de etapas; o marca-texto percorre o enunciado em "comando"; "INCORRETO" acende em "fim" |
| 03 | "não gaste todo o tempo numa questão" | 5,4–8,4 s | A etapa 01 vira ✓; a questão 03 trava, o anel de relógio gira e a barra listrada consome o tempo; as demais esmaecem |
| 04 | "e só mude uma resposta se houver motivo concreto." | 8,4–11,3 s | A seta tracejada C→D se desenha; o card "Motivo concreto?" surge; a seleção hesita e volta para C ("Não → mantém" acende) |
| 05 | "Na prática, confira o enunciado e justifique sua escolha antes de marcar." | 11,3–14,7 s | "Confira." / "Justifique." / "Marque." batem nas palavras; os dois ✓ do checklist entram; a bolha C é preenchida em "marcar" |
| 06 | "Salva esse bizu e segue o Bizu do Enem para aprender mais." | 14,7–21 s | O card "Salva" entra e o ícone pulsa em "Salva"; o card da marca entra em "segue", com "Seguir" pulsando |

## 5. Técnica

Mesmo pipeline do V001: composição GSAP em camadas, render com motion blur (3 subquadros), mixagem em −14 LUFS e entrega em H.264 1080×1920 / 30 fps + `.srt`.
