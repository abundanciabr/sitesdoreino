"""A espinha do sistema: um marco real, uma pessoa da escola, e um sim.

Tudo o que a célula fazia até aqui media o que acontece DENTRO do site. O marco
real acontece fora — a primeira obra terminada, o primeiro cliente, os primeiros
dólares — e nenhuma máquina consegue contá-lo. Este arquivo trava o caminho pelo
qual alguém da escola olha a prova e diz sim, e as defesas que esse caminho
precisa ter para não virar o contrário do que promete.

O QUE ESTÁ TRAVADO AQUI, e por que cada uma importa:

1. **Marco rende ZERO XP.** Se o primeiro cliente pagasse pontos, o marco seria
   mais um item do andaime e o aluno perseguiria o número em vez da coisa.
2. **Ninguém valida o próprio marco.** Um reconhecimento que a pessoa se dá
   sozinha não reconhece nada.
3. **Um par não fecha marco de dinheiro.** A definição já exige a equipe; a
   definição não sabe quem está clicando, e é aqui que se sabe.
4. **Devolver exige motivo da lista fechada.** É a diferença entre um processo e
   uma humilhação: o aluno recebe "falta a evidência", nunca a opinião de alguém
   sobre o trabalho dele.
5. **Duas devoluções de par escalam para a equipe.** O anti-anel, e ele é
   automático: não depende de o aluno reclamar, que é o que ele não vai fazer.
6. **O prazo é em dias ÚTEIS.** Um pedido de sexta à noite não vence no domingo,
   quando não há ninguém para atendê-lo.
7. **A evidência nunca viaja na carta.** Marco de dinheiro carrega print de
   pagamento; isso não passa por fila de evento nenhuma.
8. **Conceder é idempotente.** A conquista é uma só, e a carta também.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import jsonschema
import pytest
from django.core.management import call_command
from django.db.utils import IntegrityError
from django.utils import timezone

from apps.gamificacao.cartas import ASSUNTO_CONQUISTA, ASSUNTO_MARCO
from apps.gamificacao.models import (
    Concessao,
    ConquistaDefinicao,
    LancamentoDeXP,
    MovimentoDeCristais,
    NivelDefinicao,
    OutboxEvent,
    PedidoDeValidacao,
    PerfilJogador,
    Pessoa,
)
from apps.gamificacao.validacao import (
    DEVOLUCOES_DE_PAR_ATE_ESCALAR,
    PedidoInvalido,
    ValidacaoRecusada,
    aceitar,
    conceder,
    devolver,
    fila_da_equipe,
    pedir_validacao,
    prazo_de,
    reenviar,
)

pytestmark = pytest.mark.django_db

CONTRATO = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "eventos"
    / "notificacao.devida.v1.json"
)

SITE = "site-de-teste"
ALUNO = "pes-aluno"
PROFESSOR = "pes-professor"
COLEGA = "pes-colega"
SAO_PAULO = ZoneInfo("America/Sao_Paulo")


# ---------------------------------------------------------------------------
# Peças
# ---------------------------------------------------------------------------
def _pessoa(id_da_plataforma=ALUNO) -> Pessoa:
    return Pessoa.objects.create(
        id_da_plataforma=id_da_plataforma, email=f"{id_da_plataforma}@exemplo.test"
    )


def _marco(**campos) -> ConquistaDefinicao:
    """Um marco LIGADO. Marco rende zero XP, e o banco recusa o contrário."""
    base = {
        "slug": "portfolio-publicado",
        "site_id": SITE,
        "nome": "Portfólio no ar",
        "classe": ConquistaDefinicao.Classe.MARCO,
        "familia": ConquistaDefinicao.Familia.CARREIRA,
        "criterio": {"tipo": "manual"},
        "pontos": 0,
        "cristais": 0,
        "ativa": True,
    }
    base.update(campos)
    return ConquistaDefinicao.objects.create(**base)


def _medalha(**campos) -> ConquistaDefinicao:
    base = {
        "slug": "primeira-obra",
        "site_id": SITE,
        "nome": "Primeira obra",
        "classe": ConquistaDefinicao.Classe.MEDALHA,
        "familia": ConquistaDefinicao.Familia.OFICIO,
        "criterio": {"tipo": "manual"},
        "pontos": 50,
        "cristais": 5,
        "ativa": True,
    }
    base.update(campos)
    return ConquistaDefinicao.objects.create(**base)


def _cartas() -> list[OutboxEvent]:
    return list(OutboxEvent.objects.order_by("id"))


def _no_fio(carta: OutboxEvent) -> dict:
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


# ------------------------------------------- 1. o caminho feliz


def test_aceitar_um_marco_cria_a_concessao_e_avisa_a_pessoa():
    pessoa = _pessoa()
    marco = _marco()
    pedido = pedir_validacao(
        pessoa=pessoa, site_id=SITE, conquista=marco, evidencia="meu-portfolio.test"
    )

    concessao = aceitar(
        pedido=pedido,
        validador_id=PROFESSOR,
        validador_papel=Concessao.PapelDoValidador.PROFESSOR,
    )

    assert concessao.conquista_id == marco.pk
    # A AUDITORIA: "quem disse que sim?" precisa ter resposta meses depois.
    assert concessao.validador_id == PROFESSOR
    assert concessao.validador_papel == Concessao.PapelDoValidador.PROFESSOR
    # E nada é exposto sem ação explícita do aluno.
    assert concessao.consentimento == Concessao.Consentimento.PRIVADO

    pedido.refresh_from_db()
    assert pedido.estado == PedidoDeValidacao.Estado.ACEITO
    assert pedido.respondido_em is not None

    (carta,) = _cartas()
    assert carta.payload["assunto"] == ASSUNTO_MARCO
    assert carta.payload["destinatario_id"] == ALUNO
    assert carta.payload["parametros"] == {
        "conquista_slug": "portfolio-publicado",
        "validador_papel": "professor",
    }
    _conferir_contrato(_no_fio(carta))


def test_marco_rende_zero_xp():
    """A hierarquia da lei: realidade acima do jogo, e o jogo não paga por ela.

    Se conseguir o primeiro cliente pagasse 500 XP, o marco viraria mais um item
    do andaime — e o aluno aprenderia a perseguir o número em vez da coisa.
    """
    pessoa = _pessoa()
    NivelDefinicao.objects.create(
        nivel=2, site_id=SITE, xp_necessario=10, titulo="Modelador", ativa=True
    )
    pedido = pedir_validacao(pessoa=pessoa, site_id=SITE, conquista=_marco())

    aceitar(
        pedido=pedido,
        validador_id=PROFESSOR,
        validador_papel=Concessao.PapelDoValidador.PROFESSOR,
    )

    assert LancamentoDeXP.objects.count() == 0
    assert PerfilJogador.objects.get().xp_total == 0
    assert PerfilJogador.objects.get().nivel == 1


def test_a_medalha_credita_xp_e_cristais_e_o_perfil_acompanha():
    """A medalha é o outro lado: ela paga, e paga pela origem certa.

    `conquista` é UMA das cinco origens legítimas de Cristal — a moeda nasce de
    esforço, e a lista mora no banco. É por isso que uma medalha pode pagar
    Cristal e uma regra de evento não.
    """
    pessoa = _pessoa()
    medalha = _medalha()

    concessao, nova = conceder(pessoa=pessoa, site_id=SITE, conquista=medalha)

    assert nova is True
    assert concessao.validador_papel == Concessao.PapelDoValidador.SISTEMA
    assert LancamentoDeXP.objects.get().pontos == 50
    movimento = MovimentoDeCristais.objects.get()
    assert movimento.delta == 5
    assert movimento.origem == MovimentoDeCristais.Origem.CONQUISTA
    assert movimento.referencia == "conquista:primeira-obra"

    # A CÓPIA NÃO PODE MENTIR: sem o recálculo, o razão teria a moeda e a tela do
    # aluno mostraria o saldo de antes, sem erro em lugar nenhum.
    perfil = PerfilJogador.objects.get()
    assert perfil.xp_total == 50
    assert perfil.cristais_saldo == 5

    (carta,) = _cartas()
    assert carta.payload["assunto"] == ASSUNTO_CONQUISTA
    assert carta.payload["parametros"] == {
        "conquista_slug": "primeira-obra",
        "familia": "oficio",
    }
    _conferir_contrato(_no_fio(carta))


def test_conceder_duas_vezes_da_uma_conquista_e_uma_carta():
    """A idempotência que faz o backfill do Fundador poder ser re-executado."""
    pessoa = _pessoa()
    medalha = _medalha()

    primeira, nova = conceder(pessoa=pessoa, site_id=SITE, conquista=medalha)
    segunda, de_novo = conceder(pessoa=pessoa, site_id=SITE, conquista=medalha)

    assert nova is True and de_novo is False
    assert primeira.pk == segunda.pk
    assert Concessao.objects.count() == 1
    assert len(_cartas()) == 1
    assert LancamentoDeXP.objects.count() == 1
    assert PerfilJogador.objects.get().cristais_saldo == 5


# ------------------------------------------- 2. quem pode decidir


def test_ninguem_valida_o_proprio_marco():
    pessoa = _pessoa()
    pedido = pedir_validacao(pessoa=pessoa, site_id=SITE, conquista=_marco())

    with pytest.raises(ValidacaoRecusada, match="próprio marco"):
        aceitar(
            pedido=pedido,
            validador_id=ALUNO,
            validador_papel=Concessao.PapelDoValidador.PROFESSOR,
        )

    assert Concessao.objects.count() == 0
    assert _cartas() == []


def test_um_colega_nao_fecha_marco_de_dinheiro():
    """A definição exige a equipe; só aqui se sabe QUEM está clicando."""
    pessoa = _pessoa()
    marco = _marco(
        slug="primeiros-dolares",
        nome="Primeiros dólares",
        envolve_dinheiro=True,
        exige_validador_da_equipe=True,
    )
    pedido = pedir_validacao(pessoa=pessoa, site_id=SITE, conquista=marco)

    with pytest.raises(ValidacaoRecusada, match="só a equipe"):
        aceitar(
            pedido=pedido,
            validador_id=COLEGA,
            validador_papel=Concessao.PapelDoValidador.PAR,
        )

    # E a mesma linha, pela equipe, passa.
    aceitar(
        pedido=pedido,
        validador_id=PROFESSOR,
        validador_papel=Concessao.PapelDoValidador.PROFESSOR,
    )
    assert Concessao.objects.count() == 1


def test_o_papel_sistema_nao_decide_pedido_de_gente():
    pessoa = _pessoa()
    pedido = pedir_validacao(pessoa=pessoa, site_id=SITE, conquista=_marco())

    with pytest.raises(ValidacaoRecusada, match="sistema"):
        aceitar(
            pedido=pedido,
            validador_id="",
            validador_papel=Concessao.PapelDoValidador.SISTEMA,
        )


def test_o_banco_recusa_concessao_humana_sem_nome():
    """A trava de baixo, para o caso de alguém chegar por fora deste arquivo."""
    pessoa = _pessoa()
    with pytest.raises(IntegrityError):
        Concessao.objects.create(
            pessoa=pessoa,
            site_id=SITE,
            conquista=_marco(),
            validador_id="",
            validador_papel=Concessao.PapelDoValidador.PROFESSOR,
        )


# ------------------------------------------- 3. a devolução, e o anti-anel


def test_devolver_exige_motivo_da_lista_fechada():
    pessoa = _pessoa()
    pedido = pedir_validacao(pessoa=pessoa, site_id=SITE, conquista=_marco())

    with pytest.raises(ValidacaoRecusada, match="não é um dos motivos"):
        devolver(
            pedido=pedido,
            validador_id=PROFESSOR,
            validador_papel=Concessao.PapelDoValidador.PROFESSOR,
            motivo="não gostei do trabalho",
        )

    devolver(
        pedido=pedido,
        validador_id=PROFESSOR,
        validador_papel=Concessao.PapelDoValidador.PROFESSOR,
        motivo=PedidoDeValidacao.MotivoDaDevolucao.FALTA_EVIDENCIA,
    )
    pedido.refresh_from_db()
    assert pedido.estado == PedidoDeValidacao.Estado.DEVOLVIDO
    assert pedido.motivo_da_devolucao == "falta_evidencia"
    # Devolver não avisa ninguém: só boa notícia vira carta.
    assert _cartas() == []


def test_duas_devolucoes_de_par_escalam_para_a_equipe():
    """Se um grupo combinar de recusar alguém, o caminho termina na escola."""
    pessoa = _pessoa()
    pedido = pedir_validacao(pessoa=pessoa, site_id=SITE, conquista=_marco())

    for volta in range(DEVOLUCOES_DE_PAR_ATE_ESCALAR):
        devolver(
            pedido=pedido,
            validador_id=COLEGA,
            validador_papel=Concessao.PapelDoValidador.PAR,
            motivo=PedidoDeValidacao.MotivoDaDevolucao.FORA_DO_CRITERIO,
        )
        pedido.refresh_from_db()
        if volta + 1 < DEVOLUCOES_DE_PAR_ATE_ESCALAR:
            assert not pedido.escalado_para_adulto
            reenviar(pedido=pedido, evidencia="tentei de novo")

    assert pedido.escalado_para_adulto is True


def test_reenviar_recomeca_o_prazo_e_nao_zera_o_contador():
    """Zerar o contador daria devoluções infinitas a quem quisesse fritar alguém."""
    pessoa = _pessoa()
    pedido = pedir_validacao(pessoa=pessoa, site_id=SITE, conquista=_marco())
    devolver(
        pedido=pedido,
        validador_id=COLEGA,
        validador_papel=Concessao.PapelDoValidador.PAR,
        motivo=PedidoDeValidacao.MotivoDaDevolucao.EVIDENCIA_ILEGIVEL,
    )
    # O pedido envelhece: o prazo dele já venceu há três dias. Sem envelhecer, o
    # teste rodaria rápido demais para distinguir "recomeçou" de "não mexeu" — os
    # dois prazos cairiam no mesmo instante e a asserção passaria por acidente.
    vencido = timezone.now() - timedelta(days=3)
    PedidoDeValidacao.objects.filter(pk=pedido.pk).update(prazo_ate=vencido)
    pedido.refresh_from_db()

    reenviar(pedido=pedido, evidencia="agora dá para ler")

    pedido.refresh_from_db()
    assert pedido.estado == PedidoDeValidacao.Estado.EM_ANALISE
    assert pedido.devolucoes == 1
    assert pedido.motivo_da_devolucao == ""
    assert pedido.prazo_ate > timezone.now()


def test_pedir_adulto_escala_na_primeira_vez():
    """O motivo existe justamente para o par dizer 'isto não é comigo'."""
    pessoa = _pessoa()
    pedido = pedir_validacao(pessoa=pessoa, site_id=SITE, conquista=_marco())

    devolver(
        pedido=pedido,
        validador_id=COLEGA,
        validador_papel=Concessao.PapelDoValidador.PAR,
        motivo=PedidoDeValidacao.MotivoDaDevolucao.PRECISA_DE_ADULTO,
    )

    pedido.refresh_from_db()
    assert pedido.escalado_para_adulto is True


# ------------------------------------------- 4. a porta do pedido


def test_conquista_desligada_nao_aceita_pedido():
    pessoa = _pessoa()
    with pytest.raises(PedidoInvalido, match="ainda não está no ar"):
        pedir_validacao(pessoa=pessoa, site_id=SITE, conquista=_marco(ativa=False))


def test_nao_se_pede_o_que_ja_se_tem_nem_o_que_ja_esta_na_fila():
    pessoa = _pessoa()
    marco = _marco()
    pedir_validacao(pessoa=pessoa, site_id=SITE, conquista=marco)

    with pytest.raises(PedidoInvalido, match="já está na fila"):
        pedir_validacao(pessoa=pessoa, site_id=SITE, conquista=marco)

    conceder(pessoa=pessoa, site_id=SITE, conquista=marco)
    with pytest.raises(PedidoInvalido, match="já tem"):
        pedir_validacao(pessoa=pessoa, site_id=SITE, conquista=marco)


def test_medalha_nao_se_pede():
    pessoa = _pessoa()
    with pytest.raises(PedidoInvalido, match="é uma medalha"):
        pedir_validacao(pessoa=pessoa, site_id=SITE, conquista=_medalha())


# ------------------------------------------- 5. o prazo, em dias úteis


def test_o_prazo_pula_o_fim_de_semana():
    """Sexta-feira à noite: o marco vence na sexta seguinte, não no domingo.

    Prazo que corre enquanto a escola dorme não mede atraso — mede fim de semana,
    e uma fila que mostra atraso falso ensina a equipe a ignorar a cor vermelha.
    """
    sexta = datetime(2026, 9, 4, 21, 0, tzinfo=SAO_PAULO)
    assert sexta.weekday() == 4

    marco = prazo_de(PedidoDeValidacao.Tipo.MARCO, a_partir_de=sexta)
    resposta = prazo_de(PedidoDeValidacao.Tipo.AJUDA, a_partir_de=sexta)

    # 5 dias úteis a partir de sexta = a sexta seguinte (7 dias de calendário).
    assert marco.date() == (sexta + timedelta(days=7)).date()
    assert marco.weekday() == 4
    # 2 dias úteis a partir de sexta = terça (4 dias de calendário).
    assert resposta.date() == (sexta + timedelta(days=4)).date()
    assert resposta.weekday() == 1


def test_o_pedido_nasce_com_prazo_e_em_analise():
    """ "Em análise" é o nome do estado inicial, e o nome é a decisão: esperar
    nunca pode parecer recusa."""
    pessoa = _pessoa()
    pedido = pedir_validacao(pessoa=pessoa, site_id=SITE, conquista=_marco())

    assert pedido.estado == PedidoDeValidacao.Estado.EM_ANALISE
    assert pedido.prazo_ate is not None
    assert pedido.prazo_ate > timezone.now()
    # A evidência nasce privada: marco de dinheiro carrega print de pagamento.
    assert pedido.evidencia_privada is True


def test_a_fila_da_equipe_mostra_o_mais_urgente_primeiro():
    """Ordenar por data de criação mostraria o mais VELHO, que é outra coisa:
    os prazos são de 2 e de 5 dias úteis, e o mais novo pode vencer antes."""
    pessoa = _pessoa()
    outro = _pessoa("pes-outro")
    marco = _marco()
    devagar = pedir_validacao(pessoa=pessoa, site_id=SITE, conquista=marco)
    urgente = pedir_validacao(
        pessoa=outro, site_id=SITE, tipo=PedidoDeValidacao.Tipo.AJUDA
    )

    fila = list(fila_da_equipe(SITE))

    assert [p.pk for p in fila] == [urgente.pk, devagar.pk]

    aceitar(
        pedido=devagar,
        validador_id=PROFESSOR,
        validador_papel=Concessao.PapelDoValidador.PROFESSOR,
    )
    assert [p.pk for p in fila_da_equipe(SITE)] == [urgente.pk]


# ------------------------------------------- 6. o que não pode vazar


def test_a_evidencia_nunca_viaja_na_carta():
    pessoa = _pessoa()
    marco = _marco(
        slug="primeiro-cliente",
        nome="Primeiro cliente",
        envolve_dinheiro=True,
        exige_validador_da_equipe=True,
    )
    segredo = "print-do-pagamento-de-R$-800-do-cliente-fulano"
    pedido = pedir_validacao(
        pessoa=pessoa, site_id=SITE, conquista=marco, evidencia=segredo
    )

    aceitar(
        pedido=pedido,
        validador_id=PROFESSOR,
        validador_papel=Concessao.PapelDoValidador.PROFESSOR,
    )

    (carta,) = _cartas()
    no_fio = json.dumps(_no_fio(carta), ensure_ascii=False)
    assert segredo not in no_fio
    assert "@exemplo.test" not in no_fio


def test_reconciliar_confere_a_moeda_tambem():
    """A promessa nova do perfil: `cristais_saldo` é cópia, e cópia se prova de fora."""
    pessoa = _pessoa()
    conceder(pessoa=pessoa, site_id=SITE, conquista=_medalha())

    PerfilJogador.objects.update(cristais_saldo=999)
    call_command("reconciliar_perfis", "--consertar")

    assert PerfilJogador.objects.get().cristais_saldo == 5
