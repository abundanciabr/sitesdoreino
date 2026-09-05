# 336 — Despacho de lote que proíbe tocar `INVARIANTES.md` para um guarda `test_inv_*` deixa o PR vermelho no guarda dos guardas

**Data:** 05/09/2026 · **Onde:** todo despacho que manda plantar um teste-guarda
de invariante (`services/<celula>/tests/test_inv_*.py`) · **Custo evitado:** um
PR verde na célula e vermelho em três checks da raiz, mais uma volta da maestro
para consertar o que o robô foi proibido de tocar

## Sintoma

O robô do lote entrega o degrau perfeito: 74 testes verdes na célula, o
invariante `[INV-CUR-C2]` provado por mutação, `make ci` limpo. No CI do PR a
suíte da célula fica verde e **`muralhas`, `espelho-da-main` e
`windows-a-maquina-dos-robos` ficam vermelhos**, os três no mesmo passo "Testar
o testador":

```
ci/tests/test_guarda_dos_guardas.py::test_o_repositorio_real_passa_hoje
regra guardas/inverso: services/cursos/tests/test_inv_c2_conteudo_so_pela_porta.py
  é test_inv_* sem linha `Teste-Guarda:` em INVARIANTES.md
  nem em ci/guardas-nao-declarados.txt
```

O robô não pode consertar: o despacho dele dizia, com todas as letras,
"INVARIANTES.md: FORA DE ESCOPO (arquivo-lei da raiz, compartilhado com o lote;
o C2 entra lá no PR que fechar a Fase 1)". Ele parou, diagnosticou no PR e
devolveu à maestro, exatamente como o runbook manda. A volta foi da maestro.

## Causa

Duas leis desta casa se somam, e o despacho contrariou as duas por medo de
colisão no lote:

1. **Todo `test_inv_*` nasce declarado no mesmo PR.** O guarda dos guardas tem
   a regra `guardas/inverso`: arquivo `test_inv_*` em disco sem linha
   `Teste-Guarda:` no `INVARIANTES.md` (ou sem a linha de dívida em
   `ci/guardas-nao-declarados.txt`) reprova. É o que impede um invariante de
   existir só como teste, sem lei que o explique.
2. **O inventário é por igualdade exata.**
   `test_parse_do_documento_real_casa_os_blocos_de_hoje` lista todos os códigos
   do `INVARIANTES.md`; um invariante novo obriga a acrescentar o código à lista
   em `ci/tests/test_guarda_dos_guardas.py`. A docstring diz: "acrescentar o
   código novo a esta lista é manutenção de inventário, não afrouxamento".

O medo de colisão era infundado: a entrada de invariante é um bloco novo,
acrescentado antes de `[INV-CI01]`, e a linha do inventário é uma linha nova
numa lista; dois robôs fazendo o mesmo em células diferentes se resolvem no
`rebase` com as duas sobrevivendo (a regra anticolisão que o próprio despacho
já carregava). Proibir o arquivo não evitou colisão nenhuma; só transferiu o
trabalho para depois e pintou o PR de vermelho.

## Solução

**Todo despacho que planta um `test_inv_*` inclui, nos ALVOS, as duas linhas
da raiz:** a entrada em `INVARIANTES.md` (no molde das vizinhas: o quê, por quê,
Teste-Guarda com a data da prova por mutação, célula dona) e o código na lista
de `test_parse_do_documento_real_casa_os_blocos_de_hoje`. E a regra anticolisão
que já vale para os outros arquivos compartilhados cobre esses dois: `git fetch
origin && git rebase origin/main` antes do push, as duas linhas sobrevivem.

Os dois arquivos são caminho CODEOWNERS (`ci/`, arquivo-lei da raiz): o
mandato é o do despacho, e o PR anuncia nominalmente que os tocou.

O que a maestro fez desta vez, para não repetir: a entrada e a linha do
inventário no ramo do robô, `python -m pytest -q ci/tests/test_guarda_dos_guardas.py`
lido pelo código de saída (o primeiro `| tail -2` mascarou um vermelho e a
corrente commitou por cima; veredito nunca sai de pipe, `ARMADILHAS.md` §5.10),
`--force-with-lease` depois do rebase, e a etiqueta `arquitetural` com fechar e
reabrir, porque os dois arquivos levaram o PR de 14 para 16 (`armadilhas/077`).

**E a sequela da etiqueta aplicada depois do push.** O push com os dois
arquivos a mais saiu ANTES da etiqueta `arquitetural`, e disparou uma rodada de
checks que reprovou no orçamento (16 arquivos); fechar e reabrir disparou duas
rodadas verdes no MESMO commit. `esperar.py --checks` é fail-closed sobre todas
as execuções do commit, viu a vermelha antiga e recusou o pouso, como deve. A
cura não é commit novo: `gh run rerun <id-do-run-reprovado> --failed` refaz só
aquela rodada no mesmo commit, e a espera se re-arma. Ordem certa, da próxima
vez: etiqueta, fechar e reabrir, e SÓ ENTÃO o push que estoura o orçamento.

Régua de uma linha para quem escreve despacho: **se o ALVO tem `test_inv_`, o
ALVO tem `INVARIANTES.md` e o inventário do guarda dos guardas.**
