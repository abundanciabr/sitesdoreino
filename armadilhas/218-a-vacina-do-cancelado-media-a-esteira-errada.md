---
schema_version: 2
armadilha: 218
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  detector: test_vacina_do_deploy_automatica
  dono: ci/tests/test_vacina_do_deploy_automatica.py
sinal:
  # Estreito de propósito: a frase "já está no ar" sozinha é o desfecho CORRETO
  # da vacina na maioria dos dias, e um sino que toca no caso certo é um sino
  # que se aprende a ignorar. O que merece uma segunda olhada é o diagnóstico de
  # um cancelado da esteira de INFRA — confira se o SHA publicado que ele cita é
  # mesmo um verde do `deploy-infra`.
  - `esteira=deploy-infra .*conclusion=cancelled`
---

# A vacina do deploy cancelado media a esteira ERRADA — e "já está no ar" era sobre outra coisa

**Sintoma.** Um `deploy-infra` termina `cancelled` (cadeira musical da
[173](173-workflow-manual-no-grupo-deploy-e-cancelado-antes-de-comecar.md)).
Você roda a vacina, que existe justamente para isso, e ela responde com a
serenidade de quem mediu:

```
NADA: o run 33317249576 foi cancelado, mas o commit dele JÁ está no ar:
a última publicação verde (fae5646ca185) já contém 166dcc3924eb.
```

Você fecha a tarefa. **A infraestrutura nunca foi sincronizada.** `fae5646ca185`
é o último verde do **`deploy-celula`** — a esteira que publica IMAGEM DE
CÉLULA. Ela não diz nada sobre o `docker-compose.yml` e o `traefik` que estão na
VPS. A vacina respondeu com precisão a uma pergunta que ninguém fez.

**Causa.** `ci/rerun_de_deploy.py` nasceu (TAR-017) sabendo falar de UM workflow:
`WORKFLOW_DO_DEPLOY = "deploy-celula.yml"` era constante, e
`_colher_o_cancelado` chamava `sha_do_ultimo_deploy_verde()` **sem argumento** —
inclusive quando o run cancelado era do `deploy-infra`. A decisão inteira é
`git merge-base --is-ancestor <publicado> <sha-do-run>`, e o `<publicado>` vinha
da esteira errada.

**Por que passa despercebido, e por que é caro.** As duas referências divergem o
tempo todo: o `deploy-celula` dispara em `painel/**`, e TODO PR deste projeto
carrega um registro obrigatório ali; o `deploy-infra` só acorda em `infra/**`.
Medido em 30/08/2026, nos dois últimos verdes do dia:

```bash
$ git merge-base --is-ancestor 8848f1f7 00952d43 && echo "o verde do CELULA já contém o do INFRA"
o verde do CELULA já contém o do INFRA
$ git rev-list --count 8848f1f7..00952d43
47
$ git log --format= --name-only 8848f1f7..00952d43 | grep -c '^infra/'
0
```

Ou seja: **47 commits de faixa em que um `deploy-infra` cancelado recebia "já
está no ar"**, e nenhum deles tocou `infra/` — nenhum deploy de infra nasceria
para pagar a dívida. O falso-verde da `RETROSPECTIVA-FASE-D` §1 dentro da
própria vacina que existe para matar falso-verde.

**Solução: a esteira é um FATO DO RUN, não uma constante.**

```python
# `gh run view <id> --json workflowName,attempt` — e daí para todas as medidas
fatos.workflow = dados["workflowName"]
arquivo = arquivo_do_workflow(fatos.workflow)      # descoberto pelo `name:`
fatos.sha_publicado = sha_do_ultimo_deploy_verde(arquivo.name)
```

Três detalhes que não são enfeite:

- **Sem esteira sabida, é ERROR.** "Não sei contra o que comparar" nunca vira
  "pode repetir" (INV-CI01). Antes disso, a mesma história devolvia `repetir`/0.
- **O arquivo se DESCOBRE pelo `name:` de dentro**, não pela convenção de nome
  de arquivo — senão um rename quebra calado, justamente na hora de decidir.
- **`paths:` tem duas formas em YAML** e este repositório usa as duas: em linha
  (`paths: ['services/**', …]`, o `deploy-celula`) e em bloco (`- 'infra/…'`, o
  `deploy-infra`). Um leitor que só soubesse a primeira devolveria "não consegui
  contar" só para a esteira nova.

**A irmã inseparável: a regra de parada tem de sobreviver ao PROCESSO.** No
mesmo dia a vacina ganhou GATILHO (`.github/workflows/vacina-do-deploy.yml`,
`workflow_run` no `cancelled` das duas esteiras). Isso abre um laço que não
existia enquanto um humano rodava o comando: **vacina → rerun → cancelado de
novo → vacina → rerun**, e o contador de tentativas, que morava em memória,
recomeça em zero a cada volta. A conta durável já existia e mora no GitHub:

```python
fatos.tentativas_feitas = max(em_memoria, int(dados["attempt"]) - 1)
```

Não é hipótese: no dia da medição, o run `33325108776` estava em `attempt: 4` —
três repetições feitas à mão, antes de existir automatismo nenhum.

**Distinção rápida das vizinhas.** Todas terminam igual (merge na `main` fora do
ar, em silêncio), e cada uma entra por uma porta:

| Quem | A porta | O que fazer |
|---|---|---|
| [173](173-workflow-manual-no-grupo-deploy-e-cancelado-antes-de-comecar.md) | disparo MANUAL expulso da vaga | grupo de concorrência próprio |
| [183](183-deploy-cancelado-nao-e-deploy-adiado-a-celula-fica-para-tras.md) / [188](188-deploy-de-push-cancelado-pela-cadeira-musical-fica-fora-do-ar.md) | deploy de PUSH expulso da vaga | a vacina — hoje ela acorda sozinha |
| [215](215-deploy-verde-mais-novo-nao-cobre-as-celulas-que-o-seu-cancelou.md) | o run rodou, mas o `fail-fast` da matriz derrubou células irmãs | a vacina NO RUN DO SEU MERGE |
| **esta** | a vacina rodou e mediu a esteira errada | ela lê `workflowName` do run |

**O buraco que CONTINUA aberto, e não é este arquivo que fecha.** Para o
`deploy-celula`, "o publicado é ancestral do meu SHA" é uma resposta mais grossa
que a pergunta: cada run só publica as células que o SEU push tocou (a
[215](215-deploy-verde-mais-novo-nao-cobre-as-celulas-que-o-seu-cancelou.md)).
Um verde mais novo pode conter o seu commit no Git e mesmo assim não ter
publicado a sua célula. A vacina, hoje, diria "já está no ar". Fechar isso exige
comparar a LISTA DE CÉLULAS do run cancelado com a dos runs seguintes — que é
exatamente a guarda que a 215 declara não existir.

**Origem.** 30/08/2026, TAR-029, ao ligar a vacina num gatilho automático. O
buraco só apareceu porque automatizar obriga a perguntar "e se o run for do
outro workflow?" — pergunta que, com um humano no comando, nunca foi feita, já
que quem rodava a vacina sabia de qual esteira estava falando e não reparava que
ela não sabia. **Categoria** (`RETROSPECTIVA-FASE-D`): falso-verde · garantia
sem mecanismo (a cura existia e ninguém a tomava) · fail-closed na borda.
