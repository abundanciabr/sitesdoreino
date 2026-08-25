# Muralha de PR posta a rodar num push passa por vacuidade — e "rodar as três" é pior que rodar uma

**Sintoma:** um portão que reprova de verdade em PR imprime, no push da `main`,
um verde de aparência impecável:

```
  cerca-de-celula       PASS   ✅ Cerca de célula: OK — 0 célula(s) tocada(s)
  orcamento-de-mudanca  PASS   ✅ Orçamento de mudança: OK
```

`0 célula(s)`, `Arquivos alterados: 0`, exit 0. Nada gritou, nada faltou, nenhum
`fatal:` no log. E, no entanto, ninguém mediu coisa alguma.

**Causa — são DUAS, e a segunda sobrevive ao conserto da primeira.**

*(1) A base some.* Toda muralha de diff calcula
`git diff --name-only "${BASE_REF:-origin/main}"...HEAD`. Num push da `main`,
`HEAD` **é** `origin/main`: o merge-base dos dois lados é o próprio `HEAD`, o
diff sai vazio, e a contagem zerada percorre o script inteiro sem disparar
nenhuma regra. Não é falha de instrumento — é o instrumento respondendo
corretamente a uma pergunta que não faz sentido ali. Por isso `armadilhas/040`
não pega este caso: lá o `git` gritava; aqui ele acerta.

*(2) O contexto some — e este é o que engana.* A correção óbvia é dar uma base
real (`github.event.before`). Ela conserta o diff **e não conserta a decisão**:
`cerca-de-celula.sh` e `orcamento-de-mudanca.sh` julgam por `PR_LABELS`, que só
existe no evento `pull_request`. Medido em 25/08/2026, mesmo commit, mudando só
a variável:

```
contracts/ tocado, PR_LABELS=contrato       → ✅ OK        (exit 0)
contracts/ tocado, sem PR_LABELS            → ❌ MURALHA   (exit 1)
17 arquivos, PR_LABELS=arquitetural         → ✅ OK        (exit 0)
17 arquivos, sem PR_LABELS                  → ❌ ORÇAMENTO (exit 1)
```

Ou seja: com base real, todo merge de contrato e toda mudança arquitetural
**legítimos** — aprovados pelo rito, com a label no PR — abririam uma issue de
"main vermelha". Troca-se um falso-verde por um falso-vermelho crônico, e alarme
que grita no caso certo é alarme que se aprende a ignorar. Aí ele para de servir
para o caso errado, que era o motivo de existir.

O fundo da coisa: essas duas são muralhas da **forma de um PR** (1 PR = 1
célula; orçamento *por PR*). Um push da `main` não é um PR — pode carregar
vários de uma vez. A regra não tem referente ali.

**Solução:** antes de mudar o gatilho de um portão, pergunte de que **insumos**
a medição dele depende, e se esses insumos existem no gatilho novo. `grep -nE
'BASE_REF|PR_LABELS|git diff|git grep'` no script responde em um comando. No
caso concreto, das três muralhas só `guarda-de-segredos.sh` não lê nenhum dos
dois: ela varre a árvore inteira com `git grep`, mede na `main` exatamente o que
mede num PR — e era justamente a que nunca tinha rodado lá. **A entrega certa
foi mais estreita que o pedido:** roda a repo-wide, e o `SKIP` das outras duas
fica **declarado por escrito** ([INV-CI01]: `SKIP` só existe declarado), num
comentário do YAML com a medição colada.

Declaração escrita, porém, é papel. Torne-a executável: um teste que lê o YAML e
reprova nos **dois** sentidos — se o step sumir, *e* se alguém acrescentar ali
uma muralha de diff sem refazer a medição
(`ci/tests/test_alarme_main_roda_a_muralha_repo_wide.py`, no espírito de
`test_workflow_de_deploy_exige_o_portao`). Ele custa 0,1s e roda no `muralhas` e
no próprio `alarme-main`. Inclua no teste a checagem de que o script escolhido
**continua** repo-wide: se `guarda-de-segredos.sh` um dia passar a filtrar por
diff, o step vira vácuo silencioso — a mesma armadilha, uma camada abaixo, onde
ninguém olharia.

**Regra de bolso:** "o portão não roda aqui" é um buraco visível e barato de
achar. "O portão roda aqui e não mede nada" é um buraco que **parece uma
proteção** — e ninguém audita o que já está verde. Ao fechar o primeiro, cuide
para não abrir o segundo.

**Origem:** peça B3 do PLANO-10X, 25/08/2026 — `alarme-main.yml` rodava só
`ci/ci.py --apenas testador`, e a guarda de segredos jamais tinha varrido a
`main` (este repositório não tem required check, `ARMADILHAS-OPERACAO.md §1 H3`,
então o alarme é a única rede depois do fato).
