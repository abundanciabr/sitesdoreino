"""A tela de avisos aprende que existe carta que NÃO é de sugestão.

Até 29/08/2026 havia um assunto só (`sugestao.status-alterado`) — a Caixa era a
única coisa da plataforma que gerava aviso — e o cartão assumia isso **em
silêncio**. O título dele monta:

    {% url 'sugestao' aviso.sugestao_id %}

que estoura em `NoReverseMatch` para qualquer carta sem `suggestion_id`. Não
seria um cartão feio: seria **a página inteira em 500**, para a pessoa que
recebeu a carta e para todas as outras que ela já tinha.

É por isso que esta tela aprende o assunto novo **antes** de qualquer célula
começar a publicá-lo — a ordem entre os PRs é a proteção, não o cuidado de quem
escreve.

**Os três ramos, e o terceiro é o que importa mais:**

1. `sugestao.status-alterado` — o cartão de sempre, intocado.
2. `matricula.situacao-alterada` — o cartão novo: sem link, porque não há para
   onde levar.
3. **qualquer outro** — um cartão honesto dizendo que esta tela ainda não sabe
   mostrar aquele recado. Fail-VISÍVEL, a mesma regra da página (Escolha 2 da
   `DECISAO-fase-4-do-sininho`). Sem este ramo, um assunto que nascer amanhã
   desenha um cartão de sugestão vazio, com "(sugestão não encontrada)" e um
   link para lugar nenhum — a tela mentindo em vez de admitir.
"""

import httpx
import pytest
from django.urls import reverse

from apps.core.avisos import ASSUNTO_MATRICULA, _item_para_o_template

pytestmark = pytest.mark.django_db


def _carta(assunto, parametros, *, id_="900", lido=False):
    return {
        "id": id_,
        "assunto": assunto,
        "parametros": parametros,
        "ator_id": None,
        "lido_em": "2026-08-29T10:00:00+00:00" if lido else None,
        "criado_em": "2026-08-29T09:00:00+00:00",
    }


def _responde_com(rede, cartas):
    rede.notificacoes_avisos.mock(
        return_value=httpx.Response(200, json={"itens": cartas, "proximo_cursor": None})
    )


# ----------------------------------------------- 1. a tradução, sozinha


def test_a_carta_de_matricula_vira_um_cartao_de_matricula():
    item = _item_para_o_template(
        _carta(
            ASSUNTO_MATRICULA,
            {
                "matricula_id": "7",
                "situacao_anterior": "aguardando",
                "situacao_nova": "ativa",
            },
        ),
        {},
    )

    assert item["assunto"] == ASSUNTO_MATRICULA
    assert item["situacao_nova_label"] == "Você é aluno"
    assert item["situacao_anterior_label"] == "Na fila, esperando decisão"
    assert "sugestao_id" not in item, "o cartão de matrícula não tem sugestão"


def test_o_matricula_id_NAO_vai_para_a_tela():
    """Ele existe para quem for reconstruir o histórico. Um identificador opaco
    no cartão de um aluno é ruído sobre um dado que ele não pode usar."""
    item = _item_para_o_template(
        _carta(ASSUNTO_MATRICULA, {"matricula_id": "77", "situacao_nova": "ativa"}), {}
    )
    assert "77" not in str(item.values())


def test_situacao_que_a_tela_nao_conhece_sai_crua_e_nao_quebra():
    """A mesma regra do `vinculo` ausente: rótulo cru, nunca chave chutada,
    nunca exceção."""
    item = _item_para_o_template(
        _carta(ASSUNTO_MATRICULA, {"matricula_id": "7", "situacao_nova": "inventada"}),
        {},
    )
    assert item["situacao_nova_label"] == "inventada"


def test_carta_SEM_assunto_continua_sendo_de_sugestao():
    """As cartas emitidas antes deste campo existir são todas de sugestão, e
    precisam continuar caindo no ramo de sempre."""
    item = _item_para_o_template(
        {
            "id": "1",
            "parametros": {"suggestion_id": "5", "status_novo": "planejado"},
            "criado_em": "2026-08-29T09:00:00+00:00",
        },
        # A forma que `_sugestoes_dos_avisos` devolve desde 31/08/2026: o
        # título e `apagada` juntos, porque a tela precisa dos dois e eles
        # saem da mesma consulta.
        {"5": {"titulo": "Uma ideia", "apagada": False}},
    )
    assert item["sugestao_titulo"] == "Uma ideia"


