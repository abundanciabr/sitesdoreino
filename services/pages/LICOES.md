# Lições da célula `pages`

O que já custou tempo **dentro desta célula**. O que serve a qualquer célula vai
para `armadilhas/`, e não para cá (regra do `CLAUDE.md`).

Lei da célula: `docs/changespecs/CS-PAGES-0001.md`.
Constituição: `constituicoes/AGENTS.pages.md`.

---

## 1. Reler o pedido não prova a trava de linha (27/09/2026)

**Sintoma:** a conferência do portfólio decidia o mesmo pedido duas vezes. Duas
abas da fila da equipe gravavam dois selos e mandavam duas cartas ao aluno.

**Causa:** `aceitar()` conferia o estado no objeto que a tela leu ao abrir e
gravava com `save()` cego. A trava única do banco impede criar outro pedido,
não decidir de novo.

**Solução:** toda decisão sobre um pedido começa por `_travar(pedido)`
(`apps/portfolio/conferencia.py`), que relê a linha com
`refresh_from_db(from_queryset=...select_for_update(of=("self",)))` dentro da
transação, e só então confere o estado.

**O que a prova ensinou:** os testes com um objeto velho em memória ficam
verdes mesmo sem `select_for_update`, porque reler já basta quando as duas
decisões são uma depois da outra. Só o teste de duas conexões ao mesmo tempo
(`tests/test_a_conferencia_decide_uma_vez.py`, com `transaction=True` e duas
threads) reprova quando a trava sai. Gesto novo que decide alguma coisa nesta
casa leva os dois testes.
