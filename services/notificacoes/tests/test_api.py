# tests/test_api.py  # [RECEITA:R1 v1]
"""As três rotas da porta de consulta — Fase 4 do sininho
(`contracts/notificacoes.openapi.yaml`, Rito de Contrato de 27/08/2026).

Um arquivo só para as três (`GET /resumo`, `GET /avisos`,
`POST /marcar-lidas`), em vez de um por rota: as três dividem o mesmo par de
perguntas — quem CHAMA (Bearer do par, `apps/core/auth.py`) e qual PESSOA
(`destinatario_id`) — e o orçamento de arquivos do PR (`armadilhas/035`)
soma o que já é grande com o consumer, o modelo e a migração. Cada seção
abaixo tem seu próprio bloco de fixtures locais e é independente das outras.

O teste de CUSTO (2 vs 200 avisos, `assertNumQueries`) mora à parte, em
`tests/test_volume_da_api.py` — é outra pergunta ("o custo cresce com o
tamanho da caixa?"), não "a rota está correta?", e merece o contraste que só
um arquivo próprio dá (mesma separação de `sugestoes/tests/test_volume_dos_avisos.py`).
"""

import base64
import json
import uuid

import pytest
from django.utils import timezone
from jsonschema import Draft202012Validator

from apps.notificacoes.models import (
    ContadorDeNaoLidos,
    Notificacao,
    NotificacaoArquivada,
)
from apps.notificacoes.services import guardar
from tests.conftest import (
    ALGUEM,
    EQUIPE,
    OUTRA,
    SITE,
    cabecalho_bearer,
    schema_da_resposta,
)

pytestmark = pytest.mark.django_db


def _guardar(destinatario_id=ALGUEM, site_id=SITE, ator_id=EQUIPE, **parametros):
    return guardar(
        site_id=site_id,
        destinatario_id=destinatario_id,
        ator_id=ator_id,
        assunto="sugestao.status-alterado",
        parametros=parametros or {"suggestion_id": "1"},
        origem_event_id=str(uuid.uuid4()),
    )


# =============================================================================
# GET /resumo — o número do sininho
# =============================================================================

CAMINHO_RESUMO = "/api/notificacoes/resumo"


def _perguntar_resumo(client, destinatario_id="", token="__default__"):
    params = {"destinatario_id": destinatario_id} if destinatario_id else {}
    cabecalhos = (
        cabecalho_bearer() if token == "__default__" else cabecalho_bearer(token)
    )
    return client.get(CAMINHO_RESUMO, params, headers=cabecalhos)


def test_resumo_sem_token_e_401(client, par_autorizado):
    resposta = _perguntar_resumo(client, destinatario_id=ALGUEM, token=None)
    assert resposta.status_code == 401


def test_resumo_token_errado_e_401(client, par_autorizado):
    resposta = _perguntar_resumo(
        client, destinatario_id=ALGUEM, token="token-de-outro-par"
    )
    assert resposta.status_code == 401


def test_resumo_sem_destinatario_id_e_422(client, par_autorizado):
    resposta = client.get(CAMINHO_RESUMO, headers=cabecalho_bearer())
    assert resposta.status_code == 422


def test_resumo_destinatario_id_vazio_e_422(client, par_autorizado):
    resposta = client.get(
        CAMINHO_RESUMO, {"destinatario_id": ""}, headers=cabecalho_bearer()
    )
    assert resposta.status_code == 422


def test_resumo_destinatario_id_so_espacos_e_422(client, par_autorizado):
    resposta = client.get(
        CAMINHO_RESUMO, {"destinatario_id": "   "}, headers=cabecalho_bearer()
    )
    assert resposta.status_code == 422


def test_resumo_pessoa_sem_nenhum_aviso_e_zero(client, par_autorizado):
    """Sem `ContadorDeNaoLidos` nenhum — nunca 404, nunca 500: zero é uma
    resposta normal (é o próprio estado de quem nunca recebeu nada)."""
    resposta = _perguntar_resumo(client, destinatario_id="ninguem-nunca-ouviu-falar")
    assert resposta.status_code == 200
    assert resposta.json() == {"nao_lidas": 0}


