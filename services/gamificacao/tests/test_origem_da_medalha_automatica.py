"""A medalha que cai sozinha guarda o fato que a disparou.

Reconhecimento registra origem e data (dossiê da Comunidade §5). A aula e a
resposta aceita já levavam o evento até a concessão; faltavam os dois caminhos
por onde a maior parte das medalhas cai: o XP somado em `motor.recalcular` e o
    eventos de XP. Sem eles, a tela interna da equipe dizia "conta automática" para
uma medalha que tinha, sim, um fato por trás.

O QUE ESTE ARQUIVO TRAVA:

1. **A medalha que cai pelo XP guarda o evento que creditou o XP**, na
   concessão e na primeira linha do histórico, e a tela interna mostra esse
   evento no lugar de "conta automática".
2. **A reentrega do mesmo evento não concede duas vezes** nem escreve segunda
   linha de histórico.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.core import equipe as porta_da_equipe
from apps.gamificacao.models import (
    Concessao,
    ConquistaDefinicao,
    HistoricoDaConcessao,
    Pessoa,
    RegraDePontuacao,
)
from apps.gamificacao.motor import aplicar

pytestmark = pytest.mark.django_db

SITE = "site-de-teste"
ALUNO = "pes-aluno"
PROFESSORA = "pes-professora"
SEM_ORIGEM = "conta automática da escola"


@pytest.fixture(autouse=True)
def site_e_equipe(monkeypatch):
    monkeypatch.setattr("apps.core.views.site_atual", lambda: SITE)
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: PROFESSORA)
    monkeypatch.setenv("URL_DE_ENTRADA", "https://exemplo.test/entrar")
    monkeypatch.setenv("URL_DA_CAPA", "https://exemplo.test/")
    monkeypatch.setenv(porta_da_equipe.VARIAVEL, PROFESSORA)
    porta_da_equipe._ja_avisei_que_a_lista_esta_vazia = False


def _pessoa() -> Pessoa:
    pessoa, _ = Pessoa.objects.get_or_create(
        id_da_plataforma=ALUNO, defaults={"email": f"{ALUNO}@exemplo.test"}
    )
    return pessoa


def _medalha(slug: str, criterio: dict) -> ConquistaDefinicao:
    return ConquistaDefinicao.objects.create(
        site_id=SITE,
        slug=slug,
        nome=slug.replace("-", " ").capitalize(),
        classe=ConquistaDefinicao.Classe.MEDALHA,
        familia=ConquistaDefinicao.Familia.OFICIO,
        criterio=criterio,
        ativa=True,
    )


def _regra_de_300_xp() -> None:
    RegraDePontuacao.objects.create(
        slug="sugestao-criada",
        site_id=SITE,
        evento_gatilho="sugestao.criada.v1",
        beneficiario=RegraDePontuacao.Beneficiario.ATOR,
        pontos=300,
        cristais=0,
        acoes_cheias_por_dia=0,
        quarentena_horas=0,
        ativa=True,
        vigente_desde=timezone.now() - timedelta(days=1),
    )


def _evento(event_id: str) -> dict:
    return {
        "event": "sugestao.criada",
        "version": 1,
        "event_id": event_id,
        "occurred_at": timezone.now().isoformat(),
        "ator_id": ALUNO,
        "data": {"site_id": SITE},
    }


def _tela_interna() -> str:
    resposta = Client().get("/interno/reconhecimentos")
    assert resposta.status_code == 200
    return resposta.content.decode()


def test_a_medalha_que_cai_pelo_xp_guarda_o_evento_e_a_tela_mostra():
    _pessoa()
    _regra_de_300_xp()
    _medalha("veterano", {"tipo": "xp_acumulado", "alvo": 300})
    event_id = str(uuid.uuid4())

    aplicar(_evento(event_id), SITE)

    concessao = Concessao.objects.get(conquista__slug="veterano")
    assert concessao.origem_event_id == event_id
    assert concessao.historico.get().origem_nova == event_id
    pagina = _tela_interna()
    assert f"Origem: {event_id}" in pagina
    assert SEM_ORIGEM not in pagina


def test_a_reentrega_do_mesmo_evento_nao_concede_duas_vezes():
    _pessoa()
    _regra_de_300_xp()
    _medalha("veterano", {"tipo": "xp_acumulado", "alvo": 300})
    envelope = _evento(str(uuid.uuid4()))

    aplicar(envelope, SITE)
    aplicar(envelope, SITE)

    assert Concessao.objects.count() == 1
    assert HistoricoDaConcessao.objects.count() == 1


