"""O estado "reprovado" não existe: nem em `Envio`, nem em vocabulário nenhum
desta célula, nem nas migrações.

Lei: `PLANO-CELULA-CURSOS.md` §4 ("Não existe o valor 'reprovado', e um teste
procura a palavra no schema inteiro"), §9 ([INV-CUR-L2], cuja metade do
`Laudo` e do texto de tela nasce no degrau 2.2) e o critério de morte da lei
§11. A escola devolve com data de retorno; nunca reprova.

Os dentes: (1) a palavra não aparece no `models.py` nem em migração nenhuma da
célula, e o guarda prova que leu os arquivos certos; (2) nenhum campo com
`choices` de nenhum modelo da célula tem o valor ou o rótulo; (3) o vocabulário
do `Envio` é exatamente os cinco da lei.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from django.apps import apps

from apps.cursos.models import Envio

pytestmark = pytest.mark.django_db

APP = Path(__file__).resolve().parent.parent / "apps" / "cursos"
A_PALAVRA = "reprovad"


def test_a_palavra_nao_aparece_no_models_nem_nas_migracoes():
    arquivos = [APP / "models.py", *sorted((APP / "migrations").glob("0*.py"))]
    assert len(arquivos) >= 4, "esperava models.py e ao menos três migrações"
    textos = {arquivo.name: arquivo.read_text(encoding="utf-8") for arquivo in arquivos}
    assert "class Envio" in textos["models.py"]
    assert any(
        "Envio" in texto for nome, texto in textos.items() if nome != "models.py"
    )
    com_a_palavra = [
        nome for nome, texto in textos.items() if A_PALAVRA in texto.lower()
    ]
    assert com_a_palavra == [], f"a palavra proibida está em {com_a_palavra}"


def test_nenhum_vocabulario_da_celula_tem_o_valor_nem_o_rotulo():
    for modelo in apps.get_app_config("cursos").get_models():
        for campo in modelo._meta.fields:
            for valor, rotulo in campo.choices or ():
                assert (
                    A_PALAVRA not in str(valor).lower()
                ), f"{modelo.__name__}.{campo.name}"
                assert (
                    A_PALAVRA not in str(rotulo).lower()
                ), f"{modelo.__name__}.{campo.name}"


def test_o_vocabulario_do_envio_e_exatamente_os_cinco_da_lei():
    assert Envio.Estado.values == [
        "recebido",
        "em_revisao",
        "aberto",
        "aberto_com_ajuste",
        "devolvido",
    ]
