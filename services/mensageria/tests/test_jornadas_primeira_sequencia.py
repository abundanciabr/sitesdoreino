"""A primeira sequência de verdade: do cadastro até a carta no fio.

Degrau 5 da escada, segunda metade. O que se prova aqui: o cadastro inscreve, o
gatilho da jornada CASA com o evento que a célula escuta, a sequência semeada é
dado (não código), e um cadastro reentregue não inscreve em dobro.
"""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.eventos.handlers import GATILHO_CADASTRO, ao_pessoa_cadastrada
from apps.eventos.management.commands.consume_eventos import STREAMS
from apps.jornadas import condicoes, motor
from apps.jornadas.models import (
    Inscricao,
    Jornada,
    JornadaVersao,
    OutboxEvent,
    Passo,
    TextoDoPasso,
)

pytestmark = pytest.mark.django_db

SITE = "site-abc"
PESSOA = "pessoa-opaca-1"
EVENTO = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def semear(ligar=True):
    saida = StringIO()
    call_command("semear_boas_vindas", site_id=SITE, ligar=ligar, stdout=saida)
    return saida.getvalue()


# ---------------------------------------------------------------------------
# O GATILHO CASA COM O EVENTO — a falha que não dá erro nenhum
# ---------------------------------------------------------------------------


def test_o_gatilho_da_jornada_casa_com_o_stream_que_a_celula_escuta():
    """A falha silenciosa mais fácil de cometer neste degrau inteiro.

    O `gatilho` é texto livre. Escrever `identidade.pessoa-cadastrada.v1` (com a
    versão, como o PLANO cita o contrato) em vez de `identidade.pessoa-cadastrada`
    (o nome no fio) faria a jornada NUNCA casar com evento nenhum: o consumidor
    recebe, o handler roda, o filtro não acha jornada, e ninguém é inscrito.
    Nada erra, nada reclama, e a sequência simplesmente não acontece.

    Aqui as duas pontas são amarradas uma na outra: o gatilho da jornada semeada
    e a chave do stream que o consumidor assina.
    """
    semear()
    jornada = Jornada.objects.get(site_id=SITE, slug="boas-vindas")

    assert jornada.gatilho == GATILHO_CADASTRO
    assert f"eventos.{GATILHO_CADASTRO}" in STREAMS
    assert STREAMS[f"eventos.{GATILHO_CADASTRO}"] is ao_pessoa_cadastrada
    assert ".v1" not in jornada.gatilho, "a versao viaja no envelope, nao no nome"


# ---------------------------------------------------------------------------
# A SEMEADURA É DADO, E NASCE DESLIGADA
# ---------------------------------------------------------------------------


def test_a_jornada_semeada_nasce_desligada_e_nao_inscreve_ninguem():
    """Ligar uma sequência é decisão do mantenedor, nunca efeito de um deploy."""
    semear(ligar=False)
    jornada = Jornada.objects.get(slug="boas-vindas")
    assert jornada.ativa is False

    ao_pessoa_cadastrada({"site_id": SITE, "pessoa_id": PESSOA}, EVENTO)
    assert not Inscricao.objects.exists()


def test_com_ligar_a_jornada_passa_a_valer():
    semear(ligar=True)
    assert Jornada.objects.get(slug="boas-vindas").ativa is True


def test_a_sequencia_semeada_e_a_do_plano():
    """Três passos: boas-vindas hoje, empurrão em D+2, convite em D+7."""
    semear()
    versao = JornadaVersao.objects.get()
    passos = list(versao.passos.order_by("ordem"))

    assert [p.ordem for p in passos] == [1, 2, 3]
    assert [p.atraso for p in passos] == [
        timedelta(0),
        timedelta(days=2),
        timedelta(days=7),
    ]
    assert [p.condicao_slug for p in passos] == [
        "",
        "ainda-nao-entrou-em-aula",
        "ainda-nao-postou-no-forum",
    ]
    assert versao.publicada_em is not None


def test_toda_condicao_usada_pela_semeadura_existe_de_verdade():
    """Slug de condição é texto livre, e um erro de digitação aqui viraria passo
    PULADO para sempre (fail-closed do motor). Amarrado ao dicionário real."""
    semear()
    usados = {p.condicao_slug for p in Passo.objects.all() if p.condicao_slug}
    assert usados <= set(condicoes.CONDICOES), f"condicao inexistente: {usados}"


