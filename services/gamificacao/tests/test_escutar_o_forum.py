"""O que acontece no fórum vira ponto aqui, e a medalha "Mão amiga" passa a cair.

O fórum ganhou voz na mesma data (degrau 17, célula `forum`); esta é a outra
metade da ponte. Sem ela, ele grita no fio e ninguém escuta.

O QUE ESTE ARQUIVO TRAVA:

1. **O prêmio vai para quem ESCREVEU, não para quem marcou.** São pessoas
   diferentes, e o contrato carrega os dois ids exatamente para que ninguém
   confunda. Creditar o marcador seria pagar a pessoa errada em silêncio — e
   ninguém descobre isso olhando a tela.
2. **A medalha não depende da regra de XP estar ligada.** Reconhecimento é uma
   coisa, pagamento é outra: o mantenedor desliga a regra por uma semana e a
   medalha continua existindo.
3. **Marcar, desmarcar e remarcar conta UMA ajuda.** Se a chave fosse o evento,
   dois amigos alternando a marca fabricariam a medalha em minutos.
4. **A mensagem removida não é creditada**, e o motivo está declarado em código
   (`NAO_CREDITAM`) — não escondido num handler que ninguém escreveu.
5. **De quem é cada conversa fica GRAVADO, com a economia desligada** (02/09/2026,
   fundação do degrau 19). O Destaque da semana precisa do id opaco de quem
   abriu para endereçar a carta de parabéns, e esse id só existe no evento: o
   fórum devolve o nome de EXIBIÇÃO do autor, nunca o id.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.gamificacao.criterios import avaliar
from apps.gamificacao.handlers import HANDLERS, NAO_CREDITAM
from apps.gamificacao.models import (
    AjudaAceita,
    Concessao,
    ConversaAberta,
    ConquistaDefinicao,
    LancamentoDeXP,
    Pessoa,
    RegraDePontuacao,
)

pytestmark = pytest.mark.django_db

SITE = "site-de-teste"
QUEM_ESCREVEU = "pes-ajudou"
QUEM_MARCOU = "pes-perguntou"


def _regra(**campos) -> RegraDePontuacao:
    base = {
        "slug": "forum-resposta-aceita",
        "site_id": SITE,
        "evento_gatilho": "forum.resposta-aceita.v1",
        "beneficiario": RegraDePontuacao.Beneficiario.AUTOR_DO_ALVO,
        "pontos": 50,
        "cristais": 0,
        "acoes_cheias_por_dia": 0,
        "quarentena_horas": 0,
        "ativa": True,
        "vigente_desde": timezone.now() - timedelta(days=365),
    }
    base.update(campos)
    return RegraDePontuacao.objects.create(**base)


def _resposta_aceita(**campos) -> dict:
    """O envelope como `contracts/eventos/forum.resposta-aceita.v1.json` o fixa."""
    data = {
        "site_id": SITE,
        "topico_id": "7",
        "mensagem_id": "42",
        "autor_da_resposta_id": QUEM_ESCREVEU,
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


def _entregar(envelope: dict) -> None:
    """O caminho real: o consumidor acha o handler pelo assunto e o chama."""
    HANDLERS[envelope["event"]](envelope)


# ------------------------------------------- 1. quem recebe o prêmio


def test_a_resposta_aceita_paga_quem_escreveu_e_nao_quem_marcou():
    _regra()

    _entregar(_resposta_aceita())

    (lancamento,) = LancamentoDeXP.objects.all()
    assert lancamento.pessoa_id == QUEM_ESCREVEU
    assert lancamento.pontos == 50
    assert not LancamentoDeXP.objects.filter(pessoa_id=QUEM_MARCOU).exists()


def test_abrir_conversa_e_falar_pagam_quem_agiu():
    _regra(
        slug="forum-topico-criado",
        evento_gatilho="forum.topico-criado.v1",
        beneficiario=RegraDePontuacao.Beneficiario.ATOR,
        pontos=8,
    )
    _regra(
        slug="forum-mensagem",
        evento_gatilho="forum.mensagem-criada.v1",
        beneficiario=RegraDePontuacao.Beneficiario.ATOR,
        pontos=5,
    )

    _entregar(
        {
            "event": "forum.topico-criado",
            "version": 1,
            "event_id": str(uuid.uuid4()),
            "occurred_at": timezone.now().isoformat(),
            "ator_id": QUEM_MARCOU,
            "data": {"site_id": SITE, "topico_id": "7", "area_id": "1"},
        }
    )
    _entregar(
        {
            "event": "forum.mensagem-criada",
            "version": 1,
            "event_id": str(uuid.uuid4()),
            "occurred_at": timezone.now().isoformat(),
            "ator_id": QUEM_MARCOU,
            "data": {
                "site_id": SITE,
                "mensagem_id": "42",
                "topico_id": "7",
                "area_id": "1",
                "caracteres": 120,
            },
        }
    )

    assert sorted(
        LancamentoDeXP.objects.filter(pessoa_id=QUEM_MARCOU).values_list(
            "pontos", flat=True
        )
    ) == [5, 8]


# ------------------------------------------- 2. a ajuda, e a medalha


def test_a_ajuda_e_registrada_mesmo_com_a_regra_de_xp_desligada():
    """Reconhecimento é uma coisa, pagamento é outra.

    Sem esta separação, o mantenedor desligaria a regra por uma semana e a
    medalha "Mão amiga" pararia de existir junto, sem ninguém entender por quê.
    """
    _entregar(_resposta_aceita())

    assert LancamentoDeXP.objects.count() == 0, "sem regra ligada, ninguém paga"
    ajuda = AjudaAceita.objects.get()
    assert ajuda.pessoa_id == QUEM_ESCREVEU
    assert ajuda.mensagem_id == "42"
    # A ARESTA "A premiou B", de que a detecção de anéis depende.
    assert ajuda.quem_marcou == QUEM_MARCOU
    assert ajuda.marcada_por == "autor"


def test_marcar_desmarcar_e_remarcar_conta_uma_ajuda_so():
    """Se a chave fosse o evento, dois amigos alternando a marca fabricariam a
    medalha em minutos."""
    _entregar(_resposta_aceita())
    _entregar(_resposta_aceita())  # event_id novo, MESMA mensagem
    _entregar(_resposta_aceita())

    assert AjudaAceita.objects.count() == 1


def test_a_medalha_mao_amiga_cai_com_cinco_ajudas():
    """A primeira medalha automática que esta escola consegue conceder de verdade."""
    ConquistaDefinicao.objects.create(
        slug="mao-amiga",
        site_id=SITE,
        nome="Mão amiga",
        classe=ConquistaDefinicao.Classe.MEDALHA,
        familia=ConquistaDefinicao.Familia.COMUNIDADE,
        criterio={"tipo": "respostas_aceitas", "alvo": 5},
        pontos=100,
        cristais=0,
        ativa=True,
    )

    for numero in range(4):
        _entregar(_resposta_aceita(data={"mensagem_id": str(numero)}))
    assert avaliar(QUEM_ESCREVEU, SITE) == [], "quatro ainda não são cinco"

    _entregar(_resposta_aceita(data={"mensagem_id": "quinta"}))
    novas = avaliar(QUEM_ESCREVEU, SITE)

    assert [c.conquista.slug for c in novas] == ["mao-amiga"]
    assert Concessao.objects.get().pessoa_id == QUEM_ESCREVEU


# ------------------------------------------- 3. o que não entra, e por quê


def test_a_mensagem_removida_nao_tem_handler_e_o_motivo_esta_declarado():
    """Assinar um assunto que esta célula não sabe tratar encheria o log de
    "handler desconhecido" e daria a impressão de que o estorno acontece.

    O guarda existe para que a declaração e a realidade não divirjam: no dia em
    que o estorno for construído, apagar a linha de `NAO_CREDITAM` é PARTE de
    construí-lo, e este teste é o que obriga a lembrar.
    """
    assert "forum.mensagem-removida" not in HANDLERS
    assert "forum.mensagem-removida" in NAO_CREDITAM
    assert "ledger guarda o id do EVENTO" in NAO_CREDITAM["forum.mensagem-removida"]


def test_resposta_aceita_sem_autor_nao_credita_ninguem():
    """Fail-closed: sem quem recebe, não se inventa um dono para o ponto."""
    _regra()

    _entregar(_resposta_aceita(data={"autor_da_resposta_id": ""}))

    assert LancamentoDeXP.objects.count() == 0
    assert AjudaAceita.objects.count() == 0


# ------------------------------------------- 4. de quem é cada conversa
#
# 02/09/2026, fundação do degrau 19 (a Galeria e os Destaques da semana). Quem
# escolhe um trabalho para destacar o vê pelo fórum (`listRecentTopics`), que
# devolve o TÍTULO e o NOME DE EXIBIÇÃO do autor. Nome de exibição não endereça
# carta nenhuma: o id opaco de quem abriu só existe no `ator_id` do envelope, e
# até aqui ele chegava e era jogado fora.

QUEM_ABRIU = "pes-abriu-a-conversa"
OUTRA_ESCOLA = "site-de-outra-escola"


def _topico_criado(**campos) -> dict:
    """O envelope como `contracts/eventos/forum.topico-criado.v1.json` o fixa."""
    data = {"site_id": SITE, "topico_id": "7", "area_id": "1"}
    data.update(campos.pop("data", {}))
    base = {
        "event": "forum.topico-criado",
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "occurred_at": timezone.now().isoformat(),
        "ator_id": QUEM_ABRIU,
        "data": data,
    }
    base.update(campos)
    return base


def test_de_quem_e_a_conversa_e_gravado_com_a_economia_desligada():
    """O teste que decide se o degrau 19 nasce vivo ou morto.

    A economia desta escola está DESLIGADA hoje: nenhuma regra de pontuação
    ativa, nenhum XP creditado. Se o registro de quem abriu dependesse do
    crédito, esta tabela nasceria vazia e continuaria vazia, e a tela de escolher
    os destaques abriria sem nada para escolher, sem ninguém entender por quê.

    É a mesma lei de `AjudaAceita`, e ela vale aqui pela mesma razão:
    reconhecimento é uma coisa, pagamento é outra.
    """
    _entregar(_topico_criado())

    assert LancamentoDeXP.objects.count() == 0, "sem regra ligada, ninguém paga"
    conversa = ConversaAberta.objects.get()
    assert conversa.pessoa_id == QUEM_ABRIU
    assert conversa.topico_id == "7"
    assert conversa.site_id == SITE


def test_a_mesma_conversa_reentregue_nao_vira_duas_linhas():
    """A chave é o TÓPICO, não o evento.

    Uma discussão é aberta uma vez, por uma pessoa. Com a chave no `event_id`,
    uma reentrega do relay mostraria a mesma conversa duas vezes na tela de
    escolher o destaque, e a equipe destacaria duas vezes o mesmo trabalho.
    """
    envelope = _topico_criado()
    _entregar(envelope)
    _entregar(envelope)  # o MESMO evento, reentregue pelo relay
    _entregar(_topico_criado())  # event_id novo, MESMO tópico

    assert ConversaAberta.objects.count() == 1
    assert ConversaAberta.objects.get().pessoa_id == QUEM_ABRIU


def test_topico_sem_ator_no_envelope_nao_inventa_dono():
    """Fail-closed: sem quem abriu, não se inventa um dono para a conversa.

    O contrato do evento declara `ator_id` obrigatório e não anulável, mas quem
    consome fato de outra célula não confia na promessa. Um envelope torto que
    virasse linha mandaria a carta de parabéns para uma pessoa inventada, e a
    tela afirmaria o contrário com todas as letras.
    """
    _entregar(_topico_criado(ator_id=""))
    sem_a_chave = _topico_criado()
    del sem_a_chave["ator_id"]
    _entregar(sem_a_chave)

    assert ConversaAberta.objects.count() == 0
    assert Pessoa.objects.count() == 0, "nem a pessoa espelho é inventada"


def test_a_conversa_de_outra_escola_nao_entra_nesta():
    """O id do tópico é do fórum DAQUELA escola: o tópico 7 de duas é duas.

    A plataforma já serve mais de um site, e o `site_id` vem do EVENTO. Sem ele
    na chave, a conversa da segunda escola encontraria a linha da primeira e não
    seria gravada — o Destaque de uma escola daria o crédito a alguém da outra,
    e nada ficaria vermelho.
    """
    _entregar(_topico_criado())
    _entregar(
        _topico_criado(
            ator_id="pes-de-outra-escola",
            data={"site_id": OUTRA_ESCOLA},  # MESMO topico_id "7"
        )
    )

    daqui = ConversaAberta.objects.filter(site_id=SITE)
    assert [c.pessoa_id for c in daqui] == [QUEM_ABRIU]
    de_la = ConversaAberta.objects.filter(site_id=OUTRA_ESCOLA)
    assert [c.pessoa_id for c in de_la] == ["pes-de-outra-escola"]
