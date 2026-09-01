"""A célula ganhou VOZ: ela avisa quem subiu de nível.

Até 01/09/2026 a gamificação era MUDA. Ela contava pontos, subia níveis e não
dizia nada a ninguém — ganhar só acontecia se o aluno resolvesse abrir a tela
por conta própria. Este arquivo trava as sete coisas que a voz precisa cumprir
para não virar barulho:

1. **Subir de nível escreve a carta**, e ela nasce na MESMA transação do fato.
   Fora dela, um rollback deixaria um aviso no fio para uma subida que não
   aconteceu — o modo de falha mais caro que uma outbox existe para impedir.

2. **Só BOA NOTÍCIA vira carta.** Perder XP não avisa. Não é delicadeza: é lei
   da célula (`DECISAO-gamificacao.md`), onde notificação de culpa está na lista
   das mecânicas proibidas.

3. **Ganhar sem mudar de degrau não avisa.** O aviso é sobre o degrau, não
   sobre o placar — senão o sininho tocaria a cada ponto e a pessoa aprenderia a
   ignorá-lo.

4. **A carta casa com o contrato congelado**, validada contra o ARQUIVO de
   `contracts/eventos/notificacao.devida.v1.json` — nunca contra uma cópia do
   formato dentro do teste. É o que impede o teste de continuar verde enquanto o
   fio quebra.

5. **Os quatro assuntos da Sessão B cabem na mesma porta.** Medalha, marco e
   destaque ainda não têm fato que os justifique (degraus 12 e 19), mas o
   caminho por onde eles vão sair está provado hoje. Assunto FORA do contrato é
   recusado na origem.

6. **A comemoração de tela e a carta são as duas metades da mesma coisa.** A
   celebração visceral alcança quem está com o site aberto; a carta alcança quem
   não está. E o estado da primeira mora no MODELO, nunca na sessão
   ([INV-P12], `armadilhas/143`).

7. **Nenhuma PII no fio.** Nem nome, nem e-mail: só ids opacos e números.
"""

from __future__ import annotations

import json
import uuid
from datetime import timedelta
from pathlib import Path

import jsonschema
import pytest
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone

from apps.core.api import _celebracoes
from apps.gamificacao.cartas import (
    ASSUNTO_CONQUISTA,
    ASSUNTO_DESTAQUE,
    ASSUNTO_MARCO,
    ASSUNTO_NIVEL,
    AssuntoForaDoContrato,
    EventoForaDaTransacao,
    carta_de_celebracao,
)
from apps.gamificacao.models import (
    LancamentoDeXP,
    NivelDefinicao,
    OutboxEvent,
    PerfilJogador,
    Pessoa,
    RegraDePontuacao,
)
from apps.gamificacao.motor import aplicar, recalcular

pytestmark = pytest.mark.django_db

CONTRATO = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "eventos"
    / "notificacao.devida.v1.json"
)

SITE = "site-de-teste"
ALUNO = "pes-aluno-opaco"
EMAIL = "quem.sobe@exemplo.test"


# ---------------------------------------------------------------------------
# Peças
# ---------------------------------------------------------------------------
def _escada() -> None:
    """Três degraus ATIVOS. Nível 2 a partir de 10 XP, nível 3 a partir de 50."""
    for nivel, xp, titulo in (
        (1, 0, "Aprendiz"),
        (2, 10, "Modelador"),
        (3, 50, "Oficial"),
    ):
        NivelDefinicao.objects.create(
            nivel=nivel, site_id=SITE, xp_necessario=xp, titulo=titulo, ativa=True
        )


def _regra(**campos) -> RegraDePontuacao:
    """Uma regra LIGADA e já vigente — o banco recusa ligada sem data."""
    base = {
        "slug": "sugestao-criada",
        "site_id": SITE,
        "evento_gatilho": "sugestao.criada.v1",
        "beneficiario": RegraDePontuacao.Beneficiario.ATOR,
        "pontos": 10,
        "cristais": 0,
        "acoes_cheias_por_dia": 0,
        "quarentena_horas": 0,
        "ativa": True,
        "vigente_desde": timezone.now() - timedelta(days=365),
    }
    base.update(campos)
    return RegraDePontuacao.objects.create(**base)


def _evento(**campos) -> dict:
    """O envelope como o contrato o congelou. `ator_id` é o id de PLATAFORMA."""
    base = {
        "event": "sugestao.criada",
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "occurred_at": timezone.now().isoformat(),
        "ator_id": ALUNO,
        "data": {"site_id": SITE},
    }
    base.update(campos)
    return base


def _cartas() -> list[OutboxEvent]:
    return list(OutboxEvent.objects.order_by("id"))


def _no_fio(carta: OutboxEvent) -> dict:
    """O envelope como o relay o monta — a forma exata que vai para o fio."""
    envelope = {
        "event": carta.event,
        "version": carta.version,
        "event_id": str(carta.event_id),
        "occurred_at": carta.occurred_at.isoformat(),
        "data": carta.payload,
    }
    envelope.update(carta.envelope_extra)
    return envelope


