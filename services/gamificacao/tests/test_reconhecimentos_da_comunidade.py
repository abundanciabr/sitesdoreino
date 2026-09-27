"""Os dois reconhecimentos da Comunidade: primeiro ciclo e primeira ajuda.

Frente C5 da Comunidade Meshcraft (TAR-826). Duas medalhas da família
`comunidade`, semeadas como DADO e desligadas, que caem pelo próprio fato:

- `primeiro-ciclo`: a primeira aula concluída (`aula.concluida.v1`), contada
  por `EntregaAceita`, que o handler escreve com a regra de XP ligada ou não;
- `primeira-ajuda`: a primeira resposta aceita no fórum, contada pela
  `AjudaAceita` que já existia.

O QUE ESTE ARQUIVO TRAVA:

1. **O mesmo fato reentregue concede UMA vez**, pelo consumidor e pelo handler
   chamado direto. A entrega aceita é única por evento; a concessão é única
   por pessoa e conquista.
2. **Reconhecer não depende de pagar.** Com a economia inteira desligada (o
   estado da produção), o fato é registrado e a medalha ligada cai.
3. **Nascem desligadas, valem zero ponto e marco continua zero XP.**
4. **A migração leva as duas definições a toda escola já semeada**, porque o
   semeador não roda no deploy, e não pisa no que o mantenedor editou.
"""

from __future__ import annotations

import importlib
import uuid
from io import StringIO

import pytest
from django.apps import apps as registro_de_apps
from django.core.management import call_command
from django.utils import timezone

from apps.eventos.management.commands.consume_eventos import processar_envelope
from apps.gamificacao.criterios import avaliar
from apps.gamificacao.handlers import HANDLERS
from apps.gamificacao.interruptores import impedimentos_da_conquista
from apps.gamificacao.management.commands.semear_economia import CONQUISTAS
from apps.gamificacao.models import (
    EntregaAceita,
    Concessao,
    ConquistaDefinicao,
    LancamentoDeXP,
    Pessoa,
)

pytestmark = pytest.mark.django_db

SITE = "site-de-teste"
ALUNO = "pes-aluno"
QUEM_MARCOU = "pes-perguntou"
PRIMEIRO_CICLO = "primeiro-ciclo"
PRIMEIRA_AJUDA = "primeira-ajuda"

migracao = importlib.import_module(
    "apps.gamificacao.migrations.0007_reconhecimentos_da_comunidade"
)


def _semear(site: str = SITE) -> None:
    call_command("semear_economia", "--site", site, stdout=StringIO())


def _ligar(slug: str) -> None:
    ConquistaDefinicao.objects.filter(site_id=SITE, slug=slug).update(ativa=True)


def _aula_concluida(**campos) -> dict:
    """O envelope como `contracts/eventos/aula.concluida.v1.json` o fixa."""
    data = {"site_id": SITE, "curso_id": "c-1", "aula_id": "a-01", "e_boss": False}
    data.update(campos.pop("data", {}))
    base = {
        "event": "aula.concluida",
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "occurred_at": timezone.now().isoformat(),
        "ator_id": ALUNO,
        "data": data,
    }
    base.update(campos)
    return base


def _resposta_aceita(**campos) -> dict:
    """O envelope como `contracts/eventos/forum.resposta-aceita.v1.json` o fixa."""
    data = {
        "site_id": SITE,
        "topico_id": "7",
        "mensagem_id": "42",
        "autor_da_resposta_id": ALUNO,
        "marcada_por": "autor",
    }
    data.update(campos.pop("data", {}))
    base = {
        "event": "forum.resposta-aceita",
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "occurred_at": timezone.now().isoformat(),
        "ator_id": QUEM_MARCOU,
        "data": data,
    }
    base.update(campos)
    return base


def _entregar_pelos_dois_caminhos(envelope: dict) -> None:
    """Duas vezes pelo consumidor e duas vezes direto no handler.

    O consumidor segura a reentrega pelo `event_id` (`EventoProcessado`); o
    handler chamado direto é o reprocesso manual, que essa camada não cobre. As
    chaves únicas do banco precisam segurar sozinhas.
    """
    processar_envelope(envelope, HANDLERS)
    processar_envelope(envelope, HANDLERS)
    HANDLERS[envelope["event"]](envelope)
    HANDLERS[envelope["event"]](envelope)


# ------------------------------------------- 1. as duas nascem como dado


def test_as_duas_medalhas_nascem_desligadas_como_dado_e_valem_zero():
    _semear()

    ciclo = ConquistaDefinicao.objects.get(site_id=SITE, slug=PRIMEIRO_CICLO)
    ajuda = ConquistaDefinicao.objects.get(site_id=SITE, slug=PRIMEIRA_AJUDA)

    assert ciclo.nome == "Primeiro ciclo concluído"
    assert ciclo.criterio == {"tipo": "entregas_aceitas", "alvo": 1}
    assert ajuda.nome == "Primeira ajuda aceita"
    assert ajuda.criterio == {"tipo": "respostas_aceitas", "alvo": 1}
    for medalha in (ciclo, ajuda):
        assert medalha.classe == ConquistaDefinicao.Classe.MEDALHA
        assert medalha.familia == ConquistaDefinicao.Familia.COMUNIDADE
        assert medalha.ativa is False, "ligar é gesto do mantenedor"
        assert (medalha.pontos, medalha.cristais) == (0, 0)
    assert not ConquistaDefinicao.objects.filter(
        classe=ConquistaDefinicao.Classe.MARCO, pontos__gt=0
    ).exists(), "marco real vale zero XP"


