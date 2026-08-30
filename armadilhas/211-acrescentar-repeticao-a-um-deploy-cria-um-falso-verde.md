---
schema_version: 2
armadilha: 211
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: ci/tests/test_deploy_infra_sobrevive_ao_soluco.py
---

# Acrescentar repetição a um deploy cria um falso-verde novo — o `continue-on-error` que a repetição EXIGE apaga a reprovação da 1ª tentativa

**Sintoma.** Não há erro nenhum, e é esse o problema. Você leva a três-tentativas
de um workflow de deploy para o irmão que ainda não a tem — o desenho é o mesmo,
o YAML é válido, os passos existem, os testes passam. A partir daí o job fecha
**VERDE** em runs nos quais o script na VPS **rodou e reprovou**: validação de
compose recusada, serviço que não subiu, smoke de site em 404. O site continua
servindo a versão anterior e ninguém fica sabendo.

**Causa — a repetição e o veredito brigam pelo mesmo interruptor.** Para existir
uma 2ª tentativa, a 1ª **precisa** de `continue-on-error: true`; sem ele, o job
morre na primeira falha e não há o que repetir. Mas `continue-on-error` é
literalmente "a falha deste passo não conta", e ele não distingue *por que* o
passo falhou. Se a condição de repetir for estreita — e ela deve ser, veja abaixo
—, as tentativas seguintes são **puladas**, e aí não sobrou nenhum passo capaz de
reprovar: a única reprovação real foi apagada pelo `continue-on-error` que a
repetição exigiu.

O irmão de onde você copiou pode não ter esse buraco **por acidente de história**.
No caso real, o `deploy-celula` estava protegido porque ganhou, em 28/08/2026 e
por um motivo completamente diferente (o parâmetro com nome errado que deixou o
deploy verde sem subir imagem), um passo que EXIGE uma sentinela de conclusão na
saída capturada. Quem copia o retry e não copia essa trava leva metade do
desenho — e a metade que leva é justamente a que cria o risco.

**Solução: junto com a repetição, um portão de conclusão. Sempre.**

O script na VPS imprime uma sentinela na última linha, e um passo com
`if: ${{ !cancelled() }}` exige vê-la na saída capturada de ALGUMA tentativa:

```yaml
- name: A infraestrutura foi mesmo sincronizada?
  if: ${{ !cancelled() }}
  env:
    SAIDA_1: ${{ steps.aplicar1.outputs.stdout }}   # nunca interpolado no run:
  run: |
    set -eu
    if printf '%s' "${SAIDA_1:-}" | grep -q 'SINCRONIZACAO-CONCLUIDA:'; then
      echo "✅ rodou até o fim"; exit 0
    fi
    echo "❌ PAROU: nenhuma tentativa chegou ao fim."; exit 1
```

`!cancelled()` e não `always()`: run cancelado pela cadeira musical do grupo
`deploy` (`armadilhas/173` e `/188`) não executou nada, e narrar um deploy que não
aconteceu é inventar história.

---

## A segunda metade, que é de desenho: a repetição herdada pode não ser segura no seu workflow

Antes de copiar o retry, responda duas perguntas sobre o **seu** script — não
sobre o do irmão:

**1. Qual é a unidade de repetição?** O `deploy-celula` tem UM passo de rede
(SSH). O `deploy-infra` tem DOIS em sequência: um SCP que enche uma área de
staging e um SSH que a **consome** (`rmdir infra.new` no fim do primeiro bloco).
Repetir só o SSH morreria no `ls infra.new` da segunda volta. A unidade ali é o
**par**, e repetir o par só é seguro porque o `rm: true` da `appleboy/scp-action`
— *"Remove target directory before upload"*, na documentação da própria ação —
aponta para a área de staging e nunca para um caminho em uso.

**2. Repetir depois de o script ter COMEÇADO é inofensivo?** No `deploy-celula`,
sim: `pull` e `up -d` sobre o estado já correto não fazem nada. No `deploy-infra`,
**não**: o script troca arquivos em uso e **data um backup** do que estava lá.
Repetir depois que ele começou dataria um backup novo do estado já meio-trocado,
e o caminho de restauração que o próprio script imprime passaria a apontar para
um estado misto. O conserto não é desistir da repetição — é estreitá-la:

```
# uma SEGUNDA sentinela, impressa na PRIMEIRA linha do script
- name: Enviar para staging (tentativa 2 de 3)
  if: "!contains(steps.aplicar1.outputs.stdout, 'SINCRONIZACAO-INICIADA:')"
```

Sem a marca de partida na saída, está **provado** que a VPS não executou uma
linha — e aí repetir é tão seguro quanto o primeiro envio. Com a marca, o run
fica vermelho com o erro real, sem repetição nenhuma: o que a `armadilhas/127`
cura é a conexão que não abre, **não** o script que reprovou.

Repare que a condição NÃO é `outcome == 'failure'`. Esse é o reflexo natural, e
ele junta "a VPS não atendeu" com "o script rodou e recusou" — as duas coisas que
esta entrada inteira existe para separar. É a mesma família do
[INV-CI01] e da [127](127-deploy-vermelho-com-i-o-timeout-e-a-vps-viva-nao-e.md):
um sinal de duas posições não pode carregar três respostas.

**A régua de bolso:** repetição segura precisa de três peças, e faltar uma
qualquer estraga as outras duas — *(a)* o que repetir (a unidade), *(b)* quando
repetir (a condição, provada e não suposta) e *(c)* quem reprova no fim (o portão
de conclusão). Copiar só a (a) do workflow vizinho é o caminho mais rápido para
um verde que mente.

**O que o guarda cobre, e o que não cobre.** `ci/tests/test_deploy_infra_sobrevive_ao_soluco.py`
impõe as três peças **no `deploy-infra`**, e `ci/tests/test_sonda_da_vps.py` faz o
equivalente no `deploy-celula`. Nenhum dos dois protege um **terceiro** workflow
que ganhe repetição amanhã — para esse, a régua acima é leitura, não mecanismo.

**Origem.** 30/08/2026, TAR-024 (PR #602), levando a vacina da `armadilhas/127` ao
`deploy-infra`. O falso-verde não chegou a acontecer em produção: ele apareceu no
papel, ao contar o que restaria reprovando depois de as tentativas 2 e 3 serem
puladas. As duas perguntas de desenho acima vieram do próprio despacho, que
mandou confirmar a segurança da repetição **antes** de escrevê-la.
**Categoria** (`RETROSPECTIVA-FASE-D`): falso-verde (§1) nascendo de dentro de uma
cura — o mecanismo novo abriu o buraco que o mecanismo velho fechava.
