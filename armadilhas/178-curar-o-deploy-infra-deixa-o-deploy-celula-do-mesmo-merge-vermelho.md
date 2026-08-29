# Curar o `deploy-infra` deixa o `deploy-celula` do MESMO merge vermelho — e ele não se cura pelo mesmo caminho

**Sintoma:** um merge que toca `infra/` **e** `painel/` (ou `services/`) dispara os
DOIS deploys. O `deploy-infra` falha no blip de SSH da `armadilhas/127`, você roda
`ci/rerun_de_deploy.py` e ele fica verde — resultado correto, ferramenta certa.
Só que o `deploy-celula` do mesmo merge **também está vermelho**, e rodar o
`rerun_de_deploy.py` nele devolve:

```
run <id>: conclusion=failure · timeout-ssh=False · porta22=None · site=None
PARAR: falhou, mas NÃO com o timeout de SSH da armadilhas/127.
```

A ferramenta está certa em recusar: a falha dele **não é** o blip.

**Causa:** o `portao-de-deploy` é fail-closed contra qualquer vermelho vizinho.
No log do run barrado:

```
  vermelhos-nao-previstos  FAIL   1 workflow(s) vermelhos fora da lista do portão
  - .github/workflows/deploy-infra.yml => failure
```

Ou seja, é **cascata, não defeito**: o `deploy-celula` foi barrado porque o
`deploy-infra` estava vermelho **naquele instante**. Curar o de infra depois não
volta atrás e desbloqueia o da célula — o run barrado continua barrado, e a
célula fica servindo a versão ANTERIOR, em silêncio.

**A leitura errada e cara:** ver `timeout-ssh=False` e concluir "então é defeito
de código no meu PR". Não é. A pergunta certa é *"o que mais estava vermelho
quando este run rodou?"* — e a resposta está no próprio log do portão, na linha
`vermelhos-nao-previstos`, que **nomeia o workflow culpado**.

**Solução:** cure primeiro o vermelho que o portão nomeia; **depois** re-rode o
deploy barrado (`gh run rerun <id> --failed`) e confira o veredito por
`gh run view <id> --json status,conclusion`. A ordem importa: re-rodar o barrado
antes faz o portão barrar de novo, pelo mesmo motivo, e parece defeito teimoso.

**A armadilha dentro da armadilha — por que isto quase passou batido em
29/08/2026:** um merge SEGUINTE, minutos depois, disparou um `deploy-celula` novo
que passou limpo (o vermelho vizinho já não existia) e publicou a versão atual.
O resultado final ficou certo **por acidente de tráfego**. Se aquele merge tivesse
sido o último do dia, a célula teria dormido numa versão velha sem ninguém saber.
Não confie no próximo merge para consertar o seu: **um merge que dispara dois
deploys exige conferir os DOIS**, mesmo quando o primeiro que você olhou ficou
verde.

**Origem:** PR #502 (conserto do `www.meshcraft.top`), 29/08/2026.
