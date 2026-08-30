---
schema_version: 2
armadilha: 231
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  detector: test_vacina_do_deploy_automatica
  dono: ci/tests/test_vacina_do_deploy_automatica.py
sinal:
  # Estreito de propósito: a mensagem sozinha é o desfecho CORRETO da vacina na
  # maioria dos dias. O que merece uma segunda olhada é ela aparecer no ramo do
  # `failure`, onde a resposta é de RUN e a pergunta é de CÉLULA (a 215).
  - `falhou no timeout da porta 22, mas o commit dele JÁ está no ar`
---

# A vacina do deploy só acordava no CANCELADO — e o vermelho por timeout da porta 22, que é 3× mais frequente, continuava esperando um humano

**Sintoma.** Um `deploy-celula` morre em `dial tcp ***:22: i/o timeout`. A VPS
está viva: o site responde 200, o fórum responde 200, a porta 22 devolve o banner
`SSH-2.0-OpenSSH_9.6p1` quando medida do PC. É a
[127](127-deploy-vermelho-com-i-o-timeout-e-a-vps-viva-nao-e.md), inteirinha, e a
cura dela está escrita, testada e automatizada desde a TAR-017.

**E nada acontece.** O `vacina-do-deploy.yml` acorda por `workflow_run`, mas a
condição dele era `conclusion == 'cancelled'` e só. Um robô precisava notar o
vermelho, reler a entrada, medir a porta e rodar `gh run rerun --failed`. Em
30/08/2026 isso aconteceu **três vezes num único dia** (PRs #610, #622 e #635) —
e a própria 127 declara a régua: *"dois episódios em 24h ainda são blip; três
viram estrutura"*.

**Causa — e ela é uma justificativa que envelheceu, não um descuido.** O comentário
do workflow dizia, com todas as letras:

> `cancelled` e só ele: `failure` na `main` já tem dono (o agente que mergeou,
> avisado pelo vermelho) e `success` não tem doença.

O raciocínio é bom e está certo sobre a VISIBILIDADE: cancelado é cinza e não
avisa ninguém; vermelho avisa. Mas ele responde a pergunta errada. A pergunta não
é *"alguém fica sabendo?"* — é *"o trabalho que sobra para essa pessoa é humano?"*.
E não era: era apertar um botão, depois de uma medição que uma máquina já sabe
fazer.

**Os números que derrubaram a justificativa** (medidos em 30/08/2026, por
`gh run list --json` / `gh run view --json`, nunca por pipe — §5.10):

| | 30 dias | 7 dias |
|---|---|---|
| deploys vermelhos (`deploy-celula`) | 41 | 39 |
| …que morreram no timeout da porta 22 | **14** | **13** |
| …outras causas (defeito real, já com dono) | 27 | 26 |
| deploys vermelhos (`deploy-infra`) | 4 | 4 |
| …que morreram no timeout da porta 22 | **0** | **0** |

E o número que mais surpreende, medido pelos PASSOS que rodaram em cada job (o
`conclusion` de um passo `continue-on-error` sai `success` mesmo quando ele
falhou — não serve; os passos da 2ª e 3ª tentativa só existem quando a anterior
foi recusada, e isso serve):

> **Das 18 vezes em que a VPS recusou a 1ª conexão, 17 chegaram à 3ª tentativa e
> as 17 morreram.** A escada de 3 tentativas de dentro do deploy salvou 1 em 18.

Ou seja: os 105 s de pausa do workflow (45 s + 60 s) não atravessam a janela
ruim, e a repetição que funciona é a de MINUTOS depois — que é exatamente o que
a vacina faz. E a curva é recente e crescente, acompanhando o número de robôs em
paralelo: 0% dos jobs até 27/08, 3% em 28/08, 5% em 29/08, **10% em 30/08**.

**Solução: o gatilho passa a acordar nas DUAS conclusões doentes.**

```yaml
if: >-
  (github.event.workflow_run.conclusion == 'cancelled' ||
   github.event.workflow_run.conclusion == 'failure') &&
  github.event.workflow_run.head_branch == 'main'
```

**Duas coisas tiveram de mudar junto, e nenhuma é opcional.**

**1. O `failure` passou a atravessar o portão da
[188](188-deploy-de-push-cancelado-pela-cadeira-musical-fica-fora-do-ar.md).**
Enquanto quem rodava a vacina era um robô, do PC, minutos depois do PRÓPRIO
merge, a pergunta *"repetir isto faz voltar alguma coisa?"* tinha resposta óbvia:
o SHA era o mais novo do mundo. Com gatilho, não tem. `gh run rerun --failed`
reconstrói a imagem do SHA DAQUELE run — e a 188 escreve a frase inteira:
*"nunca repita o run FALHADO de um commit mais velho para curar o seu: ele
publica o mundo sem o seu merge"*. Medido antes do conserto, com histórias
montadas à mão:

```
                                        ANTES              DEPOIS
o publicado DIVERGIU do run       acao='repetir' cod=0  → acao='parar' cod=1
um verde mais novo já contém ele  acao='repetir' cod=0  → acao='nada'  cod=0
não consegui medir a ancestralid. acao='repetir' cod=0  → acao='nada'  cod=2
o disparo foi workflow_dispatch   acao='repetir' cod=0  → acao='nada'  cod=1
```

A primeira linha é a que dói: sem o portão, o gatilho novo publicaria um rollback
sozinho, sem ninguém pedir e sem nada ficar vermelho. A regra de parada já
sobrevivia ao processo pelo `attempt` do run
([220](220-a-vacina-do-cancelado-media-a-esteira-errada.md)) e continua valendo
inteira nos dois ramos.

**2. "Veredito" e "alarme" deixaram de ser a mesma pergunta.** Com o gatilho só
no cancelado, `codigo != 0` e "acorde um humano" coincidiam: todo cancelado
não-curado é um merge invisível fora do ar. Com o `failure` dentro, `codigo != 0`
passou a incluir os **27 vermelhos por defeito de código**, que já estão
vermelhos, já têm dono e já acordam o `alarme-main`. Uma issue por cada um
afogaria as 14 que interessam — o alarme que se aprende a ignorar, que é o
argumento que o próprio workflow já escrevia sobre não gritar em todo
cancelamento. Quem responde a segunda pergunta é `Decisao.precisa_de_alarme`, num
canal próprio (`$GITHUB_OUTPUT`), **sem torcer o sentido do código de saída** —
que é como um contrato [INV-CI01] apodrece. O padrão do campo é ALARMAR: ramo
novo nasce barulhento e o silêncio se escreve à mão, com o motivo do lado.

**A causa da porta 22 não é a VPS — e a sonda já sabia disso.** O log da 1ª
tentativa do run `33330434813` grava a frase que fecha o diagnóstico:

```
❓ A porta 22 da VPS, medida do runner: ficou MUDA nas 3 sondagens seguidas
   (estourou o tempo em 3) — e daqui eu também NÃO alcancei o site público,
   que serve 200 para o mundo. Quem está cego é o runner, não a porta.
```

O runner do GitHub não alcançava **nada** — nem a porta 22, nem o site público.
É a rede de saída do runner engasgando, não a VPS recusando. Por isso a cura é
repetir de outro runner, minutos depois, e por isso **não há o que pedir ao
provedor da VPS**: nas 18 ocorrências a VPS esteve viva e servindo o tempo todo.
Desde esta entrada a vacina do PC diz isso na mensagem quando lhe acontece o
mesmo (`_o_medidor_estava_cego`) — não muda veredito nenhum, muda o que o humano
lê na issue, para que "não consegui medir a porta 22" não seja lido como "a minha
VPS quebrou" ([209](209-a-sonda-disse-falha-permanente-e-a-vps-estava-viva.md)).

**O buraco que esta entrada NÃO fecha, e é preciso saber dele.** Para o
`deploy-celula`, *"o publicado é ancestral do meu SHA"* é uma resposta de RUN a
uma pergunta de CÉLULA: um verde mais novo pode conter este commit no Git e mesmo
assim não ter publicado a célula que morreu aqui, porque cada run publica só as
células que o push DELE tocou
([215](215-deploy-verde-mais-novo-nao-cobre-as-celulas-que-o-seu-cancelou.md)). O
ramo `head_ja_publicado` herda isso do cancelado — e a
[220](220-a-vacina-do-cancelado-media-a-esteira-errada.md) já o declara aberto.
Herdado e declarado, não alargado em silêncio.

---

## A irmã inseparável: uma esteira de deploy trancava a outra

**Sintoma.** O `deploy-infra` fica vermelho e o log não fala de infraestrutura
nenhuma:

```
  vermelhos-nao-previstos  FAIL   1 workflow(s) vermelhos fora da lista do portão
  - .github/workflows/deploy-celula.yml => failure (…/runs/33328262902)
```

Um soluço de rede na esteira das células reprovou a esteira da infraestrutura. O
merge ficou fora do ar **duas vezes em vez de uma**, e o mantenedor leu
"deploy-infra vermelho" — que soa como problema de infraestrutura.

**Causa.** `ci/portao_de_deploy.py::vermelhos_nao_previstos` barra o deploy se
QUALQUER workflow fora da lista `conhecidos` estiver vermelho no mesmo SHA. A
regra existe para uma coisa boa e estreita: *check novo não nasce fora do portão
sem decisão por escrito*. Só que as duas esteiras de deploy nunca foram
declaradas — e elas nascem no MESMO SHA sempre que um PR de infraestrutura entra,
porque **todo PR deste projeto carrega um registro obrigatório em `painel/**`**,
que casa o `paths:` do `deploy-celula`.

**Medido nos 30 dias até 30/08/2026:** `vermelhos_nao_previstos` reprovou 4
vezes, e as **quatro** foram esta cascata, nas duas direções — célula travada por
infra (runs `32713472907`, `33274286219`) e infra travada por célula (runs
`33029073525`, `33328262912`). **Zero** vezes ela pegou o que existe para pegar.

**Solução: declarar as duas em `conhecidos`** — que é literalmente o que a
mensagem de erro da regra pede de quem quer uma isenção — e **nunca** em
`exigidos`.

**Por que separar é seguro, e não só conveniente.** As duas esteiras publicam
coisas independentes: o `deploy-celula` empurra a IMAGEM de uma célula, o
`deploy-infra` troca o `docker-compose.yml` e o `traefik`. O compose referencia a
imagem por tag MÓVEL (`ghcr.io/…:${CELULA_TAG:-main}`), então uma imagem que não
foi publicada deixa a tag apontando para a anterior — a mesma que já está
rodando. Sincronizar a infraestrutura com uma célula atrasada é o estado normal
entre dois deploys.

**Por que fora de `exigidos`:** exigir a esteira irmã faria todo deploy de célula
esperar por um `deploy-infra` que, na esmagadora maioria dos SHAs, nem nasce — 26
runs em 30 dias contra 417. Trocaria um bloqueio raro por um bloqueio diário.

**Guarda:** o mesmo trio que o vigia e a vacina já exigem em
`ci/tests/test_portao_de_deploy.py` — a isenção existe · a isenção é ESTREITA (um
`inventado.yml` vermelho continua barrando) · a declaração está na fonte.

**Origem.** 30/08/2026, TAR-041. **Categoria** (`RETROSPECTIVA-FASE-D`): garantia
sem mecanismo (a cura existia, escrita e testada, e o gatilho não a alcançava) ·
humano no caminho crítico (o "dono" do vermelho tinha como trabalho apertar um
botão) · fail-closed na borda (o portão da 188 precisou vir junto, senão o
automatismo publicaria rollback sozinho).
