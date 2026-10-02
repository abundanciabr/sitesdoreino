# tests/test_experimentos.py
# O experimento mora na pagina: variantes congeladas fora do rascunho, um so
# ativo por pagina (garantido pelo banco, inclusive em corrida), transicoes
# validas e o getPage que so muda quando ha experimento no ar.
import threading

import pytest
from django.db import IntegrityError, connection, transaction

from apps.paginas.models import (
    Experimento,
    Page,
    PageDraft,
    Variante,
    VarianteCongelada,
)
from apps.sites.models import Site

HEADLINE = "Aprenda a fazer som de estudio"
NOVA = "O som de estudio, do seu quarto"


@pytest.fixture
def token(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


def _publicar(pagina, headline=HEADLINE):
    rascunho, _ = PageDraft.objects.get_or_create(page=pagina)
    rascunho.secoes = [{"nome": "cubo", "ordem": 0, "slots": {"headline": headline}}]
    rascunho.save()
    return pagina.publicar()


@pytest.fixture
def pagina(db):
    site = Site.objects.create(host="experimento.com.br", name="Exp", active=True)
    pagina = Page.objects.create(site=site, slug="oferta")
    _publicar(pagina)
    return pagina


def _base(pagina):
    return f"/api/catalogo/sites/{pagina.site_id}/paginas/{pagina.slug}"


def _corpo(**mudancas):
    corpo = {
        "secao": "cubo",
        "slot": "headline",
        "hipotese": "Falar do quarto aproxima quem ainda nao tem estudio",
        "metrica_principal": "cta_checkout",
        "taxa_base": 0.10,
        "mde": 0.02,
        "dias_planejados": 14,
        "variantes": [
            {"variante_id": "a", "peso": 5000},
            {"variante_id": "b", "peso": 5000, "valor": NOVA},
        ],
    }
    corpo.update(mudancas)
    return corpo


def _criar(client, token, pagina, **mudancas):
    return client.post(
        f"{_base(pagina)}/experimentos",
        data=_corpo(**mudancas),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )


def _estado(client, token, pagina, experimento_id, **corpo):
    return client.post(
        f"{_base(pagina)}/experimentos/{experimento_id}/estado",
        data=corpo,
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )


def _get(client, token, url):
    return client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")


def _experimento_no_banco(pagina, estado=Experimento.RASCUNHO):
    experimento = Experimento.objects.create(
        page=pagina,
        secao="cubo",
        slot="headline",
        hipotese="h",
        metrica_principal="cta_checkout",
        taxa_base=0.1,
        mde=0.02,
        n_por_braco_planejado=3841,
        dias_planejados=14,
    )
    Variante.objects.create(
        experimento=experimento, variante_id="a", peso=5000, valor=HEADLINE
    )
    Variante.objects.create(
        experimento=experimento, variante_id="b", peso=5000, valor=NOVA
    )
    if estado != Experimento.RASCUNHO:
        Experimento.objects.filter(pk=experimento.pk).update(estado=estado)
        experimento.refresh_from_db()
    return experimento


# --- criar ---------------------------------------------------------------------


def test_criar_nasce_em_rascunho_com_o_controle_publicado(client, token, pagina):
    resp = _criar(client, token, pagina)

    assert resp.status_code == 201, resp.content
    corpo = resp.json()
    assert corpo["estado"] == "rascunho"
    assert corpo["n_por_braco_planejado"] == 3841
    assert corpo["iniciado_em"] is None and corpo["fim_planejado"] is None
    assert corpo["decisao"] is None and corpo["vencedora"] is None
    assert corpo["variantes"] == [
        {"variante_id": "a", "peso": 5000, "valor": HEADLINE},
        {"variante_id": "b", "peso": 5000, "valor": NOVA},
    ]


@pytest.mark.parametrize(
    "mudancas, trecho",
    [
        ({"secao": "rodape"}, "seção desconhecida"),
        ({"slot": "preco_texto"}, "slot desconhecido"),
        (
            {
                "variantes": [
                    {"variante_id": "a", "peso": 5000},
                    {"variante_id": "b", "peso": 4000, "valor": NOVA},
                ]
            },
            "somam 9000",
        ),
        (
            {
                "variantes": [
                    {"variante_id": "b", "peso": 5000, "valor": NOVA},
                    {"variante_id": "c", "peso": 5000, "valor": "outro"},
                ]
            },
            "falta a variante 'a'",
        ),
        (
            {
                "variantes": [
                    {"variante_id": "a", "peso": 5000, "valor": "texto inventado"},
                    {"variante_id": "b", "peso": 5000, "valor": NOVA},
                ]
            },
            "não recebe outro",
        ),
        (
            {
                "variantes": [
                    {"variante_id": "a", "peso": 5000},
                    {"variante_id": "b", "peso": 5000, "valor": "  "},
                ]
            },
            "está sem texto",
        ),
        (
            {
                "variantes": [
                    {"variante_id": "a", "peso": 5000},
                    {"variante_id": "a", "peso": 5000},
                ]
            },
            "uma vez só",
        ),
        ({"taxa_base": 0.9, "mde": 0.1}, "passa de 100%"),
    ],
)
def test_criar_incoerente_e_422_e_nada_e_gravado(
    client, token, pagina, mudancas, trecho
):
    # guarda: services/catalogo/apps/paginas/api.py:780
    resp = _criar(client, token, pagina, **mudancas)

    assert resp.status_code == 422
    assert trecho in resp.json()["detail"]
    assert not Experimento.objects.exists()


def test_criar_em_slot_vazio_na_versao_publicada_e_409(client, token, pagina):
    resp = _criar(client, token, pagina, slot="subheadline")

    assert resp.status_code == 409
    assert "está vazio na versão 1" in resp.json()["detail"]
    assert not Experimento.objects.exists()


def test_criar_em_pagina_nunca_publicada_e_409(client, token, pagina):
    inedita = Page.objects.create(site=pagina.site, slug="inedita")

    resp = _criar(client, token, inedita)

    assert resp.status_code == 409
    assert "ainda não foi publicada" in resp.json()["detail"]


def test_ler_e_listar_pela_porta(client, token, pagina):
    criado = _criar(client, token, pagina).json()

    lido = _get(client, token, f"{_base(pagina)}/experimentos/{criado['id']}")
    lista = _get(client, token, f"{_base(pagina)}/experimentos")

    assert lido.status_code == 200 and lido.json() == criado
    assert lista.status_code == 200 and lista.json() == [criado]
    # guarda: services/catalogo/apps/paginas/api.py:719
    assert (
        _get(client, token, f"{_base(pagina)}/experimentos/nao-e-uuid").status_code
        == 404
    )


# --- transicoes --------------------------------------------------------------


def test_ativar_encerrar_e_repetir_e_idempotente(client, token, pagina):
    exp_id = _criar(client, token, pagina).json()["id"]

    ativo = _estado(client, token, pagina, exp_id, estado="ativo")
    de_novo = _estado(client, token, pagina, exp_id, estado="ativo")

    assert ativo.status_code == 200 and ativo.json()["estado"] == "ativo"
    assert ativo.json()["fim_planejado"] is not None
    assert de_novo.status_code == 200 and de_novo.json() == ativo.json()

    fim = _estado(
        client,
        token,
        pagina,
        exp_id,
        estado="encerrado",
        decisao="promover",
        vencedora="b",
    )
    fim_de_novo = _estado(
        client,
        token,
        pagina,
        exp_id,
        estado="encerrado",
        decisao="promover",
        vencedora="b",
    )
    outra_decisao = _estado(
        client, token, pagina, exp_id, estado="encerrado", decisao="reverter"
    )

    assert fim.status_code == 200
    assert (fim.json()["decisao"], fim.json()["vencedora"]) == ("promover", "b")
    assert fim_de_novo.status_code == 200 and fim_de_novo.json() == fim.json()
    assert outra_decisao.status_code == 409
    assert _estado(client, token, pagina, exp_id, estado="ativo").status_code == 409


def test_encerrado_nao_reativa_retomar_e_experimento_novo(client, token, pagina):
    # Encerrado sai direto do banco (bypassa a transição rascunho->ativo), para
    # que a única passagem pelo mapa de transições, nesta prova, seja a que
    # tenta reabrir um experimento encerrado.
    experimento = _experimento_no_banco(pagina, Experimento.ENCERRADO)

    # guarda: services/catalogo/apps/paginas/models.py:269
    resp = _estado(client, token, pagina, experimento.id, estado="ativo")

    assert resp.status_code == 409
    assert Experimento.objects.get(pk=experimento.id).estado == Experimento.ENCERRADO


def test_rascunho_pode_ser_encerrado_sem_ir_ao_ar(client, token, pagina):
    exp_id = _criar(client, token, pagina).json()["id"]

    resp = _estado(
        client, token, pagina, exp_id, estado="encerrado", decisao="encerrar"
    )

    assert resp.status_code == 200
    assert resp.json()["iniciado_em"] is None


@pytest.mark.parametrize(
    "corpo, trecho",
    [
        ({"estado": "encerrado"}, "diga a decisão"),
        ({"estado": "encerrado", "decisao": "promover"}, "qual variante venceu"),
        (
            {"estado": "encerrado", "decisao": "promover", "vencedora": "z"},
            "não é variante",
        ),
        ({"estado": "ativo", "decisao": "promover"}, "só se mandam ao encerrar"),
    ],
)
def test_mudanca_incoerente_e_422(client, token, pagina, corpo, trecho):
    exp_id = _criar(client, token, pagina).json()["id"]

    # guarda: services/catalogo/apps/paginas/api.py:905
    # guarda: services/catalogo/apps/paginas/api.py:911
    resp = _estado(client, token, pagina, exp_id, **corpo)

    assert resp.status_code == 422
    assert trecho in resp.json()["detail"]
    assert Experimento.objects.get(pk=exp_id).estado == "rascunho"


def test_pausa_nao_existe(client, token, pagina):
    exp_id = _criar(client, token, pagina).json()["id"]
    _estado(client, token, pagina, exp_id, estado="ativo")

    # guarda: services/catalogo/apps/paginas/api.py:635
    resp = _estado(client, token, pagina, exp_id, estado="pausado")

    assert resp.status_code == 422
    assert Experimento.objects.get(pk=exp_id).estado == "ativo"


def test_ativar_confere_o_controle_com_o_texto_publicado_de_agora(
    client, token, pagina
):
    exp_id = _criar(client, token, pagina).json()["id"]
    _publicar(pagina, "Headline republicada")

    resp = _estado(client, token, pagina, exp_id, estado="ativo")

    assert resp.json()["variantes"][0] == {
        "variante_id": "a",
        "peso": 5000,
        "valor": "Headline republicada",
    }


# --- um so ativo por pagina --------------------------------------------------


def test_segundo_ativo_na_mesma_pagina_e_409(client, token, pagina):
    primeiro = _criar(client, token, pagina).json()["id"]
    segundo = _criar(client, token, pagina).json()["id"]
    _estado(client, token, pagina, primeiro, estado="ativo")

    # guarda: services/catalogo/apps/paginas/api.py:963
    resp = _estado(client, token, pagina, segundo, estado="ativo")

    assert resp.status_code == 409
    assert "já há um experimento no ar" in resp.json()["detail"]
    assert Experimento.objects.get(pk=segundo).estado == "rascunho"


def test_o_banco_recusa_dois_ativos_na_mesma_pagina(pagina):
    _experimento_no_banco(pagina, Experimento.ATIVO)
    outro = _experimento_no_banco(pagina)

    with pytest.raises(IntegrityError), transaction.atomic():
        Experimento.objects.filter(pk=outro.pk).update(estado=Experimento.ATIVO)


@pytest.mark.django_db(transaction=True)
def test_duas_ativacoes_ao_mesmo_tempo_terminam_com_uma_so_no_ar(client, token):
    site = Site.objects.create(host="corrida.com.br", name="Corrida", active=True)
    pagina = Page.objects.create(site=site, slug="oferta-corrida")
    _publicar(pagina)
    ids = [_experimento_no_banco(pagina).id for _ in range(2)]
    largada = threading.Barrier(2)
    respostas = []

    def ativar(exp_id):
        try:
            largada.wait()
            # guarda: services/catalogo/apps/paginas/api.py:963
            respostas.append(
                _estado(client, token, pagina, exp_id, estado="ativo").status_code
            )
        finally:
            connection.close()

    corredores = [threading.Thread(target=ativar, args=(i,)) for i in ids]
    for corredor in corredores:
        corredor.start()
    for corredor in corredores:
        corredor.join()

    assert sorted(respostas) == [200, 409]
    assert Experimento.objects.filter(page=pagina, estado="ativo").count() == 1


# --- variante congelada ------------------------------------------------------


def test_variante_em_rascunho_ainda_se_edita(pagina):
    experimento = _experimento_no_banco(pagina)
    variante = experimento.variantes.get(variante_id="b")

    variante.valor = "outro texto"
    variante.save()

    assert Variante.objects.get(pk=variante.pk).valor == "outro texto"


@pytest.mark.parametrize("estado", [Experimento.ATIVO, Experimento.ENCERRADO])
def test_variante_fora_do_rascunho_nao_se_edita_nem_se_apaga(pagina, estado):
    experimento = _experimento_no_banco(pagina, estado)
    variante = experimento.variantes.get(variante_id="b")

    variante.valor = "reescrito"
    # guarda: services/catalogo/apps/paginas/models.py:387
    with pytest.raises(VarianteCongelada):
        variante.save()
    # guarda: services/catalogo/apps/paginas/models.py:392
    with pytest.raises(VarianteCongelada):
        variante.delete()
    # guarda: services/catalogo/apps/paginas/models.py:335
    with pytest.raises(VarianteCongelada):
        Variante.objects.filter(pk=variante.pk).update(valor="reescrito")
    with pytest.raises(VarianteCongelada):
        Variante.objects.filter(pk=variante.pk).delete()
    with pytest.raises(VarianteCongelada):
        Variante.objects.create(
            experimento=experimento, variante_id="c", peso=1, valor="x"
        )
    # guarda: services/catalogo/apps/paginas/models.py:321
    with pytest.raises(VarianteCongelada):
        experimento.delete()
    # guarda: services/catalogo/apps/paginas/models.py:246
    with pytest.raises(VarianteCongelada):
        Experimento.objects.filter(pk=experimento.pk).delete()

    assert Variante.objects.get(pk=variante.pk).valor == NOVA
    assert experimento.variantes.count() == 2


# --- getPage -------------------------------------------------------------------


def test_getpage_sem_experimento_nao_ganha_chave_nova(client, token, pagina):
    _experimento_no_banco(pagina)

    corpo = _get(client, token, _base(pagina)).json()

    assert set(corpo) == {
        "id",
        "site_id",
        "slug",
        "tipo",
        "version",
        "offer_slug",
        "published_at",
        "secoes",
    }


def test_getpage_devolve_so_o_experimento_ativo(client, token, pagina):
    _experimento_no_banco(pagina, Experimento.ENCERRADO)
    ativo = _experimento_no_banco(pagina, Experimento.ATIVO)

    corpo = _get(client, token, _base(pagina)).json()

    assert corpo["experimento_ativo"] == {
        "id": str(ativo.id),
        "secao": "cubo",
        "slot": "headline",
        "variantes": [
            {"variante_id": "a", "peso": 5000, "valor": HEADLINE},
            {"variante_id": "b", "peso": 5000, "valor": NOVA},
        ],
    }


def test_getpage_depois_de_encerrar_volta_ao_que_era(client, token, pagina):
    antes = _get(client, token, _base(pagina)).json()
    exp_id = _criar(client, token, pagina).json()["id"]
    _estado(client, token, pagina, exp_id, estado="ativo")
    _estado(client, token, pagina, exp_id, estado="encerrado", decisao="encerrar")

    depois = _get(client, token, _base(pagina)).json()

    assert depois == antes
