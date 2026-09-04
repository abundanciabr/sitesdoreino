"""Guardas da porta de leitura (`/api/metricas`) — o degrau 7.4.

Por que ela precisa de guarda próprio, e forte: uma porta de máquina é a
superfície mais fácil de estragar do sistema, porque ninguém olha para ela. Não
tem tela, não tem link, não aparece no navegador de ninguém. Uma operação nova
sem cadeado fica verde, e um campo a mais num Schema não quebra página nenhuma.

AS CINCO COISAS QUE ESTE ARQUIVO PROVA
--------------------------------------
1. **Fechada por padrão.** Sem token, com token errado ou com o env ausente é
   401 em TODA operação, e a lista de operações é MEDIDA do schema vivo, nunca
   digitada. Operação nova sem cadeado reprova sozinha.
2. **A sonda continua aberta.** `/healthz` responde sem token: o healthcheck do
   compose não tem crachá, e uma porta que o fechasse derrubaria a célula no
   deploy, com o erro aparecendo longe da causa.
3. **O dia é o de São Paulo.** Um fato das 22h30 do dia 30 conta no dia 30, e
   não no dia 1 do mês seguinte. É a conta que decide em que mês uma pessoa
   entrou, e é a mesma que o placar faz do outro lado (`armadilhas/099`).
4. **A fronteira de site fecha (Lei 9).** Fato de outro site não entra em
   contagem nem em cobertura, nem por engano nem por soma.
5. **Ausência não vira zero.** Dia sem fato não aparece na contagem, e assunto
   que nunca chegou não aparece na cobertura. É a diferença entre "medi e deu
   zero" e "não medi", e é a lei desta célula.

O CENÁRIO TEM DENTE, DE PROPÓSITO
---------------------------------
Ele inclui um fato de OUTRO site, um fato de outro assunto, um dia vazio no
meio do intervalo e um evento morto. Um cenário só com o caso feliz passaria
mesmo se o filtro de site não existisse, se a contagem ignorasse o `tipo` e se
a fila de mortos devolvesse o corpo cru para todo mundo.
"""

from __future__ import annotations

import datetime as dt
import uuid
from zoneinfo import ZoneInfo

import pytest
from django.test import Client

from apps.fatos.models import Evento, EventoMorto

pytestmark = pytest.mark.django_db

BASE = "/api/metricas"
TOKEN = "token-do-par-admin"
SITE = "site-da-escola"
OUTRO_SITE = "site-de-outra-escola"
SP = ZoneInfo("America/Sao_Paulo")

CADASTRO = "identidade.pessoa-cadastrada"
QUIZ = "quiz.completado"


@pytest.fixture(autouse=True)
def par_autorizado(settings):
    settings.TOKENS_ACEITOS = {TOKEN}


