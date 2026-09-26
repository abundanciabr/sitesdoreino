"""Guardas da porta de leitura (`/api/metricas`) — o degrau 7.4.

Por que ela precisa de guarda próprio, e forte: uma porta de máquina é a
superfície mais fácil de estragar do sistema, porque ninguém olha para ela. Não
tem tela, não tem link, não aparece no navegador de ninguém. Uma operação nova
sem cadeado fica verde, e um campo a mais num Schema não quebra página nenhuma.

AS SETE COISAS QUE ESTE ARQUIVO PROVA
-------------------------------------
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
6. **A contagem de conquistas não oferece total geral.** `pessoa` e `matricula`
   são vocabulários de identidade diferentes, e a resposta não tem nenhum campo
   que os atravesse. Somar maçãs com laranjas passa a exigir uma decisão de quem
   consome, em vez de acontecer por acidente (`armadilhas/303`).
7. **Sujeito sem conquista é 200 com lista vazia, nunca 404.** Esta célula não
   conhece cadastro nenhum: ela sabe o que os fatos trouxeram, e "não tenho
   marco para este id" não é o mesmo que "este sujeito não existe".

O CENÁRIO TEM DENTE, DE PROPÓSITO
---------------------------------
Ele inclui um fato de OUTRO site, um fato de outro assunto, um dia vazio no
meio do intervalo e um evento morto. Um cenário só com o caso feliz passaria
mesmo se o filtro de site não existisse, se a contagem ignorasse o `tipo` e se
a fila de mortos devolvesse o corpo cru para todo mundo.

No cenário de marcos o dente é o mesmo id em DOIS vocabulários: `sujeito-1`
existe como pessoa e como matrícula, com conquistas diferentes. Um cenário sem
essa colisão passaria mesmo se a porta ignorasse o `sujeito_tipo` por inteiro,
que é exatamente a mistura que o contrato proíbe.
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from zoneinfo import ZoneInfo

import pytest
from django.test import Client

from apps.fatos.models import Evento, EventoMorto, Marco
from apps.fatos.recepcao import GUARDADO, JA_TINHA, receber

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


def test_o_schema_vivo_tem_as_sete_operacoes():
    """Se este número mudar, o teste de 401 abaixo mudou de escopo junto."""
    assert len(operacoes_da_porta()) == 7


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


# ---------------------------------------------------------------------------
# 5. As conquistas (marcos)
# ---------------------------------------------------------------------------

#: O mesmo texto de id em dois vocabulários de identidade. É o dente do cenário
#: de marcos: com ele, uma porta que ignorasse `sujeito_tipo` some as duas
#: listas e nenhum caso feliz percebe.
ID_REPETIDO = "sujeito-1"


def marcar(sujeito_tipo: str, sujeito_id: str, tipo: str, dia: dt.date) -> Marco:
    return Marco.objects.create(
        sujeito_tipo=sujeito_tipo,
        sujeito_id=sujeito_id,
        tipo=tipo,
        dia=dia,
        event_id=uuid.uuid4(),
    )


def cenario_de_conquistas() -> None:
    """Dois vocabulários, três tipos, um dia vazio no meio e um fora da janela."""
    marcar(Marco.Sujeito.PESSOA, "p-1", Marco.Tipo.ENTROU_NO_SITE, dt.date(2026, 9, 2))
    marcar(Marco.Sujeito.PESSOA, "p-2", Marco.Tipo.ENTROU_NO_SITE, dt.date(2026, 9, 2))
    marcar(Marco.Sujeito.PESSOA, "p-3", Marco.Tipo.ENTROU_NO_SITE, dt.date(2026, 9, 4))
    marcar(
        Marco.Sujeito.PESSOA, "p-1", Marco.Tipo.ESCREVEU_NO_FORUM, dt.date(2026, 9, 4)
    )
    marcar(
        Marco.Sujeito.MATRICULA,
        "mat-1",
        Marco.Tipo.VIROU_ALUNO_COMPRANDO,
        dt.date(2026, 9, 2),
    )
    marcar(
        Marco.Sujeito.PESSOA, "p-9", Marco.Tipo.ENTROU_NO_SITE, dt.date(2026, 10, 20)
    )


def test_conta_as_conquistas_por_dia_dentro_de_cada_vocabulario():
    """Cada linha diz em que vocabulário foi contada, e o dia vazio não vira zero."""
    cenario_de_conquistas()

    corpo = pedir("/marcos/contagens?de=2026-09-01&ate=2026-09-30").json()
    por_linha = {
        (linha["sujeito_tipo"], linha["tipo"]): linha for linha in corpo["conquistas"]
    }

    assert set(por_linha) == {
        ("pessoa", "entrou-no-site"),
        ("pessoa", "escreveu-no-forum"),
        ("matricula", "virou-aluno-comprando"),
    }, "a conquista de outubro entrou numa janela de setembro"
    entrou = por_linha[("pessoa", "entrou-no-site")]
    assert entrou["total"] == 3
    assert entrou["por_dia"] == [
        {"dia": "2026-09-02", "quantidade": 2},
        {"dia": "2026-09-04", "quantidade": 1},
    ], "o dia 3, sem conquista, não pode aparecer como zero"


def test_a_contagem_nao_junta_o_mesmo_tipo_de_dois_vocabularios():
    """Duas linhas, e nunca uma só, quando o mesmo tipo existe nos dois lados.

    Nada na tabela impede isso: a chave única é (sujeito, id, tipo), e o dia em
    que uma derivação creditar a mesma conquista à pessoa E à matrícula, uma
    contagem agrupada só por `tipo` diria "2" onde a verdade são dois números de
    coisas diferentes. O guarda existe porque essa fusão não deixa erro nenhum
    para trás: o total fecha, e é o vocabulário que se perde.
    """
    marcar(
        Marco.Sujeito.PESSOA,
        "p-1",
        Marco.Tipo.VIROU_ALUNO_COMPRANDO,
        dt.date(2026, 9, 2),
    )
    marcar(
        Marco.Sujeito.MATRICULA,
        "mat-1",
        Marco.Tipo.VIROU_ALUNO_COMPRANDO,
        dt.date(2026, 9, 2),
    )

    corpo = pedir("/marcos/contagens?de=2026-09-01&ate=2026-09-30").json()

    assert sorted(linha["sujeito_tipo"] for linha in corpo["conquistas"]) == [
        "matricula",
        "pessoa",
    ], "os dois vocabulários caíram na mesma linha"
    assert [linha["total"] for linha in corpo["conquistas"]] == [1, 1]


def test_a_contagem_de_conquistas_nao_oferece_total_geral():
    """A ausência é o desenho: somar `pessoa` com `matricula` seria maçã com laranja.

    O guarda olha o CORPO inteiro, e não um campo nomeado, porque a forma de
    esta lei morrer é alguém acrescentar um `total` "por conveniência da tela" e
    ninguém reparar: quem consome somaria dois vocabulários de identidade sem
    nunca decidir somá-los (`armadilhas/303`).
    """
    cenario_de_conquistas()

    corpo = pedir("/marcos/contagens?de=2026-09-01&ate=2026-09-30").json()

    assert set(corpo) == {
        "sujeito_tipo",
        "tipo",
        "de",
        "ate",
        "conquistas",
    }, "a resposta ganhou um campo que atravessa os dois vocabulários"


def test_a_contagem_de_conquistas_filtra_por_vocabulario_e_por_tipo():
    cenario_de_conquistas()

    so_matricula = pedir(
        "/marcos/contagens?de=2026-09-01&ate=2026-09-30&sujeito_tipo=matricula"
    ).json()
    so_forum = pedir(
        "/marcos/contagens?de=2026-09-01&ate=2026-09-30&tipo=escreveu-no-forum"
    ).json()

    assert [linha["tipo"] for linha in so_matricula["conquistas"]] == [
        "virou-aluno-comprando"
    ]
    assert [linha["sujeito_tipo"] for linha in so_forum["conquistas"]] == ["pessoa"]


def test_a_contagem_de_conquistas_recusa_intervalo_invertido():
    resposta = pedir("/marcos/contagens?de=2026-09-30&ate=2026-09-01")

    assert resposta.status_code == 422
    assert "invertido" in resposta.json()["detail"]


def test_a_contagem_de_conquistas_recusa_janela_acima_do_teto():
    resposta = pedir("/marcos/contagens?de=2020-01-01&ate=2026-09-30")

    assert resposta.status_code == 422
    assert "pedaços" in resposta.json()["detail"]


def test_a_contagem_de_conquistas_recusa_vocabulario_desconhecido():
    """Vocabulário que não existe é recusa, e a recusa diz quais existem."""
    resposta = pedir(
        "/marcos/contagens?de=2026-09-01&ate=2026-09-30&sujeito_tipo=aluno"
    )

    assert resposta.status_code == 422
    assert "matricula" in resposta.json()["detail"]


def test_a_contagem_de_conquistas_recusa_conquista_desconhecida():
    resposta = pedir("/marcos/contagens?de=2026-09-01&ate=2026-09-30&tipo=virou-rico")

    assert resposta.status_code == 422
    assert "entrou-no-site" in resposta.json()["detail"]


def test_os_marcos_de_um_sujeito_vem_do_mais_antigo_para_o_mais_novo():
    """Com a linhagem junto: o `event_id` é o que permite conferir até o começo."""
    primeiro = marcar(
        Marco.Sujeito.PESSOA, "p-1", Marco.Tipo.ENTROU_NO_SITE, dt.date(2026, 9, 2)
    )
    depois = marcar(
        Marco.Sujeito.PESSOA, "p-1", Marco.Tipo.ESCREVEU_NO_FORUM, dt.date(2026, 9, 9)
    )

    corpo = pedir("/marcos?sujeito_tipo=pessoa&sujeito_id=p-1").json()

    assert [marco["tipo"] for marco in corpo["marcos"]] == [
        "entrou-no-site",
        "escreveu-no-forum",
    ]
    assert corpo["marcos"][0]["event_id"] == str(primeiro.event_id)
    assert corpo["marcos"][1]["event_id"] == str(depois.event_id)
    assert corpo["marcos"][0]["procedencia"] == "automatico"


def test_a_lista_de_marcos_nao_mistura_os_dois_vocabularios():
    """O mesmo id em dois vocabulários são dois sujeitos, e nunca se encontram."""
    marcar(
        Marco.Sujeito.PESSOA,
        ID_REPETIDO,
        Marco.Tipo.ENTROU_NO_SITE,
        dt.date(2026, 9, 2),
    )
    marcar(
        Marco.Sujeito.MATRICULA,
        ID_REPETIDO,
        Marco.Tipo.VIROU_ALUNO_COMPRANDO,
        dt.date(2026, 9, 3),
    )

    pessoa = pedir(f"/marcos?sujeito_tipo=pessoa&sujeito_id={ID_REPETIDO}").json()
    matricula = pedir(f"/marcos?sujeito_tipo=matricula&sujeito_id={ID_REPETIDO}").json()

    assert [marco["tipo"] for marco in pessoa["marcos"]] == ["entrou-no-site"]
    assert [marco["tipo"] for marco in matricula["marcos"]] == ["virou-aluno-comprando"]


def test_sujeito_sem_conquista_e_200_com_lista_vazia_e_nunca_404():
    """Esta célula não conhece cadastro: 404 afirmaria que o sujeito não existe."""
    resposta = pedir("/marcos?sujeito_tipo=pessoa&sujeito_id=nunca-fez-nada")

    assert resposta.status_code == 200
    assert resposta.json()["marcos"] == []


def test_a_lista_de_marcos_recusa_vocabulario_desconhecido():
    resposta = pedir("/marcos?sujeito_tipo=aluno&sujeito_id=p-1")

    assert resposta.status_code == 422
    assert "pessoa" in resposta.json()["detail"]


def test_a_lista_de_marcos_exige_as_duas_partes_do_sujeito():
    """Id sozinho é ambíguo, e ambiguidade aqui vira contagem errada de gente."""
    assert pedir("/marcos?sujeito_id=p-1").status_code == 422
    assert pedir("/marcos?sujeito_tipo=pessoa").status_code == 422


# ---------------------------------------------------------------------------
# 6. O funil de vendas (`countFunnel`)
# ---------------------------------------------------------------------------

FUNIL_PAGINA_VISTA = "funil.pagina-vista"
FUNIL_SECAO_VISTA = "funil.secao-vista"
FUNIL_CTA_CLICADO = "funil.cta-clicado"
FUNIL_LEAD_CAPTURADO = "funil.lead-capturado"
CHECKOUT_PEDIDO_ATRIBUIDO = "checkout.pedido-atribuido"
CHECKOUT_PEDIDO_PAGO = "checkout.pedido-pago"


def visita(tipo: str, visitor_id: str, quando: dt.datetime, site: str = SITE, **extra) -> Evento:
    return Evento.objects.create(
        event_id=uuid.uuid4(),
        tipo=tipo,
        versao=1,
        site_id=site,
        ocorrido_em=quando,
        dados={"site_id": site, "visitor_id": visitor_id, **extra},
    )


def envelope_pagina_vista(event_id: uuid.UUID, visitor_id: str, quando: dt.datetime, site: str = SITE) -> str:
    return json.dumps(
        {
            "event": "funil.pagina-vista",
            "version": 1,
            "event_id": str(event_id),
            "occurred_at": quando.isoformat(),
            "data": {
                "site_id": site,
                "visitor_id": visitor_id,
                "pagina_slug": "oferta",
                "pagina_version": 1,
                "offer_slug": "mentoria",
            },
        }
    )


def por_passo(corpo: dict, chave: str = "passos") -> dict[str, int]:
    return {linha["passo"]: linha["visitantes"] for linha in corpo[chave]}


def test_funil_conta_por_site_e_nao_mistura_com_outro_site():
    visita(FUNIL_PAGINA_VISTA, "v1", dt.datetime(2026, 9, 2, 10, 0, tzinfo=SP))
    visita(FUNIL_PAGINA_VISTA, "v2", dt.datetime(2026, 9, 2, 10, 0, tzinfo=SP), site=OUTRO_SITE)
    visita(
        FUNIL_CTA_CLICADO,
        "v1",
        dt.datetime(2026, 9, 2, 11, 0, tzinfo=SP),
        secao="oferta",
        slot="cta_texto",
        destino="/checkout/mentoria",
    )
    visita(
        FUNIL_CTA_CLICADO,
        "v1",
        dt.datetime(2026, 9, 2, 12, 0, tzinfo=SP),
        secao="cubo",
        slot="cta_topo",
        destino="/perguntas",
    )

    corpo = pedir(f"/funil?de=2026-09-01&ate=2026-09-30&site_id={SITE}").json()

    passo = por_passo(corpo)
    assert passo["pagina_vista"] == 1, "a visita do outro site vazou"
    assert passo["cta_checkout"] == 1, "só o clique com destino /checkout/ conta"


def test_funil_visitante_com_duas_visitas_conta_uma_vez():
    visita(FUNIL_PAGINA_VISTA, "v1", dt.datetime(2026, 9, 2, 9, 0, tzinfo=SP))
    visita(FUNIL_PAGINA_VISTA, "v1", dt.datetime(2026, 9, 3, 9, 0, tzinfo=SP))

    corpo = pedir(f"/funil?de=2026-09-01&ate=2026-09-30&site_id={SITE}").json()

    assert por_passo(corpo)["pagina_vista"] == 1
    dias = {linha["dia"]: por_passo(linha, "passos") for linha in corpo["por_dia"]}
    assert dias["2026-09-02"]["pagina_vista"] == 1
    assert dias["2026-09-03"]["pagina_vista"] == 1


def test_funil_duplicata_de_event_id_nao_infla_a_contagem():
    """A mesma entrega duas vezes: a recepção guarda uma vez, e o funil conta um."""
    event_id = uuid.uuid4()
    corpo_bruto = envelope_pagina_vista(event_id, "visitante-duplicado", dt.datetime(2026, 9, 2, 10, 0, tzinfo=SP))

    primeiro, _ = receber(corpo_bruto)
    segundo, _ = receber(corpo_bruto)

    assert primeiro == GUARDADO
    assert segundo == JA_TINHA
    assert Evento.objects.filter(tipo=FUNIL_PAGINA_VISTA).count() == 1

    corpo = pedir(f"/funil?de=2026-09-01&ate=2026-09-30&site_id={SITE}").json()
    assert por_passo(corpo)["pagina_vista"] == 1


def test_funil_coleta_distingue_zero_de_sem_coleta():
    sem_nada = pedir(f"/funil?de=2026-09-01&ate=2026-09-30&site_id={SITE}").json()
    assert sem_nada["coleta"] == {"primeiro": None, "ultimo": None}
    assert all(linha["visitantes"] == 0 for linha in sem_nada["passos"])

    visita(FUNIL_PAGINA_VISTA, "v1", dt.datetime(2026, 9, 2, 9, 0, tzinfo=SP))

    com_coleta = pedir(f"/funil?de=2026-09-01&ate=2026-09-30&site_id={SITE}").json()
    assert com_coleta["coleta"]["primeiro"] is not None
    passo = por_passo(com_coleta)
    assert passo["pagina_vista"] == 1
    assert passo["lead_capturado"] == 0, "zero com a coleta de pé é medição, não ausência"


def test_funil_sem_experimento_nao_traz_variantes():
    corpo = pedir(f"/funil?de=2026-09-01&ate=2026-09-30&site_id={SITE}").json()
    assert corpo["variantes"] is None
    assert corpo["visitantes_com_bracos_trocados"] is None


def test_funil_variante_e_sticky_pela_primeira_visita_e_marca_a_troca():
    exp = "exp-1"
    visita(
        FUNIL_PAGINA_VISTA, "v1", dt.datetime(2026, 9, 2, 9, 0, tzinfo=SP),
        experimento_id=exp, variante_id="a",
    )
    visita(
        FUNIL_PAGINA_VISTA, "v1", dt.datetime(2026, 9, 3, 9, 0, tzinfo=SP),
        experimento_id=exp, variante_id="b",
    )
    visita(
        FUNIL_PAGINA_VISTA, "v2", dt.datetime(2026, 9, 2, 9, 0, tzinfo=SP),
        experimento_id=exp, variante_id="b",
    )

    corpo = pedir(
        f"/funil?de=2026-09-01&ate=2026-09-30&site_id={SITE}&experimento_id={exp}&secao=oferta"
    ).json()

    variantes = {v["variante_id"]: v for v in corpo["variantes"]}
    assert variantes["a"]["atribuidos"] == 1, "v1 ficou no braço da PRIMEIRA visita"
    assert variantes["b"]["atribuidos"] == 1, "só v2, que nasceu em b"
    assert corpo["visitantes_com_bracos_trocados"] == 1


def test_funil_convertido_que_nao_foi_exposto_nao_conta():
    exp = "exp-1"
    visita(
        FUNIL_PAGINA_VISTA, "v1", dt.datetime(2026, 9, 2, 9, 0, tzinfo=SP),
        experimento_id=exp, variante_id="a",
    )
    visita(
        FUNIL_CTA_CLICADO, "v1", dt.datetime(2026, 9, 2, 10, 0, tzinfo=SP),
        experimento_id=exp, variante_id="a", secao="oferta", slot="cta_texto",
        destino="/checkout/mentoria",
    )

    corpo = pedir(
        f"/funil?de=2026-09-01&ate=2026-09-30&site_id={SITE}&experimento_id={exp}&secao=oferta"
    ).json()

    variante_a = next(v for v in corpo["variantes"] if v["variante_id"] == "a")
    assert variante_a["expostos"] == 0, "v1 nunca teve secao-vista da seção do experimento"
    assert variante_a["convertidos"] == 0, "clicou sem ter sido exposto: não é conversão deste teste"


def test_funil_expostos_e_convertidos_contam_pelo_braco_fixado_e_nao_pelo_evento():
    """Emenda 1 §5: a `secao-vista` chega com o `variante_id` errado, e não muda o braço."""
    exp = "exp-1"
    visita(
        FUNIL_PAGINA_VISTA, "v1", dt.datetime(2026, 9, 2, 9, 0, tzinfo=SP),
        experimento_id=exp, variante_id="a",
    )
    visita(
        FUNIL_SECAO_VISTA, "v1", dt.datetime(2026, 9, 2, 9, 5, tzinfo=SP),
        experimento_id=exp, variante_id="b", secao="oferta",
    )
    visita(
        FUNIL_CTA_CLICADO, "v1", dt.datetime(2026, 9, 2, 9, 10, tzinfo=SP),
        experimento_id=exp, variante_id="b", secao="oferta", slot="cta_texto",
        destino="/checkout/mentoria",
    )

    corpo = pedir(
        f"/funil?de=2026-09-01&ate=2026-09-30&site_id={SITE}&experimento_id={exp}&secao=oferta"
    ).json()

    variante_a = next(v for v in corpo["variantes"] if v["variante_id"] == "a")
    assert variante_a["expostos"] == 1
    assert variante_a["convertidos"] == 1
    assert not any(v["variante_id"] == "b" for v in corpo["variantes"]), (
        "v1 nunca teve pagina-vista em b: b não tem atribuído nenhum"
    )


def test_funil_junta_pedidos_por_visitor_id_dentro_da_janela_de_atribuicao():
    exp = "exp-1"
    visita(
        FUNIL_PAGINA_VISTA, "v1", dt.datetime(2026, 9, 5, 9, 0, tzinfo=SP),
        experimento_id=exp, variante_id="a",
    )
    visita(
        FUNIL_PAGINA_VISTA, "v2", dt.datetime(2026, 9, 5, 9, 0, tzinfo=SP),
        experimento_id=exp, variante_id="a",
    )
    # v1: um pedido ANTES da primeira visita (compra antiga, não é efeito do braço)
    # e um pedido DEPOIS (esse conta).
    visita(CHECKOUT_PEDIDO_ATRIBUIDO, "v1", dt.datetime(2026, 9, 4, 10, 0, tzinfo=SP))
    visita(CHECKOUT_PEDIDO_ATRIBUIDO, "v1", dt.datetime(2026, 9, 6, 10, 0, tzinfo=SP))
    visita(CHECKOUT_PEDIDO_PAGO, "v1", dt.datetime(2026, 9, 7, 10, 0, tzinfo=SP))
    # v2: só um pedido ANTES da primeira visita: não deve contar.
    visita(CHECKOUT_PEDIDO_ATRIBUIDO, "v2", dt.datetime(2026, 9, 3, 10, 0, tzinfo=SP))

    corpo = pedir(
        f"/funil?de=2026-09-01&ate=2026-09-30&site_id={SITE}&experimento_id={exp}&secao=oferta"
    ).json()

    variante_a = next(v for v in corpo["variantes"] if v["variante_id"] == "a")
    assert variante_a["atribuidos"] == 2
    passo = por_passo(variante_a)
    assert passo["pedido_atribuido"] == 1, "só v1, e só pelo pedido de DEPOIS da visita"
    assert passo["pedido_pago"] == 1


def test_funil_intervalo_invertido_e_recusado():
    resposta = pedir("/funil?de=2026-09-30&ate=2026-09-01")
    assert resposta.status_code == 422
    assert "invertido" in resposta.json()["detail"]


def test_funil_janela_maior_que_o_teto_e_recusada():
    resposta = pedir("/funil?de=2020-01-01&ate=2026-09-30")
    assert resposta.status_code == 422
    assert "pedaços" in resposta.json()["detail"]


def test_funil_experimento_sem_secao_e_recusado():
    resposta = pedir("/funil?de=2026-09-01&ate=2026-09-30&experimento_id=exp-1")
    assert resposta.status_code == 422
    assert "juntos" in resposta.json()["detail"]


def test_funil_secao_sem_experimento_e_recusada():
    resposta = pedir("/funil?de=2026-09-01&ate=2026-09-30&secao=oferta")
    assert resposta.status_code == 422
    assert "juntos" in resposta.json()["detail"]
