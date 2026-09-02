"""O comando que liga a escada de degraus, e o que ele se recusa a fazer.

Ele existe porque `/admin/economia/` tem interruptor para regras e conquistas e
NENHUM para degraus — decisão do mantenedor em 01/09/2026: ligar agora pelo
pipeline, e ganhar o botão na tela em seguida.

O QUE ESTE ARQUIVO PROTEGE
--------------------------
1. **Ligar degrau não liga economia nenhuma.** Degrau é a régua com que o XP é
   lido; regra é quanto a escola paga. Um comando que ligasse as duas seria uma
   mudança de economia que ninguém decidiu (lei §10.5).
2. **Escola sem degrau não vira "OK".** Ligar zero linhas e sair com sucesso é
   falso-verde, a doença nº 1 do catálogo desta casa.
3. **Um degrau só também não vira "OK".** Com um degrau não há para onde subir e
   a tela diz "o degrau seguinte ainda não abriu" (`armadilhas/271`): quem rodou
   isto acharia que falhou.
4. **A linha de conclusão só sai no caminho feliz** — é ela que o pipeline
   procura, e ela nunca pode aparecer numa saída em que algo deu errado.
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.gamificacao.models import NivelDefinicao, RegraDePontuacao

pytestmark = pytest.mark.django_db

SITE = "escola-de-teste"
OUTRA = "escola-vizinha"
CONCLUSAO = "ESCADA DE DEGRAUS LIGADA OK"


def _degraus(site: str = SITE, quantos: int = 3, ativa: bool = False) -> None:
    for numero in range(1, quantos + 1):
        NivelDefinicao.objects.create(
            nivel=numero,
            site_id=site,
            xp_necessario=(numero - 1) * 50,
            titulo=f"Degrau {numero}",
            ativa=ativa,
        )


def _rodar(site: str = SITE) -> str:
    saida = StringIO()
    call_command("ligar_degraus", site=site, stdout=saida)
    return saida.getvalue()


def test_liga_todos_os_degraus_do_site():
    _degraus()

    saida = _rodar()

    assert NivelDefinicao.objects.filter(site_id=SITE, ativa=False).count() == 0
    assert NivelDefinicao.objects.filter(site_id=SITE, ativa=True).count() == 3
    assert CONCLUSAO in saida


def test_nao_liga_regra_de_pontuacao_nenhuma():
    """**O guarda que justifica este arquivo existir.**

    Degrau não paga nada; regra paga. Se este teste ficar verde com uma regra
    ligada, o comando virou uma mudança de economia sem decisão de ninguém.
    """
    _degraus()
    RegraDePontuacao.objects.create(
        site_id=SITE,
        slug="quiz-aprovado",
        evento_gatilho="quiz.completado.v1",
        beneficiario="ator",
        pontos=30,
        ativa=False,
    )

    _rodar()

    assert RegraDePontuacao.objects.filter(site_id=SITE, ativa=True).count() == 0


def test_nao_encosta_na_escada_de_outra_escola():
    """Lei 9: um deploy, N domínios. Ligar a escada de um site é ligar UM site."""
    _degraus()
    _degraus(site=OUTRA)

    _rodar()

    assert NivelDefinicao.objects.filter(site_id=OUTRA, ativa=True).count() == 0


def test_rodar_duas_vezes_nao_muda_nada_na_segunda():
    _degraus()
    _rodar()

    saida = _rodar()

    assert "já estavam ligados ............ 3" in saida
    assert "ligados agora ................. 0" in saida
    assert CONCLUSAO in saida


def test_sem_degrau_nenhum_para_por_seguranca_e_nao_diz_ok():
    with pytest.raises(CommandError) as recusa:
        _rodar()

    assert "PAROU POR SEGURANÇA" in str(recusa.value)
    assert "semear_economia" in str(recusa.value), "não ensinou o caminho"


def test_com_um_degrau_so_para_por_seguranca():
    """Um degrau ligado não é escada: a tela do aluno diz que o seguinte ainda
    não abriu, e quem rodou o comando acharia que ele falhou."""
    _degraus(quantos=1)

    with pytest.raises(CommandError) as recusa:
        _rodar()

    assert "PAROU POR SEGURANÇA" in str(recusa.value)
    assert NivelDefinicao.objects.filter(site_id=SITE, ativa=True).count() == 0


def test_a_recusa_nunca_carrega_a_linha_de_conclusao():
    """É esta linha que o pipeline procura para declarar sucesso. Se ela vazar
    para um caminho de erro, o falso-verde volta pela porta da frente."""
    saida = StringIO()

    with pytest.raises(CommandError):
        call_command("ligar_degraus", site=SITE, stdout=saida)

    assert CONCLUSAO not in saida.getvalue()