def test_assunto_desconhecido_e_marcado_como_desconhecido():
    item = _item_para_o_template(_carta("coisa.que-ninguem-previu", {}), {})
    assert item["desconhecido"] is True
    assert "sugestao_id" not in item


# ------------------------------------------------------ 2. na tela, de fora


def test_a_pagina_mostra_o_cartao_de_matricula(dentro, rede, quadro):
    _responde_com(
        rede,
        [
            _carta(
                ASSUNTO_MATRICULA,
                {
                    "matricula_id": "7",
                    "situacao_anterior": "aguardando",
                    "situacao_nova": "ativa",
                },
            )
        ],
    )

    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert "Sua situação na escola mudou" in corpo
    assert "Você é aluno" in corpo
    assert "Na fila, esperando decisão" in corpo


def test_o_cartao_de_matricula_NAO_leva_a_lugar_nenhum(dentro, rede, quadro):
    """Sem link de propósito: a ficha mora na célula `alunos` e a tela dela é a
    do MANTENEDOR. Mandar a pessoa para lá seria oferecer uma porta que bate na
    cara — o defeito que a home já cometeu uma vez."""
    _responde_com(
        rede,
        [_carta(ASSUNTO_MATRICULA, {"matricula_id": "7", "situacao_nova": "ativa"})],
    )

    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert "sugest" not in corpo.split("Sua situação na escola mudou")[1][:400].lower()
    assert "(sugestão não encontrada)" not in corpo


def test_uma_carta_de_assunto_desconhecido_NAO_derruba_a_pagina(dentro, rede, quadro):
    """O guarda que carrega este arquivo.

    Sem o ramo do desconhecido, o cartão de sugestão tentaria montar o link e a
    página inteira viraria 500 — para essa carta e para todas as outras que a
    pessoa já tinha.
    """
    _responde_com(rede, [_carta("coisa.que-ninguem-previu", {"o_que": "seja"})])

    resposta = dentro.client.get(reverse("avisos"))
    corpo = resposta.content.decode()

    assert resposta.status_code == 200
    assert "ainda não sabe mostrar" in corpo
    assert "problema é nosso, não seu" in corpo


def test_as_tres_cartas_convivem_na_mesma_pagina(dentro, rede, sugestao):
    """A prova de que os ramos não se atrapalham — e de que a de sugestão
    continua desenhando o link dela."""
    _responde_com(
        rede,
        [
            _carta(
                "sugestao.status-alterado",
                {
                    "suggestion_id": str(sugestao.id),
                    "status_anterior": "em_analise",
                    "status_novo": "planejado",
                },
                id_="1",
            ),
            _carta(
                ASSUNTO_MATRICULA,
                {"matricula_id": "7", "situacao_nova": "suspensa"},
                id_="2",
            ),
            _carta("coisa.que-ninguem-previu", {}, id_="3"),
        ],
    )

    resposta = dentro.client.get(reverse("avisos"))
    corpo = resposta.content.decode()

    assert resposta.status_code == 200
    assert sugestao.titulo in corpo
    assert "Acesso pausado" in corpo
    assert "ainda não sabe mostrar" in corpo


def test_toda_carta_pode_ser_marcada_como_lida_seja_qual_for_o_assunto(
    dentro, rede, quadro
):
    """Um aviso que a pessoa não consegue tirar da frente fica contando no sino
    para sempre — e o sino que não zera é o que faz alguém parar de olhar."""
    for assunto in (ASSUNTO_MATRICULA, "coisa.que-ninguem-previu"):
        _responde_com(rede, [_carta(assunto, {"situacao_nova": "ativa"})])
        corpo = dentro.client.get(reverse("avisos")).content.decode()
        assert "Marcar como lido" in corpo, assunto
