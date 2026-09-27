"""A tela das medalhas, `/conquistas/medalhas`: o critério antes de conquistar.

O `PLANO-CELULA-GAMIFICACAO.md` §5 previa a coleção de medalhas e ela não
existia: uma medalha ligada caía sem que a pessoa soubesse que ela existia, nem
o que precisava fazer. Esta tela mostra cada medalha LIGADA com o critério em
português e o estado de quem olha.

O QUE ESTE ARQUIVO TRAVA:

1. **O critério aparece antes de conquistar**, dito em português a partir do
   próprio dado (`criterio`), e não de um texto solto que pode divergir dele.
2. **Só a pessoa que olha.** Sem ranking, sem "quantas pessoas já têm", sem o
   nome de ninguém: a lei §8 proíbe ranking público, e o progresso dos outros
   não entra na conta de ninguém.
3. **Visitante não leva erro**, como na Base e nos Marcos.
4. **Toda palavra do vocabulário tem frase.** Um critério novo sem frase faria
   a tela mostrar uma medalha sem dizer como se ganha.
"""

from __future__ import annotations

import pytest
from django.test import Client
from django.utils import timezone

from apps.gamificacao.criterios import FRASES_DOS_CRITERIOS
from apps.gamificacao.models import (
    CRITERIOS_ACEITOS,
    AjudaAceita,
    Concessao,
    ConquistaDefinicao,
    Pessoa,
)

pytestmark = pytest.mark.django_db

SITE = "site-de-teste"
ALUNO = "pes-aluno"
OUTRA = "pes-outra-pessoa"


@pytest.fixture(autouse=True)
def site_e_sessao(monkeypatch):
    """O site vem do env e quem é a pessoa vem da identidade: os dois em dublê."""
    monkeypatch.setattr("apps.core.views.site_atual", lambda: SITE)
    monkeypatch.setenv("URL_DE_ENTRADA", "https://exemplo.test/entrar")
    monkeypatch.setenv("URL_DA_CAPA", "https://exemplo.test/")


def _entrar_como(monkeypatch, pessoa_id: str | None):
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: pessoa_id)


def _medalha(**campos) -> ConquistaDefinicao:
    base = {
        "slug": "primeira-ajuda",
        "site_id": SITE,
        "nome": "Primeira ajuda aceita",
        "classe": ConquistaDefinicao.Classe.MEDALHA,
        "familia": ConquistaDefinicao.Familia.COMUNIDADE,
        "criterio": {"tipo": "respostas_aceitas", "alvo": 1},
        "ativa": True,
    }
    base.update(campos)
    return ConquistaDefinicao.objects.create(**base)


def _pessoa(pessoa_id: str) -> Pessoa:
    return Pessoa.objects.create(
        id_da_plataforma=pessoa_id, email=f"{pessoa_id}@exemplo.test"
    )


def _corpo() -> str:
    resposta = Client().get("/medalhas")
    assert resposta.status_code == 200
    return resposta.content.decode()


def test_visitante_ve_convite_e_nunca_erro(monkeypatch):
    _entrar_como(monkeypatch, None)
    _medalha()

    corpo = _corpo()

    assert "Entrar na escola" in corpo
    assert "Primeira ajuda aceita" not in corpo


def test_sem_site_no_env_tambem_nao_quebra(monkeypatch):
    _entrar_como(monkeypatch, ALUNO)
    monkeypatch.setattr("apps.core.views.site_atual", lambda: None)

    assert "Entrar na escola" in _corpo()


def test_o_criterio_aparece_em_portugues_antes_de_conquistar(monkeypatch):
    _entrar_como(monkeypatch, ALUNO)
    _medalha()
    _medalha(
        slug="primeiro-ciclo",
        nome="Primeiro ciclo concluído",
        criterio={"tipo": "entregas_aceitas", "alvo": 1},
    )

    corpo = _corpo()

    assert "Primeira ajuda aceita" in corpo
    assert "Ter uma resposta sua aceita no fórum como a que resolveu a dúvida." in corpo
    assert "Primeiro ciclo concluído" in corpo
    assert "Ter uma entrega aceita pela escola, abrindo a aula seguinte." in corpo
    assert "Seu progresso: 0 de 1." in corpo


def test_a_medalha_conquistada_diz_quando(monkeypatch):
    _entrar_como(monkeypatch, ALUNO)
    medalha = _medalha()
    concessao = Concessao.objects.create(
        pessoa=_pessoa(ALUNO), site_id=SITE, conquista=medalha
    )

    corpo = _corpo()

    assert f"Conquistada em {concessao.concedida_em:%d/%m/%Y}." in corpo
    assert "Seu progresso" not in corpo


def test_so_aparece_medalha_ligada_nunca_marco_nem_secreta_por_conquistar(
    monkeypatch,
):
    _entrar_como(monkeypatch, ALUNO)
    _medalha(slug="desligada", nome="Medalha desligada", ativa=False)
    _medalha(slug="segredo", nome="Medalha secreta", secreta=True)
    _medalha(
        slug="primeiro-cliente",
        nome="Primeiro cliente",
        classe=ConquistaDefinicao.Classe.MARCO,
        familia=ConquistaDefinicao.Familia.CARREIRA,
        criterio={"tipo": "manual"},
    )

    corpo = _corpo()

    assert "Medalha desligada" not in corpo
    assert "Medalha secreta" not in corpo
    assert "Primeiro cliente" not in corpo
    assert "Ainda não há medalhas ligadas nesta escola" in corpo


def test_so_a_pessoa_que_olha_sem_ranking_e_sem_numero_dos_outros(monkeypatch):
    """Outra pessoa já ganhou e já ajudou: nada disso aparece para esta."""
    _entrar_como(monkeypatch, ALUNO)
    medalha = _medalha()
    outra = _pessoa(OUTRA)
    Concessao.objects.create(pessoa=outra, site_id=SITE, conquista=medalha)
    AjudaAceita.objects.create(
        pessoa=outra,
        site_id=SITE,
        mensagem_id="1",
        topico_id="7",
        marcada_por="autor",
        occurred_at=timezone.now(),
    )

    corpo = _corpo()

    assert "Seu progresso: 0 de 1." in corpo
    assert "Conquistada em" not in corpo
    assert OUTRA not in corpo
    assert "pessoas" not in corpo


def test_o_progresso_nunca_passa_do_alvo(monkeypatch):
    """Ligada agora e ainda não avaliada: a pessoa já cumpriu e a tela diz 1 de 1."""
    _entrar_como(monkeypatch, ALUNO)
    _medalha()
    aluno = _pessoa(ALUNO)
    for mensagem in ("1", "2"):
        AjudaAceita.objects.create(
            pessoa=aluno,
            site_id=SITE,
            mensagem_id=mensagem,
            topico_id="7",
            marcada_por="autor",
            occurred_at=timezone.now(),
        )

    assert "Seu progresso: 1 de 1." in _corpo()


def test_toda_palavra_do_vocabulario_tem_frase_em_portugues():
    assert set(FRASES_DOS_CRITERIOS) == set(CRITERIOS_ACEITOS)