def test_resumo_conta_bate_com_os_avisos_realmente_nao_lidos(client, par_autorizado):
    for _ in range(3):
        _guardar()
    lida = _guardar()
    lida.lido_em = timezone.now()
    lida.save(update_fields=["lido_em"])
    _guardar(destinatario_id=OUTRA)  # de outra pessoa: não pode contar aqui

    resposta = _perguntar_resumo(client, destinatario_id=ALGUEM)

    assert resposta.status_code == 200
    # 4 cartas chegaram para ALGUEM, 1 foi marcada lida por fora (update direto
    # no model, sem passar pela porta de leitura) só para provar que `/resumo`
    # está de fato lendo o CONTADOR (que continua em 4, porque só
    # `guardar()`/`marcar_todas_como_lidas` o tocam) e não fazendo um
    # `COUNT(*)` na tabela (que daria 3).
    assert resposta.json() == {"nao_lidas": 4}


def test_resumo_a_conta_e_por_pessoa_nao_global(client, par_autorizado):
    _guardar(destinatario_id=ALGUEM)
    _guardar(destinatario_id=ALGUEM)
    _guardar(destinatario_id=OUTRA)

    resposta_alguem = _perguntar_resumo(client, destinatario_id=ALGUEM)
    resposta_outra = _perguntar_resumo(client, destinatario_id=OUTRA)

    assert resposta_alguem.json() == {"nao_lidas": 2}
    assert resposta_outra.json() == {"nao_lidas": 1}


def test_resumo_bate_com_o_schema_do_contrato_congelado(client, par_autorizado):
    _guardar()
    resposta = _perguntar_resumo(client, destinatario_id=ALGUEM)
    schema = schema_da_resposta("/resumo", "get", "200")

    Draft202012Validator(schema).validate(resposta.json())


# =============================================================================
# GET /avisos — a lista paginada, mais novo primeiro
# =============================================================================

CAMINHO_AVISOS = "/api/notificacoes/avisos"


def _viva(destinatario_id=ALGUEM, minutos_atras=0, ator_id=EQUIPE, **parametros):
    notificacao = _guardar(
        destinatario_id=destinatario_id, ator_id=ator_id, **parametros
    )
    quando = timezone.now() - timezone.timedelta(minutes=minutos_atras)
    Notificacao.objects.filter(pk=notificacao.pk).update(criado_em=quando)
    return notificacao


def _arquivada(destinatario_id=ALGUEM, minutos_atras=0, lida_minutos_atras=None):
    agora = timezone.now()
    return NotificacaoArquivada.objects.create(
        site_id=SITE,
        destinatario_id=destinatario_id,
        ator_id=EQUIPE,
        assunto="sugestao.status-alterado",
        parametros={"suggestion_id": "arquivada"},
        origem_event_id=uuid.uuid4(),
        criado_em=agora - timezone.timedelta(minutes=minutos_atras),
        lido_em=agora - timezone.timedelta(minutes=lida_minutos_atras or minutos_atras),
    )


def _pedir_avisos(
    client, destinatario_id="", cursor=None, limite=None, token="__default__"
):
    params = {}
    if destinatario_id:
        params["destinatario_id"] = destinatario_id
    if cursor is not None:
        params["cursor"] = cursor
    if limite is not None:
        params["limite"] = limite
    cabecalhos = (
        cabecalho_bearer() if token == "__default__" else cabecalho_bearer(token)
    )
    return client.get(CAMINHO_AVISOS, params, headers=cabecalhos)


def test_avisos_sem_token_e_401(client, par_autorizado):
    assert _pedir_avisos(client, destinatario_id=ALGUEM, token=None).status_code == 401


def test_avisos_token_errado_e_401(client, par_autorizado):
    resposta = _pedir_avisos(client, destinatario_id=ALGUEM, token="token-de-outro-par")
    assert resposta.status_code == 401