def test_cada_passo_tem_texto_nos_tres_idiomas():
    """A escola serve três idiomas, e a frase nasce na LEITURA (§4.3).

    Passo sem texto no idioma de quem lê é aviso que aparece sem frase — e a
    tela deve mostrar "não carregou", nunca inventar. Semear os três é o que
    evita esse buraco no primeiro dia.
    """
    semear()
    for passo in Passo.objects.all():
        idiomas = set(passo.textos.values_list("idioma", flat=True))
        assert idiomas == {"pt-br", "en", "es"}, f"passo {passo.ordem}: {idiomas}"
    assert TextoDoPasso.objects.count() == 9


def test_semear_duas_vezes_nao_duplica_nem_reescreve():
    """Idempotente, e a segunda passada NÃO tenta alterar a versão publicada.

    Se tentasse, o gatilho do banco recusaria: versão publicada é pedra. O
    comando avisa e sai, que é o comportamento certo — trocar o texto é publicar
    uma versão NOVA, e quem faz isso é a tela do mantenedor.
    """
    semear()
    saida = semear()

    assert Jornada.objects.count() == 1
    assert JornadaVersao.objects.count() == 1
    assert Passo.objects.count() == 3
    assert TextoDoPasso.objects.count() == 9
    assert "ja existe" in saida


# ---------------------------------------------------------------------------
# DO CADASTRO À INSCRIÇÃO
# ---------------------------------------------------------------------------


def test_o_cadastro_inscreve_a_pessoa_na_jornada():
    semear()
    ao_pessoa_cadastrada({"site_id": SITE, "pessoa_id": PESSOA}, EVENTO)

    inscricao = Inscricao.objects.get()
    assert inscricao.destinatario_id == PESSOA
    assert str(inscricao.origem_event_id) == EVENTO
    assert inscricao.estado == "andando"
    assert inscricao.passo_atual == 0


def test_o_cadastro_reentregue_nao_inscreve_em_dobro():
    semear()
    ao_pessoa_cadastrada({"site_id": SITE, "pessoa_id": PESSOA}, EVENTO)
    ao_pessoa_cadastrada({"site_id": SITE, "pessoa_id": PESSOA}, EVENTO)

    assert Inscricao.objects.count() == 1


def test_o_cadastro_de_outro_site_nao_entra_nesta_jornada():
    """Multissítio: a jornada é de um site, e o `site_id` do evento decide."""
    semear()
    ao_pessoa_cadastrada({"site_id": "outro-site", "pessoa_id": PESSOA}, EVENTO)
    assert not Inscricao.objects.exists()


def test_sem_origem_a_inscricao_entra_mas_a_carta_nao_sai():
    """As duas metades da mesma decisão, medidas juntas.

    Inscrever sem origem é aceitável (a pessoa entrou mesmo). Publicar carta sem
    origem não é: `origem_event_id` é obrigatório no contrato e é o que torna o
    aviso rastreável. O motor conta isso como `sem_despacho`, e o passo continua
    devendo em vez de sumir.
    """
    from apps.jornadas import despacho

    semear()
    ao_pessoa_cadastrada({"site_id": SITE, "pessoa_id": PESSOA}, None)

    inscricao = Inscricao.objects.get()
    assert inscricao.origem_event_id is None

    # Amanhã às 10h de São Paulo, e não `timezone.now()`: a inscrição foi
    # ancorada no relógio real, então o momento da varredura precisa vir DEPOIS
    # dela E dentro da janela da régua (8h-20h). Com o relógio cru, entre as 20h
    # e as 8h a régua barrava o passo e o teste media `barradas=1` em vez de
    # `sem_despacho=1`: verde de dia, vermelho à noite (`armadilhas/323`).
    amanha_as_10 = (timezone.localtime() + timedelta(days=1)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    passada = motor.varrer(momento=amanha_as_10, despachar=despacho.despachar)
    assert passada.sem_despacho == 1
    assert passada.entregues == 0
    assert not OutboxEvent.objects.exists()

    inscricao.refresh_from_db()
    assert inscricao.passo_atual == 0, "o passo continua devendo"
