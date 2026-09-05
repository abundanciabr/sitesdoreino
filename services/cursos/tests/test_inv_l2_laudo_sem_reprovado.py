"""Teste-guarda [INV-CUR-L2]: o estado "reprovado" não existe: nem em `Envio`,
nem em `Laudo`, nem em texto de tela.

`tests/test_sem_reprovado.py` já varre `models.py` e as migrações da célula
inteira (e por isso cobre `Laudo.Decisao` automaticamente, sem precisar de
código novo lá). Este arquivo cobre o que aquele NÃO lê: o SERVIÇO
(`apps/cursos/laudo.py`) e as TELAS do plantão e do laudo — "nem em texto de
tela" é metade da lei, e sem isso um `{% comment %}` desavisado poderia
escrever a palavra proibida na tela sem nenhum guarda notar.

Provado por mutação em 05/09/2026: acrescentar `"reprovado"` a
`Laudo.Decisao.choices` (sem tocar `Laudo.Decisao.values` no serviço) deixa 2
vermelhos (o guarda do vocabulário aqui e o de `test_sem_reprovado.py`);
acrescentar a palavra a um template do plantão deixa 1 vermelho aqui.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apps.cursos import laudo as parecer
from apps.cursos.models import Laudo
from tests.conftest import forcas_validas, mudanca_valida, notas_validas

pytestmark = pytest.mark.django_db

APP = Path(__file__).resolve().parent.parent / "apps"
A_PALAVRA = "reprovad"


def test_a_palavra_nao_aparece_no_servico_do_laudo():
    fonte = (APP / "cursos" / "laudo.py").read_text(encoding="utf-8")
    assert A_PALAVRA not in fonte.lower()


def test_a_palavra_nao_aparece_nas_telas_do_plantao_nem_no_laudo():
    templates = (APP / "core" / "templates" / "cursos").glob("*.html")
    com_a_palavra = [
        t.name for t in templates if A_PALAVRA in t.read_text(encoding="utf-8").lower()
    ]
    assert com_a_palavra == [], f"a palavra proibida está em {com_a_palavra}"


def test_laudo_decisao_e_exatamente_as_tres_da_lei():
    assert Laudo.Decisao.values == ["aberto", "aberto_com_ajuste", "devolvido"]


def test_o_servico_recusa_reprovado_explicitamente(envio_na_fila, professora):
    with pytest.raises(parecer.LaudoRecusado, match="quarta decisão"):
        parecer.emitir(
            envio_na_fila,
            avaliador=professora,
            papel=Laudo.Papel.PROFESSOR,
            notas=notas_validas(),
            forcas=forcas_validas(),
            mudanca=mudanca_valida(envio_na_fila.aula),
            decisao="reprovado",
            sabe_o_que_fazer_amanha=True,
        )
    assert Laudo.objects.count() == 0
