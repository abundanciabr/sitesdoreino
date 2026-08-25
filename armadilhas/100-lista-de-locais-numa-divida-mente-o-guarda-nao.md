# A lista de locais dentro de uma dívida mente, e o guarda de referências não pega

**Sintoma:** você pega carona numa dívida do `ARMADILHAS-OPERACAO.md §9` que
enumera os arquivos a corrigir, conserta exatamente os que ela nomeia, o
`make ci` fica verde — e a citação errada continua no repositório.

Concreto (25/08/2026, despacho `leads/fuso-e-data`): a dívida "12 citações ainda
dizem `ARMADILHAS.md §1` / `§9`" lista **dois** lugares em `leads`
(`apps/core/…/consume_eventos.py:88`, `tests/test_inv_leads_reentrega_pel.py:3`).
O `grep` achou **três** — `services/leads/LICOES.md:136` também citava
`ARMADILHAS §9` e não estava na tabela.

**Causa — duas, e a segunda é a que dói:**

1. A lista foi escrita à mão no dia do particionamento e congelou ali; o
   repositório continuou andando.
2. O guarda que existe, `test_toda_referencia_a_uma_armadilha_resolve`
   (`ci/tests/test_indice_de_armadilhas.py`), valida o **número** da armadilha,
   nunca o **nome do arquivo** que a prosa cita. `ARMADILHAS.md §9` resolve
   verde exatamente como `ARMADILHAS-OPERACAO.md §9` — foi por isso que a
   dívida pôde nascer e envelhecer sem nada apitar. Garantia sem mecanismo: a
   tabela promete a lista completa, e nada mede que ela esteja completa.

**Solução:** trate a lista da dívida como **pista, não como inventário**. Antes
de dar por quitada a parte que é sua, rode o grep e conserte o que ele achar,
não o que a tabela nomeou:

```bash
grep -rn "ARMADILHAS[- .A-Za-z]*§9" services/<sua-celula>/
```

E, ao reportar, diga quantos locais você achou de verdade — quem mantém a
tabela precisa saber que o número dela está errado. Vale para qualquer dívida
que enumere caminhos: `§9` de citações, listas de "as 8 células antigas", listas
de TODO em decisão.

**Origem:** despacho `leads/fuso-e-data` (lote de 25/08/2026), PR do
`TIME_ZONE` da `leads`. Restam 4 células com a mesma carona pendente —
`alunos`, `checkout`, `mensageria`, `pagamentos` —, e a contagem delas na tabela
também pode estar baixa.
