"""O terceiro interruptor: os degraus da escada.

POR QUE ELE EXISTE
------------------
Em 01/09/2026 o mantenedor abriu `/conquistas` e leu três frases que se
contradiziam. O defeito da tela foi corrigido (`armadilhas/271`) e o que sobrou
foi a verdade: a escola nunca ligou degrau nenhum. A tela dele tinha botão para
as regras e para as conquistas; para a escada, nada.

O QUE ESTE ARQUIVO PROTEGE
--------------------------
1. **Ligar um degrau não paga nada.** Degrau é a régua com que o XP já existente
   é lido, e é por isso que aqui não há `vigente_desde` nem crédito nenhum. Se
   um dia alguém fizer este gesto creditar, o guarda do XP fica vermelho.
2. **Ligar um degrau não recalcula perfil.** `PerfilJogador.nivel` é
   desnormalizado e quem o reescreve é o motor. Varrer a escola num clique
   mandaria uma chuva de cartas "você subiu de nível" para quem não fez nada.
3. **Os dois impedimentos falam antes do clique**, que é a única hora em que
   eles servem para alguma coisa.
4. **Chamada que não muda nada não gasta versão** — a mesma regra dos outros
   dois interruptores.
"""

from __future__ import annotations

import pytest
from django.utils import timezone

from apps.gamificacao.interruptores import (
    DegrauDesconhecido,
    impedimentos_do_degrau,
    listar_degraus,
    mudar_degrau,
)
from apps.gamificacao.models import (
    NivelDefinicao,
    PerfilJogador,
    Pessoa,
    RegraDePontuacao,
)

pytestmark = pytest.mark.django_db

SITE = "escola-de-teste"
OUTRA = "escola-vizinha"


def _degrau(nivel: int, xp: int, titulo: str, *, site: str = SITE, ativa: bool = False):
    return NivelDefinicao.objects.create(
        nivel=nivel, site_id=site, xp_necessario=xp, titulo=titulo, ativa=ativa
    )


def _regra_ligada(site: str = SITE):
    return RegraDePontuacao.objects.create(
        site_id=site,
        slug="quiz-aprovado",
        evento_gatilho="quiz.completado.v1",
        beneficiario="ator",
        pontos=30,
        ativa=True,
        # O banco EXIGE a data numa regra ligada (`regra_ligada_tem_data_de_
        # vigencia`): é o mecanismo do "nunca retroativo", e ele não abre
        # exceção nem para cenário de teste.
        vigente_desde=timezone.now(),
    )


# --------------------------------------------------------------- ligar e listar


def test_listar_devolve_todos_os_degraus_do_primeiro_ao_ultimo():
    _degrau(2, 50, "Aprendiz de Ateliê")
    _degrau(1, 0, "Aprendiz", ativa=True)
    _degrau(3, 150, "Modelador")

    escada = listar_degraus(SITE)

    assert [d.nivel for d in escada] == [1, 2, 3], "a tela desenharia fora de ordem"
    assert [d.ativa for d in escada] == [True, False, False]


def test_ligar_marca_ativa_e_sobe_a_versao():
    _degrau(1, 0, "Aprendiz")

    degrau = mudar_degrau(site_id=SITE, nivel=1, ativa=True)

    assert degrau.ativa is True
    assert degrau.versao == 2


def test_ligar_de_novo_nao_gasta_versao():
    """Dois cliques no mesmo botão não inflam o histórico com mudanças que
    ninguém fez. Mesma regra dos outros dois interruptores."""
    _degrau(1, 0, "Aprendiz", ativa=True)

    degrau = mudar_degrau(site_id=SITE, nivel=1, ativa=True)

    assert degrau.versao == 1


def test_desligar_volta_atras_e_sobe_a_versao():
    _degrau(1, 0, "Aprendiz", ativa=True)

    degrau = mudar_degrau(site_id=SITE, nivel=1, ativa=False)

    assert degrau.ativa is False
    assert degrau.versao == 2


def test_degrau_de_outra_escola_nao_e_encontrado():
    """Lei 9: um deploy, N domínios. O número do degrau só existe dentro do
    site, e é o par (site, nivel) que o banco torna único."""
    _degrau(1, 0, "Aprendiz", site=OUTRA)

    with pytest.raises(DegrauDesconhecido):
        mudar_degrau(site_id=SITE, nivel=1, ativa=True)

    assert NivelDefinicao.objects.get(site_id=OUTRA, nivel=1).ativa is False