def test_avisos_sem_destinatario_id_e_422(client, par_autorizado):
    assert client.get(CAMINHO_AVISOS, headers=cabecalho_bearer()).status_code == 422


def test_avisos_destinatario_id_vazio_e_422(client, par_autorizado):
    assert _pedir_avisos(client, destinatario_id="   ").status_code == 422


def test_avisos_limite_nao_numerico_e_422(client, par_autorizado):
    resposta = _pedir_avisos(client, destinatario_id=ALGUEM, limite="abacate")
    assert resposta.status_code == 422


@pytest.mark.parametrize("limite", [0, -1, 101, 1000])
def test_avisos_limite_fora_do_intervalo_e_422(client, par_autorizado, limite):
    resposta = _pedir_avisos(client, destinatario_id=ALGUEM, limite=limite)
    assert resposta.status_code == 422


def test_avisos_sem_limite_usa_o_padrao_de_20(client, par_autorizado):
    for i in range(25):
        _viva(minutos_atras=i)

    resposta = _pedir_avisos(client, destinatario_id=ALGUEM)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo["itens"]) == 20
    assert corpo["proximo_cursor"] is not None


def test_avisos_cursor_ilegivel_e_422(client, par_autorizado):
    resposta = _pedir_avisos(
        client, destinatario_id=ALGUEM, cursor="isto-nao-e-um-cursor"
    )
    assert resposta.status_code == 422


def test_avisos_cursor_base64_valido_mas_com_forma_errada_e_422(client, par_autorizado):
    lixo = base64.urlsafe_b64encode(json.dumps({"nada": "a ver"}).encode()).decode()
    resposta = _pedir_avisos(client, destinatario_id=ALGUEM, cursor=lixo)
    assert resposta.status_code == 422


def test_avisos_pessoa_sem_nenhum_aviso_e_lista_vazia(client, par_autorizado):
    resposta = _pedir_avisos(client, destinatario_id="ninguem-nunca-ouviu-falar")

    assert resposta.status_code == 200
    assert resposta.json() == {"itens": [], "proximo_cursor": None}


def test_avisos_so_devolve_avisos_do_destinatario_pedido(client, par_autorizado):
    _viva(destinatario_id=ALGUEM, minutos_atras=1)
    _viva(destinatario_id=OUTRA, minutos_atras=2)

    resposta = _pedir_avisos(client, destinatario_id=ALGUEM)

    itens = resposta.json()["itens"]
    assert len(itens) == 1


def test_avisos_ator_id_nulo_vira_null_no_json(client, par_autorizado):
    _viva(ator_id=None)

    item = _pedir_avisos(client, destinatario_id=ALGUEM).json()["itens"][0]

    assert item["ator_id"] is None


def test_avisos_lido_em_e_null_para_nao_lido_e_string_para_lido(client, par_autorizado):
    nao_lido = _viva(minutos_atras=1)
    lido = _viva(minutos_atras=2)
    Notificacao.objects.filter(pk=lido.pk).update(lido_em=timezone.now())

    itens = _pedir_avisos(client, destinatario_id=ALGUEM).json()["itens"]
    por_id = {item["id"]: item for item in itens}

    assert por_id[f"n{nao_lido.pk}"]["lido_em"] is None
    assert isinstance(por_id[f"n{lido.pk}"]["lido_em"], str)


def test_avisos_parametros_viaja_como_objeto_e_nao_como_frase(client, par_autorizado):
    _viva(suggestion_id="731", status_novo="planejado")

    item = _pedir_avisos(client, destinatario_id=ALGUEM).json()["itens"][0]

    assert item["parametros"] == {"suggestion_id": "731", "status_novo": "planejado"}
    assert item["assunto"] == "sugestao.status-alterado"


