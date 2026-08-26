# `mergeable=UNKNOWN` depois de um merge: o portão recusa, e ele está certo

**Sintoma:** numa janela de merge serial, `python ci/mergear.py <N> --confirmo <N>`
devolve **ERROR** logo depois do merge anterior:

```
conflitos   ERROR  o GitHub ainda não sabe se dá para mergear (mergeable=UNKNOWN)
RESULTADO   ERROR
MERGE RECUSADO. Não foi possível confirmar o estado do PR.
```

Todos os checks estão verdes. Rodar de novo geralmente devolve **PASS** e mergeia.

**Causa:** o GitHub recalcula a mergeabilidade de cada PR aberto de forma
**assíncrona** toda vez que a `main` se move. Enquanto o cálculo não termina, a API
responde `UNKNOWN`. O portão trata isso como ERROR de propósito — `UNKNOWN` não é
`MERGEABLE`, e "não consegui medir" nunca vira PASS ([INV-CI01]). **Isto não é um bug
do `mergear.py`; é ele funcionando.** Não conserte o portão, não force o merge.

**Solução, em degraus:**

1. **Rode de novo.** Na maioria das vezes o segundo `--conferir` já sai PASS. Em
   26/08/2026 isso aconteceu em 5 de 9 merges de uma janela.
2. **Se ficar teimoso** (medido: `UNKNOWN` por mais de 2 minutos, com
   `gh pr view <N> --json mergeable` repetido), force o recálculo com
   `gh pr update-branch <N>`. Ele traz a `main` para dentro do branch e o cálculo
   sai do lugar. **Atenção:** isso cria um commit novo no PR, então **os checks
   rodam outra vez** — espere ficarem verdes antes de mergear (~2 min), senão o
   portão recusa por check pendente, que é outro ERROR com outra causa.
3. **Nunca** contorne com o botão do site nem com `gh pr merge` cru. O portão é o
   único caminho (Lei 4).

**A armadilha DENTRO da armadilha, e ela quase passou:** ao encadear
`mergear.py ... ; <espera o run de deploy>` num comando só, o merge pode ser
**recusado** e a etapa seguinte ainda encontrar um run de deploy — o do PR
**anterior**, que já estava lá. A saída sai assim:

```
MERGE RECUSADO. Não foi possível confirmar o estado do PR.
DEPLOY identidade: completed/success        ← MENTIRA: esse run é do merge anterior
```

Um veredito verde com o nome da célula errada, pronto para ser copiado no relatório.
**Antídoto:** guarde o id do último run ANTES do merge e compare depois —

```bash
ANTES=$(gh run list --branch main --workflow deploy-celula.yml --limit 1 --json databaseId -q '.[0].databaseId')
python ci/mergear.py <N> --confirmo <N>
ID=$(gh run list --branch main --workflow deploy-celula.yml --limit 1 --json databaseId -q '.[0].databaseId')
[ "$ID" = "$ANTES" ] && echo "PAROU: nenhum run novo foi disparado" && exit 1
```

Prima direta da §5.10 (veredito de run nunca sai do exit de um pipe): aqui o veredito
é real, só que **de outra coisa**.

**Origem:** janela de merge do lote do fuso horário, 26/08/2026 — 9 PRs mergeados,
`UNKNOWN` em 5 deles, dois exigindo `update-branch`, e um relatório de deploy com o
nome errado pego antes de virar registro.