def test_numero_de_degrau_que_nao_existe_recusa():
    """404 na porta. Inventar em silêncio qual degrau ele quis ligar seria pior
    que recusar."""
    _degrau(1, 0, "Aprendiz")

    with pytest.raises(DegrauDesconhecido):
        mudar_degrau(site_id=SITE, nivel=99, ativa=True)


# --------------------------------------- o que ligar um degrau NUNCA pode fazer


def test_ligar_um_degrau_nao_credita_xp_nenhum():
    """**O guarda que justifica este arquivo existir.**

    Degrau é régua, não pagamento. Se este teste ficar vermelho, o gesto virou
    uma mudança de economia que ninguém decidiu, e o "nunca retroativo" das
    regras de pontuação passou a ter um buraco do tamanho de uma escada.
    """
    pessoa = Pessoa.objects.create(id_da_plataforma="p1", email="a@b.invalid")
    perfil = PerfilJogador.objects.create(pessoa=pessoa, site_id=SITE, xp_total=60)
    _degrau(1, 0, "Aprendiz")
    _degrau(2, 50, "Aprendiz de Ateliê")

    mudar_degrau(site_id=SITE, nivel=1, ativa=True)
    mudar_degrau(site_id=SITE, nivel=2, ativa=True)

    perfil.refresh_from_db()
    assert perfil.xp_total == 60, "ligar degrau creditou XP"


def test_ligar_um_degrau_nao_reescreve_o_nivel_gravado_do_perfil():
    """A ausência é DECISÃO, e está escrita no contrato.

    Quem reescreve `PerfilJogador.nivel` é o motor, na próxima vez que o XP
    daquela pessoa mexer; o acerto em massa é `reconciliar_perfis`. Recalcular
    aqui mandaria uma chuva de cartas "você subiu de nível" para gente que não
    fez nada hoje.
    """
    pessoa = Pessoa.objects.create(id_da_plataforma="p1", email="a@b.invalid")
    perfil = PerfilJogador.objects.create(
        pessoa=pessoa, site_id=SITE, xp_total=60, nivel=1
    )
    _degrau(1, 0, "Aprendiz")
    _degrau(2, 50, "Aprendiz de Ateliê")

    mudar_degrau(site_id=SITE, nivel=2, ativa=True)

    perfil.refresh_from_db()
    assert perfil.nivel == 1


# ------------------------------------------------ os avisos, ANTES do clique


def test_avisa_quando_ligar_este_degrau_nao_forma_escada():
    """Um degrau sozinho não é escada: a tela do aluno diz que o seguinte ainda
    não abriu (`armadilhas/271`). Ele precisa saber disso antes de clicar."""
    primeiro = _degrau(1, 0, "Aprendiz")
    _degrau(2, 50, "Aprendiz de Ateliê")

    avisos = impedimentos_do_degrau(primeiro, ativos_no_site=0)

    assert "escada-de-um-degrau-so" in avisos


def test_com_dois_degraus_ligados_o_aviso_da_escada_some():
    segundo = _degrau(2, 50, "Aprendiz de Ateliê")
    _degrau(1, 0, "Aprendiz", ativa=True)
    _regra_ligada()

    avisos = impedimentos_do_degrau(segundo, ativos_no_site=1)

    assert avisos == []


def test_avisa_quando_nenhuma_regra_paga_pontos():
    """Escada de pé com a economia desligada: o aluno vê a barra, e ela nunca
    anda. É o estado exato da escola em 02/09/2026."""
    degrau = _degrau(1, 0, "Aprendiz", ativa=True)
    _degrau(2, 50, "Aprendiz de Ateliê", ativa=True)

    avisos = impedimentos_do_degrau(degrau, ativos_no_site=2)

    assert avisos == ["sem-regra-que-paga"]


def test_regra_ligada_de_outra_escola_nao_cala_o_aviso():
    """Cenário com dente: uma regra ligada no site vizinho não paga nada aqui."""
    degrau = _degrau(1, 0, "Aprendiz", ativa=True)
    _degrau(2, 50, "Aprendiz de Ateliê", ativa=True)
    _regra_ligada(site=OUTRA)

    avisos = impedimentos_do_degrau(degrau, ativos_no_site=2)

    assert "sem-regra-que-paga" in avisos