def test_avisos_a_lista_inclui_avisos_arquivados_junto_com_os_ativos(
    client, par_autorizado
):
    """`DECISAO-notificacoes` §5.2: "nada se perde: o histórico continua
    consultável". Esta é a ÚNICA porta de consulta — se ela não lesse a
    tabela de arquivo, um aviso lido sumiria da vida da pessoa 30 dias depois
    de ela o ter lido.
    """
    mais_novo = _viva(minutos_atras=1)
    arquivado = _arquivada(minutos_atras=2)
    mais_velho = _viva(minutos_atras=3)

    itens = _pedir_avisos(client, destinatario_id=ALGUEM).json()["itens"]
    ids = [item["id"] for item in itens]

    assert ids == [
        f"n{mais_novo.pk}",
        f"a{arquivado.pk}",
        f"n{mais_velho.pk}",
    ], "ordem errada: o merge das duas tabelas não respeitou criado_em"


def test_avisos_paginacao_atravessa_o_merge_sem_perder_nem_repetir(
    client, par_autorizado
):
    """5 avisos intercalados (vivo, arquivado, vivo, arquivado, vivo), lidos em
    páginas de 2. As três páginas juntas precisam reconstruir a MESMA ordem
    que uma chamada única com limite alto devolveria — sem faltar e sem
    repetir nenhum, e sem depender de qual tabela cada um veio.
    """
    rank1 = _viva(minutos_atras=1)
    rank2 = _arquivada(minutos_atras=2)
    rank3 = _viva(minutos_atras=3)
    rank4 = _arquivada(minutos_atras=4)
    rank5 = _viva(minutos_atras=5)
    esperado = [
        f"n{rank1.pk}",
        f"a{rank2.pk}",
        f"n{rank3.pk}",
        f"a{rank4.pk}",
        f"n{rank5.pk}",
    ]

    coletados = []
    cursor = None
    paginas = 0
    while True:
        paginas += 1
        assert paginas <= 10, "não convergiu — cursor não avança"
        corpo = _pedir_avisos(
            client, destinatario_id=ALGUEM, cursor=cursor, limite=2
        ).json()
        coletados += [item["id"] for item in corpo["itens"]]
        cursor = corpo["proximo_cursor"]
        if cursor is None:
            break

    assert paginas == 3, f"esperava 3 páginas (2+2+1), vieram {paginas}"
    assert coletados == esperado


def test_avisos_bate_com_o_schema_do_contrato_congelado(client, par_autorizado):
    _viva(ator_id=None)
    _arquivada()

    resposta = _pedir_avisos(client, destinatario_id=ALGUEM)
    schema = schema_da_resposta("/avisos", "get", "200")

    Draft202012Validator(schema).validate(resposta.json())


# =============================================================================
# POST /marcar-lidas — marca todos os não lidos de uma pessoa de uma vez
# =============================================================================

CAMINHO_MARCAR_LIDAS = "/api/notificacoes/marcar-lidas"


def _contador(destinatario_id=ALGUEM) -> int:
    return (
        ContadorDeNaoLidos.objects.filter(site_id=SITE, destinatario_id=destinatario_id)
        .values_list("nao_lidos", flat=True)
        .first()
        or 0
    )


def _marcar(client, destinatario_id="__omitir__", token="__default__", corpo_cru=None):
    cabecalhos = (
        cabecalho_bearer() if token == "__default__" else cabecalho_bearer(token)
    )
    if corpo_cru is not None:
        return client.post(
            CAMINHO_MARCAR_LIDAS,
            data=corpo_cru,
            content_type="text/plain",
            headers=cabecalhos,
        )
    payload = (
        {} if destinatario_id == "__omitir__" else {"destinatario_id": destinatario_id}
    )
    return client.post(
        CAMINHO_MARCAR_LIDAS,
        data=json.dumps(payload),
        content_type="application/json",
        headers=cabecalhos,
    )


def test_marcar_lidas_sem_token_e_401(client, par_autorizado):
    resposta = _marcar(client, destinatario_id=ALGUEM, token=None)
    assert resposta.status_code == 401


def test_marcar_lidas_token_errado_e_401(client, par_autorizado):
    resposta = _marcar(client, destinatario_id=ALGUEM, token="token-de-outro-par")
    assert resposta.status_code == 401