def test_a_tela_da_economia_ja_lista_as_duas_sem_impedimento():
    """`/admin/economia/` lê `listar_conquistas`; o aviso "nada alimenta isto"
    mentiria aqui, porque as duas têm fato de verdade por trás."""
    _semear()

    for slug in (PRIMEIRO_CICLO, PRIMEIRA_AJUDA):
        conquista = ConquistaDefinicao.objects.get(site_id=SITE, slug=slug)
        assert impedimentos_da_conquista(conquista) == []


# ------------------------------------------- 2. primeiro ciclo concluído


def test_a_primeira_aula_concede_o_primeiro_ciclo_uma_vez_com_o_xp_desligado():
    _semear()
    _ligar(PRIMEIRO_CICLO)

    _entregar_pelos_dois_caminhos(_aula_concluida())

    assert EntregaAceita.objects.count() == 1, "reentrega virou segundo ciclo"
    concessao = Concessao.objects.get()
    assert concessao.conquista.slug == PRIMEIRO_CICLO
    assert concessao.pessoa_id == ALUNO
    assert concessao.validador_papel == Concessao.PapelDoValidador.SISTEMA
    assert LancamentoDeXP.objects.count() == 0, "a economia está desligada"


def test_dois_laudos_sao_duas_entregas_e_o_primeiro_ciclo_continua_um_so():
    """A chave da linha é o evento, e a chave da medalha é a pessoa.

    A célula não guarda QUAL aula abriu (invariante 3 da economia): guarda que
    uma entrega foi aceita. Dois laudos são dois fatos; a medalha, uma só.
    """
    _semear()
    _ligar(PRIMEIRO_CICLO)

    HANDLERS["aula.concluida"](_aula_concluida())
    HANDLERS["aula.concluida"](_aula_concluida(data={"aula_id": "a-02"}))

    assert EntregaAceita.objects.count() == 2
    assert Concessao.objects.get().conquista.slug == PRIMEIRO_CICLO


def test_medalha_desligada_registra_o_fato_e_ligar_depois_reconhece():
    """Ligar uma medalha RECONHECE quem já cumpriu (decisão de 01/09/2026)."""
    _semear()

    HANDLERS["aula.concluida"](_aula_concluida())
    assert EntregaAceita.objects.count() == 1
    assert Concessao.objects.count() == 0, "medalha desligada concedeu"

    _ligar(PRIMEIRO_CICLO)
    assert [c.conquista.slug for c in avaliar(ALUNO, SITE)] == [PRIMEIRO_CICLO]


@pytest.mark.parametrize("ator_id", [None, ""])
def test_aula_sem_aluno_nao_registra_ciclo_nem_inventa_pessoa(ator_id):
    _semear()
    _ligar(PRIMEIRO_CICLO)

    HANDLERS["aula.concluida"](_aula_concluida(ator_id=ator_id))

    assert EntregaAceita.objects.count() == 0
    assert Pessoa.objects.count() == 0
    assert Concessao.objects.count() == 0


# ------------------------------------------- 3. primeira ajuda aceita


def test_a_primeira_ajuda_aceita_concede_uma_vez_a_quem_escreveu():
    _semear()
    _ligar(PRIMEIRA_AJUDA)

    _entregar_pelos_dois_caminhos(_resposta_aceita())

    concessao = Concessao.objects.get()
    assert concessao.conquista.slug == PRIMEIRA_AJUDA
    assert concessao.pessoa_id == ALUNO, "o prêmio é de quem escreveu"
    assert not Concessao.objects.filter(pessoa_id=QUEM_MARCOU).exists()
    assert LancamentoDeXP.objects.count() == 0, "a economia está desligada"


# ------------------------------------------- 4. a migração que leva à produção


def test_a_migracao_leva_as_duas_a_toda_escola_ja_semeada_sem_pisar_em_edicao():
    """O semeador não roda no deploy (o contêiner só roda `migrate`); é esta
    migração que faz as duas aparecerem em `/admin/economia/` da produção."""
    ConquistaDefinicao.objects.create(
        slug="fundador",
        site_id="escola-em-producao",
        nome="Fundador",
        classe=ConquistaDefinicao.Classe.MEDALHA,
        familia=ConquistaDefinicao.Familia.EPOCA,
        criterio={"tipo": "manual"},
    )
    ConquistaDefinicao.objects.create(
        slug=PRIMEIRA_AJUDA,
        site_id="escola-que-ja-editou",
        nome="Nome que o mantenedor escolheu",
        classe=ConquistaDefinicao.Classe.MEDALHA,
        familia=ConquistaDefinicao.Familia.COMUNIDADE,
        criterio={"tipo": "respostas_aceitas", "alvo": 1},
        ativa=True,
    )

    migracao.levar_os_reconhecimentos(registro_de_apps, None)
    migracao.levar_os_reconhecimentos(registro_de_apps, None)

    semeadas = {linha[0]: linha for linha in CONQUISTAS}
    for slug in (PRIMEIRO_CICLO, PRIMEIRA_AJUDA):
        linha = ConquistaDefinicao.objects.get(site_id="escola-em-producao", slug=slug)
        _, nome, descricao, classe, familia, criterio, *_, pontos, cristais = semeadas[
            slug
        ]
        assert (linha.nome, linha.descricao, linha.criterio) == (
            nome,
            descricao,
            criterio,
        ), "a migração e o semeador divergiram"
        assert (linha.classe, linha.familia) == (classe, familia)
        assert (linha.pontos, linha.cristais, linha.ativa) == (pontos, cristais, False)

    editada = ConquistaDefinicao.objects.get(
        site_id="escola-que-ja-editou", slug=PRIMEIRA_AJUDA
    )
    assert editada.nome == "Nome que o mantenedor escolheu"
    assert editada.ativa is True
    assert ConquistaDefinicao.objects.filter(slug=PRIMEIRO_CICLO).count() == 2
