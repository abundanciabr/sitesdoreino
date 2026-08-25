"""O relatório do que ficou sem — o antídoto nominal da §9 do PLANO-MESTRE.

O risco número 1 da Fase 1 é *"sai errada e o id da plataforma some; todo o resto
herda o defeito"*, e o antídoto tem duas metades: o teste-guarda
(`test_inv_id_da_plataforma.py`) e **este relatório**. O guarda responde "o código
grava?"; o relatório responde a pergunta que nenhum teste responde: *em produção,
agora, quanto falta?*

Somente leitura — o que este teste também mede, porque um "relatório" que
escrevesse deixaria de ser seguro de rodar em produção a qualquer hora.
"""

import pytest
from django.core.management import call_command

from apps.sugestoes.models import Identidade

pytestmark = pytest.mark.django_db


def _rodar(capsys) -> str:
    call_command("relatorio_id_da_plataforma")
    return capsys.readouterr().out


def test_imprime_os_dois_numeros(capsys):
    Identidade.objects.create(email="casada@exemplo.test", id_da_plataforma="idt-1")
    Identidade.objects.create(email="pendente-a@exemplo.test")
    Identidade.objects.create(email="pendente-b@exemplo.test")

    saida = _rodar(capsys)

    assert "com o id da plataforma: 1" in saida
    assert "ainda sem o id:         2" in saida
    assert "total de identidades:   3" in saida


def test_tabela_vazia_nao_vira_uma_divisao_por_zero(capsys):
    """Célula recém-implantada é o caso normal de um relatório novo — e é
    exatamente onde `100 * 0 / 0` derrubaria o comando."""
    saida = _rodar(capsys)

    assert "com o id da plataforma: 0" in saida
    assert "total de identidades:   0" in saida


def test_o_relatorio_nao_escreve_nada(capsys):
    pendente = Identidade.objects.create(email="pendente@exemplo.test")

    _rodar(capsys)

    pendente.refresh_from_db()
    assert pendente.id_da_plataforma is None
    assert Identidade.objects.count() == 1