def _conferir_contrato(envelope: dict) -> None:
    jsonschema.validate(envelope, json.loads(CONTRATO.read_text(encoding="utf-8")))


# ------------------------------------------- 1. a carta nasce com o fato


def test_subir_de_nivel_escreve_a_carta():
    _escada()
    _regra(pontos=10)
    fato = _evento()

    aplicar(fato, SITE)

    (carta,) = _cartas()
    assert carta.event == "notificacao.devida"
    assert carta.payload["assunto"] == ASSUNTO_NIVEL
    assert carta.payload["destinatario_id"] == ALUNO
    assert carta.payload["parametros"] == {"nivel": 2, "titulo_slug": "modelador"}
    # A TRILHA: de qualquer aviso se chega ao acontecimento que o causou. Sem
    # esta linha o campo existiria e apontaria para a própria carta, e a
    # promessa "rastreável" morreria na primeira delas.
    assert carta.payload["origem_event_id"] == fato["event_id"]


def test_a_carta_casa_com_o_contrato_congelado():
    _escada()
    _regra(pontos=10)

    aplicar(_evento(), SITE)

    (carta,) = _cartas()
    _conferir_contrato(_no_fio(carta))


@pytest.mark.django_db(transaction=True)
def test_a_carta_recusa_nascer_fora_da_transacao():
    """A Lei 1 aplicada: a própria função recusa, em vez de confiar na memória.

    `transaction=True` é o que torna este guarda possível: o `django_db` normal
    envolve cada teste numa transação, e dentro dela `in_atomic_block` é sempre
    verdadeiro — a recusa nunca dispararia e o teste passaria por acidente,
    medindo outra coisa.
    """
    with pytest.raises(EventoForaDaTransacao):
        carta_de_celebracao(
            site_id=SITE,
            destinatario_id=ALUNO,
            assunto=ASSUNTO_NIVEL,
            parametros={"nivel": 2, "titulo_slug": "modelador"},
        )


# ------------------------------------------- 2 e 3. só boa notícia, e só o degrau


def test_perder_xp_nao_gera_carta():
    """A regra que o mantenedor não vai ver funcionar, e é a que mais importa.

    Um estorno derruba o nível de volta. Se a comemoração olhasse "mudou de
    nível" em vez de "SUBIU de nível", a pessoa receberia um aviso festivo no
    segundo em que perdeu o ponto.
    """
    _escada()
    _regra(pontos=10)
    aplicar(_evento(), SITE)
    assert len(_cartas()) == 1
    assert PerfilJogador.objects.get().nivel == 2

    # O estorno é linha NOVA no ledger, nunca apagar (lei do modelo).
    pessoa = Pessoa.objects.get()
    LancamentoDeXP.objects.create(
        pessoa=pessoa,
        site_id=SITE,
        pontos=-10,
        origem_event_id=str(uuid.uuid4()),
        regra_slug="estorno",
        regra_versao=1,
        occurred_at=timezone.now(),
        dia_local=timezone.now().date(),
        status=LancamentoDeXP.Status.DEFINITIVO,
    )
    recalcular(ALUNO, SITE)

    assert PerfilJogador.objects.get().nivel == 1
    assert len(_cartas()) == 1, "descer de nível não pode escrever carta nenhuma"


def test_ganhar_xp_sem_trocar_de_degrau_nao_gera_carta():
    _escada()
    _regra(pontos=10, acoes_cheias_por_dia=0)
    aplicar(_evento(), SITE)
    assert len(_cartas()) == 1  # a subida para o nível 2

    # Mais 10 pontos: 20 no total, e o nível 3 só chega aos 50.
    aplicar(_evento(), SITE)

    assert PerfilJogador.objects.get().xp_total == 20
    assert PerfilJogador.objects.get().nivel == 2
    assert len(_cartas()) == 1, "o aviso é sobre o degrau, não sobre o placar"


def test_o_mesmo_fato_reentregue_nao_comemora_duas_vezes():
    """At-least-once no transporte: o mesmo evento CHEGA duas vezes, e chega mesmo.

    Quem recusa é a chave única do ledger, no PostgreSQL. Sem ela, uma reentrega
    somaria XP de novo — e, com o degrau já ultrapassado, escreveria a segunda
    carta da mesma subida.
    """
    _escada()
    _regra(pontos=10)
    fato = _evento()

    aplicar(fato, SITE)
    aplicar(fato, SITE)

    assert PerfilJogador.objects.get().xp_total == 10
    assert len(_cartas()) == 1


# ------------------------------------------- 4 e 5. o contrato manda


