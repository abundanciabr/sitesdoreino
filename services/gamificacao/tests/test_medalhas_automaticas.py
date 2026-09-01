"""As medalhas que a escola concede sozinha, e os limites honestos delas.

O marco real se PEDE; a medalha cai quando a conta bate. Este arquivo trava a
conta — e, tão importante quanto, trava o que ela NÃO faz.

O QUE ESTÁ GUARDADO AQUI:

1. **Ligar uma medalha reconhece quem já cumpriu.** É a decisão do mantenedor no
   Rito de 01/09/2026: quem já tinha o XP quando a medalha foi ligada a recebe.
   O contrário negaria a "Primeira obra" a quem já fez a primeira obra.
2. **Marco real NUNCA cai por conta.** Conceder um por cálculo seria a escola
   afirmar que alguém conseguiu um cliente sem ninguém ter olhado.
3. **Medalha desligada não cai.** A economia inteira nasce desligada, e ligar é
   decisão do mantenedor.
4. **A cadeia termina.** Uma medalha paga XP, o XP sobe o nível, e o nível pode
   alcançar outra medalha: o motor resolve isso num laço, sem recursão infinita.
5. **Critério fora do vocabulário não concede nada**, e não estoura. É o
   critério de morte nº 1 da lei tendo um lugar concreto onde acontece.
6. **Os critérios sem fato devolvem zero de verdade**, lendo a tabela vazia — e
   não um número inventado que pareça medido.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.gamificacao.criterios import avaliar, cumpre
from apps.gamificacao.models import (
    Concessao,
    ConquistaDefinicao,
    Forja,
    LancamentoDeXP,
    NivelDefinicao,
    OutboxEvent,
    PerfilJogador,
    Pessoa,
    RegraDePontuacao,
)
from apps.gamificacao.motor import aplicar, recalcular

pytestmark = pytest.mark.django_db

SITE = "site-de-teste"
ALUNO = "pes-aluno"


def _pessoa() -> Pessoa:
    return Pessoa.objects.create(id_da_plataforma=ALUNO, email="a@exemplo.test")


def _perfil(xp: int = 0) -> PerfilJogador:
    pessoa = Pessoa.objects.filter(id_da_plataforma=ALUNO).first() or _pessoa()
    perfil, _ = PerfilJogador.objects.get_or_create(pessoa=pessoa, site_id=SITE)
    if xp:
        LancamentoDeXP.objects.create(
            pessoa=pessoa,
            site_id=SITE,
            pontos=xp,
            origem_event_id=str(uuid.uuid4()),
            regra_slug="semente",
            regra_versao=1,
            occurred_at=timezone.now(),
            dia_local=timezone.now().date(),
        )
        perfil = recalcular(ALUNO, SITE)
    return perfil


def _medalha(**campos) -> ConquistaDefinicao:
    base = {
        "slug": "veterano",
        "site_id": SITE,
        "nome": "Veterano",
        "classe": ConquistaDefinicao.Classe.MEDALHA,
        "familia": ConquistaDefinicao.Familia.OFICIO,
        "criterio": {"tipo": "xp_acumulado", "alvo": 300},
        "pontos": 0,
        "cristais": 0,
        "ativa": True,
    }
    base.update(campos)
    return ConquistaDefinicao.objects.create(**base)


# ------------------------------------------- 1. reconhecer quem já cumpriu


def test_ligar_uma_medalha_reconhece_quem_ja_tinha_o_numero():
    """A decisão do mantenedor, virando comportamento.

    A pessoa acumulou 500 XP quando a medalha dos 300 nem existia. Ligar a medalha
    e depois avaliar tem de conceder — negar seria punir quem chegou cedo.
    """
    _perfil(xp=500)
    _medalha(criterio={"tipo": "xp_acumulado", "alvo": 300})

    novas = avaliar(ALUNO, SITE)

    assert [c.conquista.slug for c in novas] == ["veterano"]
    concessao = Concessao.objects.get()
    # O papel do validador é `sistema`: é o único sem pessoa por trás, e a
    # pergunta "quem disse que sim?" tem esta resposta honesta.
    assert concessao.validador_papel == Concessao.PapelDoValidador.SISTEMA
    assert concessao.validador_id == ""


def test_quem_nao_alcancou_nao_ganha():
    _perfil(xp=100)
    _medalha(criterio={"tipo": "xp_acumulado", "alvo": 300})

    assert avaliar(ALUNO, SITE) == []
    assert Concessao.objects.count() == 0


def test_medalha_desligada_nao_cai():
    """A economia inteira nasce desligada, e ligar é decisão do mantenedor."""
    _perfil(xp=500)
    _medalha(ativa=False)

    assert avaliar(ALUNO, SITE) == []


def test_avaliar_duas_vezes_nao_concede_duas_vezes():
    _perfil(xp=500)
    _medalha()

    avaliar(ALUNO, SITE)
    segunda = avaliar(ALUNO, SITE)

    assert segunda == []
    assert Concessao.objects.count() == 1


# ------------------------------------------- 2. o que NÃO cai por conta


def test_marco_real_nunca_cai_por_conta():
    """Conceder um marco por cálculo seria a escola afirmar que alguém conseguiu
    um cliente sem ninguém ter olhado a prova."""
    _perfil(xp=500)
    _medalha(
        slug="primeiro-cliente",
        nome="Primeiro cliente",
        classe=ConquistaDefinicao.Classe.MARCO,
        familia=ConquistaDefinicao.Familia.CARREIRA,
        criterio={"tipo": "xp_acumulado", "alvo": 1},
    )

    assert avaliar(ALUNO, SITE) == []
    assert Concessao.objects.count() == 0


def test_medalha_manual_nao_cai_por_conta():
    """O Fundador não tem conta para bater: é a equipe que o concede."""
    _perfil(xp=500)
    _medalha(slug="fundador", criterio={"tipo": "manual"})

    assert avaliar(ALUNO, SITE) == []


def test_criterio_fora_do_vocabulario_nao_concede_e_nao_estoura():
    """O critério de morte nº 1 da lei, com lugar concreto onde acontece.

    A linha é gravada por baixo do `save()` (que a recusaria) para simular uma
    que tenha entrado antes daquela trava existir. Fail-closed é não conceder.
    """
    perfil = _perfil(xp=500)
    medalha = _medalha()
    ConquistaDefinicao.objects.filter(pk=medalha.pk).update(
        criterio={"tipo": "inventado_por_alguem", "alvo": 1}
    )
    medalha.refresh_from_db()

    assert cumpre(medalha, perfil.pessoa, SITE, perfil) is False
    assert avaliar(ALUNO, SITE) == []


# ------------------------------------------- 3. a cadeia, e o fim dela


def test_uma_medalha_pode_destravar_a_seguinte_e_o_laco_termina():
    """Ganhar a de ofício paga XP, o XP sobe o nível, e o nível alcança a outra.

    Sem o laço, a segunda medalha só cairia no próximo fato que mexesse no
    número — e o aluno veria uma chegar hoje e a outra semana que vem, sem
    entender por quê.
    """
    _perfil(xp=300)
    NivelDefinicao.objects.create(
        nivel=2, site_id=SITE, xp_necessario=350, titulo="Modelador", ativa=True
    )
    _medalha(
        slug="dos-trezentos", criterio={"tipo": "xp_acumulado", "alvo": 300}, pontos=100
    )
    _medalha(
        slug="do-nivel-dois",
        nome="Nível dois",
        criterio={"tipo": "nivel_alcancado", "alvo": 2},
    )

    novas = avaliar(ALUNO, SITE)

    assert sorted(c.conquista.slug for c in novas) == ["do-nivel-dois", "dos-trezentos"]
    assert PerfilJogador.objects.get().nivel == 2


def test_a_medalha_de_familia_conta_as_que_a_pessoa_ja_tem():
    """`conquistas_da_familia` é um dos três critérios com dado de verdade hoje."""
    _perfil(xp=500)
    _medalha(slug="primeira", criterio={"tipo": "xp_acumulado", "alvo": 100})
    _medalha(slug="segunda", criterio={"tipo": "xp_acumulado", "alvo": 200})
    _medalha(
        slug="colecionador",
        nome="Colecionador",
        criterio={"tipo": "conquistas_da_familia", "familia": "oficio", "alvo": 2},
    )

    novas = avaliar(ALUNO, SITE)

    assert "colecionador" in [c.conquista.slug for c in novas]


# ------------------------------------------- 4. o motor roda onde deve


def test_creditar_xp_por_evento_ja_concede_a_medalha():
    """O ponto de chamada é `recalcular`, por onde TODA mudança de número passa."""
    _pessoa()
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
    _medalha(criterio={"tipo": "xp_acumulado", "alvo": 300})

    aplicar(
        {
            "event": "sugestao.criada",
            "version": 1,
            "event_id": str(uuid.uuid4()),
            "occurred_at": timezone.now().isoformat(),
            "ator_id": ALUNO,
            "data": {"site_id": SITE},
        },
        SITE,
    )

    assert Concessao.objects.filter(conquista__slug="veterano").exists()
    # E a pessoa é avisada: a carta da medalha sai pela mesma porta de sempre.
    assuntos = [c.payload["assunto"] for c in OutboxEvent.objects.all()]
    assert "gamificacao.conquista-concedida" in assuntos


def test_consertar_um_perfil_nao_concede_medalha_nenhuma():
    """`celebrar=False` é o reparo de manutenção: ele não faz ninguém conquistar."""
    _perfil(xp=500)
    _medalha()

    recalcular(ALUNO, SITE, celebrar=False)

    assert Concessao.objects.count() == 0


# ------------------------------------------- 5. os limites, ditos em teste


def test_os_criterios_sem_fato_devolvem_zero_lendo_a_tabela_vazia():
    """Zero MEDIDO, não zero inventado.

    `forjas_seladas` lê a tabela `Forja`, que existe e que ninguém escreve ainda
    (degrau 14). O teste prova as duas metades: com a tabela vazia não concede, e
    com uma linha de verdade lá dentro concede. É o que garante que a medalha vai
    funcionar no dia em que a Forja nascer, sem ninguém precisar voltar aqui.
    """
    perfil = _perfil(xp=10)
    medalha = _medalha(slug="uma-forja", criterio={"tipo": "forjas_seladas", "alvo": 1})

    assert avaliar(ALUNO, SITE) == []

    Forja.objects.create(
        pessoa=perfil.pessoa,
        site_id=SITE,
        desafio_ref="peca-1",
        medidor=3,
        selada_em=timezone.now(),
    )

    assert [c.conquista.slug for c in avaliar(ALUNO, SITE)] == [medalha.slug]
