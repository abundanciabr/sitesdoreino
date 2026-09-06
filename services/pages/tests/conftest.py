"""As peças que os guardas do portfólio montam, e nenhuma regra.

As fábricas montam estado; quem julga é o banco, e quem afirma é cada teste. Uma
fábrica que decidisse o que é permitido seria o teste medindo a própria resposta.

**Nenhum instante fixo mora aqui.** `criado_em` e `criada_em` são `auto_now_add`
e quem os preenche é o relógio da máquina: uma constante escrita no topo do
arquivo vira bomba-relógio no dia em que o relógio real a ultrapassar
(`armadilhas/323`, medida na célula `encomendas` em 04/09/2026, três horas
depois de o arquivo nascer).
"""

from datetime import datetime, timezone as fuso

import pytest

from apps.portfolio.models import EstadoDoAluno, ItemDeConferencia, Peca, Portfolio

SITE = "escola-a"
OUTRO_SITE = "escola-b"


def agora():
    """O relógio real, nunca um instante escrito à mão (`armadilhas/323`)."""
    return datetime.now(tz=fuso.utc)


@pytest.fixture
def criar_portfolio(db):
    """Fábrica de portfólio no estado normal: vitrine desligada, sem apelido.

    O padrão é o do aluno que acabou de abrir a Prancheta pela primeira vez, e é
    de propósito que ele seja o estado privado: a vitrine é opt-in (AC-13).
    """

    def fabrica(aluno_id, *, site_id=SITE, apelido="", publicada=False):
        return Portfolio.objects.create(
            site_id=site_id,
            aluno_id=aluno_id,
            apelido=apelido,
            vitrine_publicada=publicada,
            publicada_em=agora() if publicada else None,
        )

    return fabrica


@pytest.fixture
def criar_peca(db):
    """Fábrica de peça: um link colado, na posição pedida."""

    def fabrica(
        portfolio, *, ordem=1, link="https://exemplo.test/render.png", **campos
    ):
        return Peca.objects.create(
            portfolio=portfolio, ordem=ordem, link=link, **campos
        )

    return fabrica


@pytest.fixture
def criar_item(db):
    """Fábrica de item da lista de conferência, desmarcado."""

    def fabrica(portfolio, *, chave="tres-tipos-escolhidos", etapa=1, **campos):
        return ItemDeConferencia.objects.create(
            portfolio=portfolio, chave=chave, etapa=etapa, **campos
        )

    return fabrica


@pytest.fixture
def criar_estado(db):
    """Fábrica de estado do aluno, na primeira etapa e sem selo."""

    def fabrica(portfolio, **campos):
        return EstadoDoAluno.objects.create(portfolio=portfolio, **campos)

    return fabrica
