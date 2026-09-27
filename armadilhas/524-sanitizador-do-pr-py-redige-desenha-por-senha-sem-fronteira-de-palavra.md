---
schema_version: 2
armadilha: 524
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: nenhum
  motivo: consertar a regex exige decidir a fronteira certa para todas as palavras da lista (password, senha, token...) sem quebrar a deteccao real de segredo; e mudanca de codigo em ci/pr.py, nao guarda automatico desta entrada.
sinal:
  - "desenha: <REDIGIDO>"
gatilho:
  - ci/pr.py
licao: "O sanitizador de segredos de ci/pr.py usa (?:password|senha|token|...)\\s*[:=] sem \\b antes da alternativa: qualquer palavra terminada em -senha seguida de dois-pontos (como desenha:) casa a alternativa senha e tem o conteudo apos os dois-pontos trocado por <REDIGIDO>. Evite a palavra desenha: (ou qualquer -senha:, -token:, -secret:) em corpo de PR ate a regex ganhar \\b."
---

# 524: Sanitizador de segredos do `ci/pr.py` redige "desenha:" por falta de fronteira de palavra

## Sintoma

Um corpo de PR com o trecho `desenha: headline` (uma instrução de layout,
sem segredo nenhum) foi publicado como `desenha: <REDIGIDO>`, apagando o
valor real depois do texto de dois-pontos.

## Causa

`ci/pr.py::_sanitizar` usa a regex

```python
r"""(?i)((?:\\?["'])?(?:password|senha|token|access_token|secret|api_key|authorization)(?:\\?["'])?\s*[:=]\s*)..."""
```

sem `\b` antes da alternativa. A engine de regex tenta casar a partir de
qualquer posição da string, então em `desenha:` ela encontra `senha:` a
partir da terceira letra e substitui esse trecho (e o valor seguinte) por
`<REDIGIDO>`, sem que a palavra completa (`desenha`) tenha relação nenhuma
com senha de verdade.

## Solução

Até a regra ganhar `\b` antes da alternativa em `ci/pr.py`, evite escrever
`desenha:` (ou qualquer palavra terminada em `-senha:`, `-token:`,
`-secret:`) em corpo, mensagem ou detalhe de PR: reformule a frase (por
exemplo, "o layout do headline" em vez de "desenha: headline") para não
disparar a redação indevida.

## Evidência

Sistema de experimentos, 26 e 27/09/2026, relatado pela sessão que fechou o
sistema de experimentos, confirmado contra `ci/pr.py::_sanitizar` (linha da
regex sem `\b`).