def pedir(caminho: str, token: str | None = TOKEN):
    cabecalhos = {}
    if token:
        cabecalhos["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return Client().get(f"{BASE}{caminho}", **cabecalhos)


def gravar(tipo: str, quando: dt.datetime, site: str = SITE) -> Evento:
    return Evento.objects.create(
        event_id=uuid.uuid4(),
        tipo=tipo,
        versao=1,
        site_id=site,
        ocorrido_em=quando,
        dados={"site_id": site},
    )


def operacoes_da_porta() -> list[tuple[str, str]]:
    """Toda operação do schema VIVO, com os parâmetros de caminho preenchidos.

    Medida, e não digitada: é isto que faz o guarda de 401 alcançar a operação
    que alguém acrescentar amanhã sem ler este arquivo.

    O import mora aqui dentro, e não no topo, porque esta função roda na COLETA
    do pytest: importar a API no topo do módulo a construiria antes de o
    pytest-django terminar de configurar o Django.

    A medição é do schema VIVO porque o contrato congelado ainda não existe: ele
    nasce pelo `RITOS.md` §3, e a ordem porta-antes-de-contrato é obrigatória
    (`armadilhas/228`). Quando ele existir, esta função passa a ler o congelado,
    porque é contra a PROMESSA que o cadeado precisa valer.
    """
    from config.api import api

    schema = api.get_openapi_schema(path_prefix="")
    return [
        (metodo, caminho.replace("{morto_id}", "1"))
        for caminho, item in schema["paths"].items()
        for metodo in item
    ]


# ---------------------------------------------------------------------------
# 1. Fechada por padrão
# ---------------------------------------------------------------------------


def test_o_schema_vivo_tem_as_quatro_operacoes():
    """Se este número mudar, o teste de 401 abaixo mudou de escopo junto."""
    assert len(operacoes_da_porta()) == 4


@pytest.mark.parametrize("metodo,caminho", operacoes_da_porta())
def test_toda_operacao_recusa_sem_token(metodo, caminho):
    resposta = Client().generic(metodo.upper(), f"{BASE}{caminho}")
    assert resposta.status_code == 401, f"{metodo} {caminho} respondeu sem token"


@pytest.mark.parametrize("metodo,caminho", operacoes_da_porta())
def test_toda_operacao_recusa_token_errado(metodo, caminho):
    resposta = Client().generic(
        metodo.upper(),
        f"{BASE}{caminho}",
        HTTP_AUTHORIZATION="Bearer token-de-quem-nao-e-da-casa",
    )
    assert resposta.status_code == 401, f"{metodo} {caminho} aceitou token errado"


def test_env_ausente_fecha_a_porta_para_todo_mundo(settings):
    """Sem `TOKENS_ACEITOS_*` no env, o conjunto nasce vazio e ninguém entra.

    É o modo de falha que importa: a célula sobe antes de o token existir, e uma
    porta que se abrisse "porque não há lista" ficaria aberta justamente na
    janela em que ninguém está olhando.
    """
    settings.TOKENS_ACEITOS = set()
    assert pedir(f"/cobertura?site_id={SITE}").status_code == 401


def test_a_sonda_continua_aberta():
    """O healthcheck do compose não tem crachá, e não pode passar a precisar de um."""
    assert Client().get("/healthz").status_code == 200


# ---------------------------------------------------------------------------
# 2. Contagens
# ---------------------------------------------------------------------------


def test_conta_por_dia_so_o_assunto_e_o_site_pedidos():
    gravar(CADASTRO, dt.datetime(2026, 9, 2, 10, 0, tzinfo=SP))
    gravar(CADASTRO, dt.datetime(2026, 9, 2, 11, 0, tzinfo=SP))
    gravar(CADASTRO, dt.datetime(2026, 9, 4, 9, 0, tzinfo=SP))
    gravar(QUIZ, dt.datetime(2026, 9, 2, 12, 0, tzinfo=SP))
    gravar(CADASTRO, dt.datetime(2026, 9, 2, 13, 0, tzinfo=SP), site=OUTRO_SITE)

    corpo = pedir(
        f"/contagens?site_id={SITE}&tipo={CADASTRO}&de=2026-09-01&ate=2026-09-30"
    ).json()

    assert corpo["total"] == 3
    assert corpo["por_dia"] == [
        {"dia": "2026-09-02", "quantidade": 2},
        {"dia": "2026-09-04", "quantidade": 1},
    ], "o dia 3, sem fato, não pode aparecer como zero"


def test_sem_tipo_conta_todos_os_assuntos_do_site():
    gravar(CADASTRO, dt.datetime(2026, 9, 2, 10, 0, tzinfo=SP))
    gravar(QUIZ, dt.datetime(2026, 9, 2, 12, 0, tzinfo=SP))
    gravar(CADASTRO, dt.datetime(2026, 9, 2, 13, 0, tzinfo=SP), site=OUTRO_SITE)

    corpo = pedir(f"/contagens?site_id={SITE}&de=2026-09-01&ate=2026-09-30").json()

    assert corpo["total"] == 2


def test_o_dia_e_o_de_sao_paulo_e_nao_o_de_utc():
    """22h30 do dia 30 em São Paulo é 01h30 do dia 1 em UTC.

    Com o fuso errado esta pessoa cairia no mês seguinte, sem erro em lugar
    nenhum, e a meta do mantenedor mediria outra coisa (`armadilhas/099`).
    """
    gravar(CADASTRO, dt.datetime(2026, 9, 30, 22, 30, tzinfo=SP))

    setembro = pedir(f"/contagens?site_id={SITE}&de=2026-09-01&ate=2026-09-30").json()
    outubro = pedir(f"/contagens?site_id={SITE}&de=2026-10-01&ate=2026-10-31").json()

    assert setembro["total"] == 1
    assert outubro["total"] == 0


def test_intervalo_invertido_e_recusado():
    resposta = pedir(f"/contagens?site_id={SITE}&de=2026-09-30&ate=2026-09-01")
    assert resposta.status_code == 422
    assert "invertido" in resposta.json()["detail"]


def test_intervalo_maior_que_o_teto_e_recusado():
    resposta = pedir(f"/contagens?site_id={SITE}&de=2020-01-01&ate=2026-09-30")
    assert resposta.status_code == 422
    assert "pedaços" in resposta.json()["detail"]


# ---------------------------------------------------------------------------
# 3. Cobertura
# ---------------------------------------------------------------------------


def test_cobertura_diz_de_cada_assunto_quantos_e_quando_foi_o_ultimo():
    gravar(CADASTRO, dt.datetime(2026, 9, 1, 10, 0, tzinfo=SP))
    gravar(CADASTRO, dt.datetime(2026, 9, 3, 10, 0, tzinfo=SP))
    gravar(QUIZ, dt.datetime(2026, 9, 2, 10, 0, tzinfo=SP))
    gravar(CADASTRO, dt.datetime(2026, 9, 4, 10, 0, tzinfo=SP), site=OUTRO_SITE)

    corpo = pedir(f"/cobertura?site_id={SITE}").json()
    por_tipo = {linha["tipo"]: linha for linha in corpo["tipos"]}

    assert set(por_tipo) == {CADASTRO, QUIZ}, "assunto de outro site vazou"
    assert por_tipo[CADASTRO]["quantidade"] == 2
    assert por_tipo[CADASTRO]["celula"] == "identidade"
    assert por_tipo[CADASTRO]["ultimo_ocorrido_em"].startswith("2026-09-03")


def test_assunto_que_nunca_chegou_nao_aparece_como_zero():
    """A ausência é a resposta, e quem compara com o esperado é a `admin`."""
    gravar(CADASTRO, dt.datetime(2026, 9, 1, 10, 0, tzinfo=SP))

    corpo = pedir(f"/cobertura?site_id={SITE}").json()

    assert [linha["tipo"] for linha in corpo["tipos"]] == [CADASTRO]


# ---------------------------------------------------------------------------
# 4. A fila de eventos mortos
# ---------------------------------------------------------------------------


def morto(motivo: str = "o corpo não é JSON válido") -> EventoMorto:
    return EventoMorto.objects.create(
        corpo='{"event": "quiz.completado", quebrado',
        motivo=motivo,
        tipo_declarado="quiz.completado",
    )


def test_a_lista_de_mortos_nao_carrega_o_corpo_cru():
    """O corpo pode conter o que esta casa não guarda; em lote, seria espalhar."""
    morto()

    corpo = pedir("/eventos-mortos").json()

    assert corpo["total"] == 1
    assert "corpo" not in corpo["itens"][0]
    assert corpo["itens"][0]["motivo"].startswith("o corpo não é JSON")


def test_inspecionar_um_morto_traz_o_corpo():
    alvo = morto()

    corpo = pedir(f"/eventos-mortos/{alvo.id}").json()

    assert corpo["corpo"] == '{"event": "quiz.completado", quebrado'


def test_morto_que_nao_existe_e_404_e_nao_resposta_vazia():
    assert pedir("/eventos-mortos/4242").status_code == 404


def test_o_cursor_anda_do_mais_novo_para_o_mais_velho_sem_repetir():
    primeiro, segundo, terceiro = morto(), morto(), morto()

    pagina1 = pedir("/eventos-mortos?limite=2").json()
    pagina2 = pedir(f"/eventos-mortos?limite=2&apos={pagina1['proximo_cursor']}").json()

    assert [item["id"] for item in pagina1["itens"]] == [terceiro.id, segundo.id]
    assert [item["id"] for item in pagina2["itens"]] == [primeiro.id]
    assert pagina2["proximo_cursor"] is None
    assert pagina1["total"] == 3, "o total conta a fila inteira, não a página"


def test_estado_desconhecido_e_recusado_dizendo_quais_existem():
    resposta = pedir("/eventos-mortos?estado=resolvido")

    assert resposta.status_code == 422
    assert "descartado" in resposta.json()["detail"]


def test_limite_fora_da_faixa_e_recusado():
    assert pedir("/eventos-mortos?limite=0").status_code == 422
    assert pedir("/eventos-mortos?limite=201").status_code == 422
