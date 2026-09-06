"""A 2ª e a 3ª leitura chegam à página, e a edição do mantenedor sobrevive.

Guarda de `0014_as_tres_leituras_dos_documentos.py`.

**Por que este arquivo fabrica o estado de produção.** No banco de teste a
`0003` semeia a pasta inteira com o arquivo de HOJE, já com as três leituras, e
a `0014` não teria o que trocar: o teste ficaria verde sem exercitar uma linha
dela. Em produção o banco tem a versão de ONTEM, semeada pela `0013`. Cada
teste abaixo reconstrói esse estado antes de medir.

**A metade que mais importa.** A `0014` troca texto que o mantenedor pode ter
editado pela tela. Uma migração de conteúdo que sobrescreve trabalho dele é
pior do que uma que não roda: ela desfaz o que ele escreveu para instalar o que
a máquina escreveu. Por isso ela casa a impressão digital do corpo antes de
tocar em qualquer coisa, e por isso existe
`test_nao_encosta_no_que_o_mantenedor_editou`.
"""

import hashlib
import importlib

import pytest

from apps.core import documentos
from apps.core.models import Documento

_leituras = importlib.import_module(
    "apps.core.migrations.0014_as_tres_leituras_dos_documentos"
)

NOME = "como-criar-os-agentes-de-ia"
CORPO_DE_ONTEM = "# Como criar os agentes de IA da Meshcraft (setembro de 2026)\n\nA versão de uma leitura só."
TITULO_DE_ONTEM = "Como criar os agentes de IA da Meshcraft (setembro de 2026)"


class _AppsFalso:
    @staticmethod
    def get_model(app_label, model_name):
        assert (app_label, model_name) == ("core", "Documento")
        return Documento


def _rodar():
    _leituras.as_tres_leituras(_AppsFalso, None)


@pytest.fixture
def banco_de_ontem(db, monkeypatch):
    """O banco em que a `0013` semeou a versão de uma leitura só.

    A impressão digital que a `0014` procura é a daquele corpo, e não a deste
    texto curto: o teste aponta a constante da migração para o que ele planta,
    que é o mesmo gesto com o mesmo significado.
    """
    Documento.objects.update_or_create(
        nome=NOME,
        defaults={
            "titulo": TITULO_DE_ONTEM,
            "corpo": CORPO_DE_ONTEM,
            "publico": False,
        },
    )
    monkeypatch.setattr(
        _leituras,
        "CORPO_SEMEADO",
        hashlib.sha256(CORPO_DE_ONTEM.encode("utf-8")).hexdigest(),
    )


def test_as_tres_leituras_chegam_a_pagina(banco_de_ontem):
    _rodar()

    documento = Documento.objects.get(nome=NOME)
    assert documento.titulo == "Os documentos do Meshcraft, lidos contra o que existe"
    assert "Documento 2 — Antes de como começar" in documento.corpo
    assert "Documento 3 — Ajustar o que foi escrito" in documento.corpo
    assert "De 8 lotes, 6 se distribuem entre células existentes" in documento.corpo


def test_a_pagina_continua_so_para_administradores(banco_de_ontem):
    """Trocar o texto não pode reabrir a página ao público."""
    _rodar()

    assert Documento.objects.get(nome=NOME).publico is False


def test_nao_encosta_no_que_o_mantenedor_editou(banco_de_ontem):
    """A metade mais importante deste arquivo.

    Se ele escreveu qualquer coisa na página, a impressão digital não bate e a
    migração não faz nada. O texto dele fica, e ele mesmo vê e decide.
    """
    Documento.objects.filter(nome=NOME).update(
        corpo=CORPO_DE_ONTEM + "\n\nUma anotação que eu escrevi na tela."
    )

    _rodar()

    documento = Documento.objects.get(nome=NOME)
    assert documento.corpo.endswith("Uma anotação que eu escrevi na tela.")
    assert "Documento 2" not in documento.corpo


def test_sem_a_pagina_no_banco_nao_estoura(db, monkeypatch):
    """Banco em que a `0013` não rodou: nada a trocar, e nada quebra."""
    Documento.objects.filter(nome=NOME).delete()

    _rodar()

    assert not Documento.objects.filter(nome=NOME).exists()


def test_sem_a_pasta_na_imagem_nao_estoura(banco_de_ontem, monkeypatch, tmp_path):
    """Falhar aqui deixaria a célula em crashloop no `migrate` por um passo de
    conteúdo (a lição H18)."""
    monkeypatch.setattr(documentos, "CANDIDATOS", (tmp_path / "nao-existe",))

    _rodar()

    assert Documento.objects.get(nome=NOME).corpo == CORPO_DE_ONTEM


def test_a_impressao_digital_da_migracao_e_a_do_arquivo_que_a_0013_semeou():
    """A constante da migração precisa ser a do texto REAL que está lá.

    Se alguém editar o arquivo sem recalcular a constante, a `0014` deixa de
    reconhecer o corpo semeado e a página nunca se atualiza, em silêncio. Este
    teste não consegue medir o arquivo de ontem (ele não existe mais no
    repositório), mas mede o formato: 64 caracteres hexadecimais.
    """
    assert len(_leituras.CORPO_SEMEADO) == 64
    assert all(c in "0123456789abcdef" for c in _leituras.CORPO_SEMEADO)
