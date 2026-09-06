"""O Extrator construído e o Gerador dissolvido chegam à página, no banco.

Guarda de `0016_o_extrator_existe_e_o_gerador_foi_dissolvido.py`.

**Por que este arquivo fabrica o estado de produção.** No banco de teste a
`0003` semeia a pasta inteira com o arquivo de HOJE, já corrigido, e a `0016`
não teria o que trocar: o teste ficaria verde sem exercitar uma linha dela. Em
produção o banco tem a versão que a `0014` instalou, que ainda afirma que o
Extrator não foi construído. Cada teste abaixo reconstrói esse estado antes de
medir.

**A metade que mais importa.** A `0016` troca texto que o mantenedor pode ter
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

_extrator = importlib.import_module(
    "apps.core.migrations.0016_o_extrator_existe_e_o_gerador_foi_dissolvido"
)

NOME = "como-criar-os-agentes-de-ia"
TITULO = "Os documentos do Meshcraft, lidos contra o que existe"
CORPO_DE_ONTEM = (
    "# Os documentos do Meshcraft, lidos contra o que existe\n\n"
    "O Extrator: registrado, não construído. O Gerador de derivados: não construído."
)


class _AppsFalso:
    @staticmethod
    def get_model(app_label, model_name):
        assert (app_label, model_name) == ("core", "Documento")
        return Documento


def _rodar():
    _extrator.o_extrator_existe_e_o_gerador_foi_dissolvido(_AppsFalso, None)


@pytest.fixture
def banco_de_ontem(db, monkeypatch):
    """O banco em que a `0014` deixou a versão que envelheceu no mesmo dia.

    A impressão digital que a `0016` procura é a daquele corpo, e não a deste
    texto curto: o teste aponta a constante da migração para o que ele planta,
    que é o mesmo gesto com o mesmo significado.
    """
    Documento.objects.update_or_create(
        nome=NOME,
        defaults={"titulo": TITULO, "corpo": CORPO_DE_ONTEM, "publico": False},
    )
    monkeypatch.setattr(
        _extrator,
        "CORPO_SEMEADO",
        hashlib.sha256(CORPO_DE_ONTEM.encode("utf-8")).hexdigest(),
    )


def test_o_extrator_aparece_construido_e_sem_ia(banco_de_ontem):
    """O agente 1 saiu de "registrado" para construído em duas telas."""
    _rodar()

    corpo = Documento.objects.get(nome=NOME).corpo
    assert "Construído em duas telas, e nenhuma delas usa IA" in corpo
    assert "16 de 16 peças" in corpo
    assert "Registrado, não construído" not in corpo


def test_o_gerador_de_derivados_aparece_dissolvido(banco_de_ontem):
    """O agente 5 saiu da lista dos que faltam, com a razão escrita."""
    _rodar()

    corpo = Documento.objects.get(nome=NOME).corpo
    assert "Por que o Gerador de derivados foi dissolvido" in corpo
    assert "os textos já estão escritos" in corpo


def test_o_placar_de_agentes_de_ia_diminuiu(banco_de_ontem):
    """A frase que vale a atualização inteira precisa chegar à página."""
    _rodar()

    corpo = Documento.objects.get(nome=NOME).corpo
    assert "diminuiu em vez de crescer" in corpo
    assert "só dois são de IA de verdade" in corpo


def test_a_tabela_como_conferir_ganha_a_afirmacao_nova(banco_de_ontem):
    """Afirmação nova sem linha de como medir é afirmação sem fiscal."""
    _rodar()

    corpo = Documento.objects.get(nome=NOME).corpo
    assert "| O Extrator existe e não usa IA |" in corpo
    assert "`services/admin/apps/core/capitulo.py`" in corpo


def test_o_que_ja_tem_dono_sai_da_lista_do_que_falta(banco_de_ontem):
    """As duas linhas resolvidas hoje somem de "O que ainda não tem dono"."""
    _rodar()

    corpo = Documento.objects.get(nome=NOME).corpo
    assert "**A tela de colar o sumário** (o Extrator)" not in corpo
    assert "- **O Gerador de derivados** (o Cartão de 1 página e o quiz)." not in corpo


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
    assert "Construído em duas telas" not in documento.corpo


def test_sem_a_pagina_no_banco_nao_estoura(db):
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


def test_a_impressao_digital_e_a_do_corpo_que_a_0014_instalou():
    """A constante precisa ser a do texto REAL que está no banco de produção.

    Se alguém editar o arquivo sem recalcular a constante, a `0016` deixa de
    reconhecer o corpo instalado e a página nunca se atualiza, em silêncio.
    Este teste não consegue medir o corpo de ontem (ele não existe mais no
    repositório), mas mede o formato: 64 caracteres hexadecimais.
    """
    assert len(_extrator.CORPO_SEMEADO) == 64
    assert all(c in "0123456789abcdef" for c in _extrator.CORPO_SEMEADO)