def test_marcar_lidas_sem_destinatario_id_e_422(client, par_autorizado):
    assert _marcar(client).status_code == 422


def test_marcar_lidas_destinatario_id_vazio_e_422(client, par_autorizado):
    assert _marcar(client, destinatario_id="   ").status_code == 422


def test_marcar_lidas_corpo_nao_e_json_e_422(client, par_autorizado):
    resposta = _marcar(client, corpo_cru="isto nao e json")
    assert resposta.status_code == 422


def test_marcar_lidas_corpo_e_uma_lista_json_valida_mas_sem_forma_e_422(
    client, par_autorizado
):
    resposta = _marcar(client, corpo_cru="[1, 2, 3]")
    assert resposta.status_code == 422


def test_marcar_lidas_pessoa_sem_nada_para_marcar_devolve_zero(client, par_autorizado):
    """0 é resposta válida (o contrato diz isso explicitamente) — nunca 404."""
    resposta = _marcar(client, destinatario_id="ninguem-nunca-ouviu-falar")

    assert resposta.status_code == 200
    assert resposta.json() == {"marcados": 0}


def test_marcar_lidas_marca_todos_os_nao_lidos_e_devolve_a_contagem(
    client, par_autorizado
):
    avisos = [_guardar() for _ in range(4)]
    assert _contador() == 4

    resposta = _marcar(client, destinatario_id=ALGUEM)

    assert resposta.status_code == 200
    assert resposta.json() == {"marcados": 4}
    for aviso in avisos:
        aviso.refresh_from_db()
        assert aviso.lido_em is not None
    assert _contador() == 0


def test_marcar_lidas_nao_marca_o_que_ja_estava_lido(client, par_autorizado):
    ja_lido = _guardar()
    Notificacao.objects.filter(pk=ja_lido.pk).update(lido_em=timezone.now())
    nao_lido = _guardar()

    resposta = _marcar(client, destinatario_id=ALGUEM)

    assert resposta.json() == {"marcados": 1}
    nao_lido.refresh_from_db()
    assert nao_lido.lido_em is not None


def test_marcar_lidas_nao_toca_avisos_de_outra_pessoa(client, par_autorizado):
    _guardar(destinatario_id=ALGUEM)
    da_outra = _guardar(destinatario_id=OUTRA)

    resposta = _marcar(client, destinatario_id=ALGUEM)

    assert resposta.json() == {"marcados": 1}
    da_outra.refresh_from_db()
    assert da_outra.lido_em is None
    assert _contador(OUTRA) == 1


def test_marcar_lidas_chamar_duas_vezes_seguidas_a_segunda_marca_zero_e_nao_fica_negativo(
    client, par_autorizado
):
    _guardar()
    _guardar()

    primeira = _marcar(client, destinatario_id=ALGUEM)
    segunda = _marcar(client, destinatario_id=ALGUEM)

    assert primeira.json() == {"marcados": 2}
    assert segunda.json() == {"marcados": 0}
    assert _contador() == 0


def test_marcar_lidas_o_contador_desconta_exatamente_o_que_marcou_nao_zera_tudo(
    client, par_autorizado
):
    """A prova do porquê o decremento é `F("nao_lidos") - marcados` e não um
    `.update(nao_lidos=0)` cravado: uma carta nova chegando DEPOIS da consulta
    que decidiu quem seria marcado não pode ser apagada do contador.
    """
    _guardar()
    resposta = _marcar(client, destinatario_id=ALGUEM)
    assert resposta.json() == {"marcados": 1}
    assert _contador() == 0

    _guardar()  # chega DEPOIS do marcar-lidas — tem que continuar contando
    assert _contador() == 1


def test_marcar_lidas_bate_com_o_schema_do_contrato_congelado(client, par_autorizado):
    _guardar()
    resposta = _marcar(client, destinatario_id=ALGUEM)
    schema = schema_da_resposta("/marcar-lidas", "post", "200")

    Draft202012Validator(schema).validate(resposta.json())
