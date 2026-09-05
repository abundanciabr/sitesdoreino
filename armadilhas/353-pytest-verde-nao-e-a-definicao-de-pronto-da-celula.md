---
schema_version: 2
armadilha: 353
estado: guardada
degrau: 12
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  dono: services/admin/Makefile
sinal:
  - "1132 testes, 0 falhas" seguido de PR reprovado em menos de 1 minuto
  - "black --check" ou "mypy" reprovando um PR que só rodou pytest antes de abrir
---

# Rodar pytest e chamar de suíte não é rodar a Definição de Pronto da célula

**Sintoma.** Você roda `pytest -q` na célula, lê `1132 passed`, abre o PR, e o
`ci-celula (admin)` reprova em segundos:

```
black --check .
would reformat apps/core/tests/test_laboratorio.py
Oh no! 1 file would be reformatted.
```

Aconteceu em 05/09/2026: o PR #1127 (o laboratório, degrau 12 do painel de
gestão) foi aberto com `pytest -q` verde e o `ci-celula (admin)` reprovou em
**29 segundos**, no `black --check`, antes mesmo de chegar ao `mypy` ou ao
`test`.

**Causa.** "A suíte passou" e "a célula está pronta" são frases diferentes, e
só a segunda é a régua real. Cada célula publica o que "pronto" significa ali
no próprio `Makefile` (`ci: lint type test contrato-check` ou equivalente), e
`lint` (formatação) e `type` (tipos) reprovam **sozinhos**, sem tocar um teste
sequer. `pytest -q` verde não cobre nenhum dos dois: ele mede só o terceiro dos
quatro passos que o portão vai cobrar. Rodar só ele e chamar de "a suíte" é
medir um quarto do que o CI mede, e descobrir o resto na pista.

**Solução.** Antes de abrir o PR, rode o alvo que a própria célula já publica:

```bash
cd services/<celula> && make ci
```

Isso roda `lint`, `type`, `test` e `contrato-check` (quando a célula tiver) na
mesma ordem do `ci-celula`, na mesma bancada. Um `black --check` ou `mypy` que
vai reprovar na pista reprova ali, em segundos, sem gastar uma rodada de CI
nem a espera do mantenedor.

**A régua, para a próxima vez:** o portão nunca deveria ser o primeiro a
descobrir o que o `Makefile` já dizia. "Rodei a suíte" só é verdade quando o
comando rodado foi `make ci`, não `pytest`.

**Por que já tem guarda:** o `ci-celula` do CI já roda os quatro passos em
todo PR e reprova sozinho, sem depender de ninguém lembrar. O que faltava não
é mecanismo novo, é rodar o mecanismo que já existe **antes** de abrir o PR,
em vez de descobrir o resultado dele na pista.
