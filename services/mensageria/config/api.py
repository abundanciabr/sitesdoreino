# config/api.py  # [RECEITA:R1 v1]
from ninja import NinjaAPI

from apps.core.api import router as mensageria_router
from apps.core.auth import bearerAuth

# O ENDEREÇO, e a escolha entre os dois formatos que a casa usa.
#
# Sete células montam a porta em `/api/<celula>/` (`alunos`, `catalogo`,
# `checkout`, `gamificacao`, `leads`, `notificacoes`, `pagamentos`); três a
# montam em `/interno/` (`identidade`, `forum`, `sugestoes`). A diferença não é
# gosto: as três do `/interno/` também servem PÁGINAS sob um prefixo público, e
# ali a palavra "interno" separa a porta de máquina da superfície que o
# visitante vê.
#
# A `mensageria` não serve página nenhuma, não tem `SCRIPT_NAME` e não tem rota
# no Traefik (`infra/traefik/dynamic/plataforma.yml` não a cita): ela existe só
# na rede interna do Docker. Sem superfície pública para separar, a palavra
# "interno" não distinguiria nada, e o formato majoritário é o que fica.
#
# CONGELAR ESTE VALOR É O DEGRAU 6d, e ele é PR à parte, com a etiqueta
# `contrato` e o mantenedor presente (RITOS.md §3). Este PR NÃO cria
# `contracts/mensageria.openapi.yaml` e NÃO mexe em
# `ci/manifesto-de-contratos.json`: contrato em disco obriga a linha do
# manifesto a virar `required`, e `required` sem esta porta deixa o `make ci` da
# célula em ERROR no PR seguinte, longe de quem causou (`armadilhas/228`, que já
# custou isso à `gamificacao`). Depois do 6d, mudar o endereço vira Rito.
#
# QUEM FECHA A PORTA É O BEARER, e nesta célula ele não é o único cadeado: sem
# rota no Traefik, `mensageria:8000` não é alcançável da internet — só de dentro
# da rede `interna`. A topologia AJUDA aqui (como ajuda na `identidade`, e ao
# contrário do que acontece na `gamificacao`, `armadilhas/186`). Mesmo assim o
# guarda de 401 cobre TODAS as operações e o caso do env ausente: topologia é
# configuração de infra, muda sem passar por este arquivo, e uma porta que
# dependesse dela ficaria aberta no dia em que alguém a roteasse.
api = NinjaAPI(
    title="Mensageria - API interna",
    version="1.0.0",
    description=(
        "Superficie de MAQUINA das sequencias de mensagens (as jornadas).\n"
        "Existe para que a tela do mantenedor leia as sequencias pelo CONTRATO\n"
        "e nunca pelo banco desta celula: o motor por baixo pode mudar sem que\n"
        "quem consome saiba.\n"
        "\n"
        "Lei do assunto: docs/decisoes/PLANO-SEQUENCIAS-DE-MENSAGENS.md.\n"
        "\n"
        "NADA DE DADO PESSOAL SAI POR AQUI: nem e-mail, nem nome, nem telefone.\n"
        "So o `destinatario_id`, que e o id OPACO de plataforma emitido pela\n"
        "celula identidade. Esta celula nem guarda o e-mail de ninguem: ela o\n"
        "pergunta a identidade na hora do envio.\n"
        "\n"
        "ESCREVER AQUI SIGNIFICA PUBLICAR VERSAO NOVA. Versao publicada e\n"
        "imutavel por gatilho no Postgres, e quem esta no meio de uma sequencia\n"
        "termina na versao em que entrou. A porta devolve o numero da versao\n"
        "que nasceu, para a tela poder dizer isso em portugues simples.\n"
    ),
    servers=[{"url": "http://mensageria:8000/api/mensageria"}],
    auth=bearerAuth(),
    openapi_extra={"security": [{"bearerAuth": []}]},
)
api.add_router("", mensageria_router)