def test_os_quatro_assuntos_da_sessao_b_cabem_na_mesma_porta():
    """Os três que ainda não têm fato saem pelo caminho já provado.

    Medalha (degrau 12), marco validado (degrau 12) e destaque da semana
    (degrau 19) não têm, hoje, nada nesta célula que os conceda. O que este
    teste garante é que, quando tiverem, a carta sai sem contrato novo e sem
    código novo em `cartas.py` — e que a forma de cada uma já bate com o
    congelado.
    """
    parametros = {
        ASSUNTO_NIVEL: {"nivel": 7, "titulo_slug": "modelador"},
        ASSUNTO_CONQUISTA: {"conquista_slug": "primeira-obra", "familia": "oficio"},
        ASSUNTO_MARCO: {
            "conquista_slug": "primeiro-cliente",
            "validador_papel": "professor",
        },
        ASSUNTO_DESTAQUE: {"destaque_id": "dst-123", "semana": "2026-08-31"},
    }

    for assunto, parametro in parametros.items():
        carta = carta_de_celebracao(
            site_id=SITE,
            destinatario_id=ALUNO,
            assunto=assunto,
            parametros=parametro,
        )
        _conferir_contrato(_no_fio(carta))

    assert len(_cartas()) == 4


def test_assunto_fora_do_contrato_e_recusado_na_origem():
    """Fail-closed. Um assunto inventado seria gravado no sininho de alguém e
    apareceria como aviso mudo numa tela, sem ninguém saber de onde veio."""
    with pytest.raises(AssuntoForaDoContrato):
        carta_de_celebracao(
            site_id=SITE,
            destinatario_id=ALUNO,
            assunto="gamificacao.subiu-muito",
            parametros={},
        )
    assert _cartas() == []


# ------------------------------------------- 6. as duas metades da comemoração


def test_a_comemoracao_de_tela_entra_na_forma_que_a_porta_devolve():
    """A celebração visceral não pode nascer torta.

    A porta de máquina DESCARTA silenciosamente a linha que não casa com o
    vocabulário fechado (`tipo` + `referencia`), com um aviso só no log. Uma
    forma errada aqui não quebraria nada: a comemoração simplesmente nunca
    aconteceria, e ninguém descobriria por quê.
    """
    _escada()
    _regra(pontos=10)
    aplicar(_evento(), SITE)

    perfil = PerfilJogador.objects.get()
    devolvidas = _celebracoes(perfil)

    assert len(devolvidas) == 1
    assert devolvidas[0].tipo == "nivel-alcancado"
    assert devolvidas[0].referencia == "2"


def test_consertar_um_perfil_divergente_nao_comemora():
    """`reconciliar_perfis --consertar` repara a cópia; reparo não é conquista.

    O perfil atrasado em relação ao ledger "sobe" ao ser reparado. Comemorar ali
    mandaria uma carta sobre um fato que aconteceu semanas antes, pelo relógio da
    manutenção — e a pessoa receberia uma festa por algo que ela nem lembra ter
    feito.
    """
    _escada()
    _regra(pontos=10)
    aplicar(_evento(), SITE)
    assert len(_cartas()) == 1

    # A cópia é torcida À MÃO, que é exatamente o cenário que o comando existe
    # para achar: alguém escreveu no perfil por fora do motor.
    PerfilJogador.objects.update(nivel=1, xp_total=0)

    call_command("reconciliar_perfis", "--consertar")

    assert PerfilJogador.objects.get().nivel == 2
    assert len(_cartas()) == 1, "consertar a cópia não escreve carta"


# ------------------------------------------- 7. nada de PII no fio


def test_nenhuma_pii_viaja_na_carta():
    _escada()
    _regra(pontos=10)
    Pessoa.objects.create(id_da_plataforma=ALUNO, email=EMAIL, nome_exibido="Quem Sobe")

    aplicar(_evento(), SITE)

    (carta,) = _cartas()
    no_fio = json.dumps(_no_fio(carta), ensure_ascii=False)
    assert EMAIL not in no_fio
    assert "Quem Sobe" not in no_fio
    # E o `ator_id` é NULO de propósito: ninguém "concede" um nível — quem o
    # alcançou foi a própria pessoa.
    assert carta.envelope_extra == {"ator_id": None}


def test_a_carta_sai_com_transaction_on_commit_registrado():
    """O publish acontece DEPOIS do commit, e é isso que dá o aviso em segundos.

    `captureOnCommitCallbacks` é a única forma honesta de medir isto: dentro de
    um teste normal o commit nunca chega, e um `on_commit` esquecido passaria
    despercebido — a carta ficaria na outbox esperando o relay do minuto
    seguinte, sem nada acusar.
    """
    from django.test import TestCase

    _escada()
    _regra(pontos=10)

    with TestCase.captureOnCommitCallbacks(execute=False) as callbacks:
        with transaction.atomic():
            aplicar(_evento(), SITE)

    assert callbacks, "sem on_commit, o aviso só sairia no relay do minuto seguinte"
