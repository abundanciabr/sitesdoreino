---
schema_version: 2
armadilha: 279
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  detector: test_o_SEGUNDO_BRACO_viaja_ate_o_script
  dono: ci/tests/test_vacina_do_deploy_automatica.py
sinal:
  - `cannot be rerun; Resource not accessible by personal access token`
  - `Resource not accessible by integration`
---

# `secrets.X || github.token` não é um plano B: é o PAT SOMBREANDO o único token capaz — e a permissão certa, concedida, não salva

**Sintoma.** Um workflow tem o bloco `permissions:` certo, o log do `Set up job`
confirma a permissão concedida, e a operação falha assim mesmo:

```
🧱 PAROU POR SEGURANÇA: gh run rerun falhou:
run 33341511607 cannot be rerun; Resource not accessible by personal access token
```

Você olha o YAML, vê `actions: write` escrito ali, e a mensagem parece mentir.

**Causa.** A permissão do bloco `permissions:` pertence ao `github.token` do
job, **e só a ele**. Um PAT do dono, passado por `env`, não recebe nada dali: os
escopos dele foram definidos quando ele foi criado, na tela do GitHub. Então a
linha aparentemente defensiva

```yaml
GH_TOKEN: ${{ secrets.PISTA_TOKEN || github.token }}
```

não é "usa o melhor e cai no outro": é **usa sempre o PAT quando ele existe**, e
o `||` do GitHub Actions não tem como saber que o PAT é o mais fraco dos dois
para aquela operação. O token com a permissão fica no banco de reservas, o
tempo todo, sem nunca entrar em campo.

**A palavra que diz QUEM falou, e é a única pista útil na mensagem:**

| última palavra da recusa | quem foi recusado |
|---|---|
| `by personal access token` | um PAT (fine-grained ou clássico) |
| `by integration` | o `GITHUB_TOKEN` do próprio job |

Se a sua recusa termina em `personal access token` num workflow que você acha
que usa o token padrão, ela está dizendo que o token padrão **não é** o que está
sendo usado. Foi assim que este caso se resolveu.

**Medido em 02/09/2026** (TAR-051), três casos isolados num ramo descartável,
cada um com o **seu próprio** run alvo — achado pelo título do commit e nunca
por índice de lista, porque um caso que redisparasse tiraria o alvo da lista de
falhados e moveria os índices dos outros, dando à asserção duas causas
suficientes. E o veredito lido do `run_attempt` **por fora**, porque
`gh run rerun` devolve 0 só por enfileirar
([183](183-deploy-cancelado-nao-e-deploy-adiado-a-celula-fica-para-tras.md)):

```
PISTA_TOKEN   + permissions actions:write  → 403 "by personal access token" · attempt 1 → 1
github.token  + permissions actions:write  → OK                             · attempt 1 → 2
github.token  + permissions actions:read   → 403 "by integration"           · attempt 1 → 1
```

A terceira linha é a mutação deliberada da primeira hipótese: o único delta
contra a segunda é `write` virar `read`, mesmo token e mesmo comando. Ela prova
que o bloco `permissions:` é **necessário**; a segunda prova que ele é
**suficiente** — desde que o token que o recebe seja o que vai ser usado.

**O agravante, e é o que faz esta entrada existir.** O projeto **já tinha
medido isto um dia antes.** O `pouso.yml` escreve desde 29/08/2026, com a mesma
mensagem crua, a frase inteira: *"permissão `actions: write` no token, que a
`PISTA_TOKEN` não tem"*, e há um teste-guarda (`test_a_pista_nao_chama_a_si_mesma_por_dispatch`)
que impede a pista de voltar a depender dela. No dia seguinte a vacina nasceu
preferindo aquele mesmo token, justamente para `gh run rerun` — a única
operação do arquivo que exige aquela permissão. O conhecimento existia a dois
arquivos de distância, guardado por teste, e **não alcançou quem precisava**.

**Por que a justificativa parecia boa.** A preferência pelo PAT foi copiada,
com o comentário junto, de um caso vizinho onde ela é **verdadeira**: *"events
triggered by the GITHUB_TOKEN will not create a new workflow run"* — um merge
feito com o token padrão não dispara o `deploy-celula`, e a pista depende disso.
Só que um **rerun não cria run novo**: ele cria um `attempt` do mesmo run. A
razão foi importada junto com o padrão, para um caso em que ela não se aplica, e
custou a única coisa que o PAT não podia fazer.

**Solução — a escada de braços, não a troca seca.**

```python
# ci/rerun_de_deploy.py
def bracos_do_rerun(ambiente=None):
    env = os.environ if ambiente is None else ambiente
    principal = env.get("GH_TOKEN") or env.get("GITHUB_TOKEN") or ""
    reserva = env.get("GH_TOKEN_RESERVA") or ""
    bracos = [("o token principal", principal)]
    if reserva and reserva != principal:      # sem PAT os dois são o mesmo:
        bracos.append(("o do próprio job", reserva))   # repetir seria teatro
    return bracos
```

```yaml
GH_TOKEN: ${{ secrets.PISTA_TOKEN || github.token }}
GH_TOKEN_RESERVA: ${{ github.token }}     # o segundo braço
```

**As três propriedades que fazem isto ser seguro, e nenhuma é opcional:**

- **Fail-open no BRAÇO, fail-closed no VEREDITO.** Se nenhum braço passar, o
  desfecho é byte a byte o de antes: erro, código 2, issue aberta, com a saída
  crua de cada um. A escada só pode transformar um "não consegui" em
  "consegui", nunca o contrário.
- **A reserva igual ao principal é DESCARTADA.** Duas voltas com o mesmo token
  não curam nada e ainda escrevem no log que havia um plano B — garantia sem
  mecanismo na forma mais barata que existe.
- **A escada não decide O QUE repetir.** Ela troca quem pede, nunca o `--failed`
  (run cancelado não tem job falhado —
  [188](188-deploy-de-push-cancelado-pela-cadeira-musical-fica-fora-do-ar.md)).

**Por que não trocar o token de vez.** Porque o motivo escrito para preferir o
PAT continua **não medido** aqui: um workflow `workflow_run` só dispara a partir
do ramo padrão, então "o rerun pedido pelo `github.token` acorda a vacina de
novo?" não se responde de um ramo de trabalho. Trocar a preferência por leitura
de documentação seria a inferência que a tarefa proibiu. Com a escada, se um dia
o PAT ganhar `actions: write`, ele volta a ser o preferido sozinho.

**A régua de bolso, para a próxima vez:** ao ver `||` entre um segredo e o
`github.token`, pergunte **qual dos dois tem a permissão da operação** — não
qual é "mais forte". Um PAT é mais forte para quase tudo e mais fraco
exatamente onde o bloco `permissions:` age. E quando a recusa vier, **leia a
última palavra dela**: ela nomeia o token, e é de graça.

**Origem.** 30/08/2026 23:20 UTC, run 33341539836 (a vacina) tentando curar o
run 33341511607 (`deploy-celula`, merge do PR #657, célula `admin`). A vacina
decidiu certo e não teve braço; a célula chegou ao ar de carona no deploy do PR
#658. Diagnosticado e curado em 02/09/2026 pela TAR-051 (PR #852).
**Categoria** (`RETROSPECTIVA-FASE-D`): garantia sem mecanismo (a permissão
estava declarada e não alcançava o token usado) · prova de fora (o veredito veio
do `run_attempt`, não do exit do `gh`) · contexto é orçamento (o fato estava
medido e escrito num workflow vizinho, e não chegou a quem precisava).
