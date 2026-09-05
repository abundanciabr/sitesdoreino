# config/api.py  # [RECEITA:R1 v1]
from ninja import NinjaAPI

from apps.core.auth import bearerAuth
from apps.fatos.api import router as fatos_router

# O ENDEREÇO, e a escolha entre os dois formatos que a casa usa.
#
# As células que também servem PÁGINAS sob um prefixo público montam a porta de
# máquina em `/interno/` (`identidade`, `forum`, `sugestoes`): ali a palavra
# "interno" separa a porta da superfície que o visitante vê. As demais montam
# em `/api/<celula>/`.
#
# A `metricas` não serve página nenhuma, hoje e sempre (`AGENTS.metricas.md`),
# e não tem rota no Traefik: `infra/docker-compose.yml` a declara sem `labels`,
# então ela só existe na rede interna do Docker. Sem superfície pública para
# separar, a palavra "interno" não distinguiria nada, e o formato majoritário é
# o que fica.
#
# CONGELAR ESTE VALOR É O RITO DE CONTRATO (`RITOS.md` §3), e é PR à parte, com
# a etiqueta `contrato` e o mantenedor presente. Este PR NÃO cria
# `contracts/metricas.openapi.yaml` e NÃO mexe em `ci/manifesto-de-contratos.json`:
# contrato em disco obriga a linha do manifesto a virar `required`, e `required`
# antes de a porta existir deixa o `make ci` da célula em ERROR no PR seguinte,
# longe de quem causou. Foi o que custou uma rodada à `gamificacao`
# (`armadilhas/228` e `243`), e é por isso que a ordem aqui é porta primeiro,
# contrato depois.
#
# QUEM FECHA A PORTA É O BEARER, e nesta célula ele não é o único cadeado: sem
# rota no Traefik, `metricas:8000` não é alcançável da internet. A topologia
# AJUDA (como ajuda na `mensageria`), mas não é o guarda: ela é configuração de
# infra, muda sem passar por este arquivo, e uma porta que dependesse dela
# ficaria aberta no dia em que alguém a roteasse (`armadilhas/186`). Por isso o
# teste de 401 cobre TODAS as operações, medidas do schema vivo.
api = NinjaAPI(
    title="Metricas - API de leitura",
    version="1.0.0",
    description=(
        "O livro de fatos da plataforma, lido por MAQUINA.\n"
        "\n"
        "Existe para que o placar do mantenedor possa dizer o que MUDOU, e nao\n"
        "so como as coisas estao agora. As celulas donas respondem o presente\n"
        "ao vivo; o passado esta aqui, guardado fato a fato, imutavel.\n"
        "\n"
        "Lei do assunto: docs/decisoes/PLANO-PAINEL-DE-GESTAO.md §6.2.\n"
        "\n"
        "NADA DE DADO PESSOAL SAI POR AQUI, e nem entra: esta celula guarda so\n"
        "ids opacos. Para contar nao e preciso saber quem e.\n"
        "\n"
        "ESTA PORTA SO LE. Um fato guardado nao se corrige nem se apaga: a\n"
        "correcao e um fato novo, e ela entra pela recepcao de eventos, nunca\n"
        "por aqui.\n"
        "\n"
        "ONDE FALTA COBERTURA, A RESPOSTA DIZ QUE FALTA. Assunto que nunca\n"
        "chegou nao aparece em listCoverage, e dia sem fato nao aparece em\n"
        "countFacts: ausencia nao vira zero, porque zero e uma afirmacao sobre\n"
        "o mundo.\n"
        "\n"
        "MARCO NAO E FATO, e a diferenca decide o que se pode guardar. O fato e\n"
        "o que uma celula afirmou, e nunca muda; o marco (countMilestones,\n"
        "listMilestones) e uma LEITURA que esta celula faz dos fatos, e a data\n"
        "dele anda para tras quando um fato mais antigo chega depois.\n"
        "\n"
        "MARCO TEM SUJEITO, E O SUJEITO TEM TIPO: `pessoa` ou `matricula`, que\n"
        "sao vocabularios de identidade diferentes e nunca se somam. As duas\n"
        "operacoes de marco carregam esse tipo em toda linha, e de proposito\n"
        "nao oferecem nenhum total que atravesse os dois.\n"
        "\n"
        "MARCO NAO TEM SITE. countFacts e listCoverage exigem site_id; as duas\n"
        "operacoes de marco contam a plataforma inteira, porque a tabela de\n"
        "marcos nao guarda o site. Quem consome nao pode apresentar esse numero\n"
        "como sendo de um site.\n"
    ),
    servers=[{"url": "http://metricas:8000/api/metricas"}],
    auth=bearerAuth(),
    openapi_extra={"security": [{"bearerAuth": []}]},
)
api.add_router("", fatos_router)
