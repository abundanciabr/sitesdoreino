"""A migração que corrige o reembolso no texto JÁ GRAVADO no banco.

Guarda de `apps/core/migrations/0005_o_reembolso_no_texto_que_ja_esta_no_banco.py`.

**Por que este arquivo precisa existir, e por que ele constrói o documento à
mão:** a migração `0003` semeia os documentos a partir dos `.md` do repositório,
e no banco de teste eles nascem com o texto **já corrigido** (o PR #764 arrumou
os arquivos). Rodar a suíte não exercitaria uma única linha da `0005` — ela não
encontraria nada para trocar, e ficaria verde sem nunca ter feito nada.

Foi assim que o defeito passou: o `deploy-celula` do #764 ficou **verde**, a
suíte ficou **verde**, e `curl` na página pública devolvia a frase errada. Um
teste que só olha o caminho feliz do banco novo é cego para o banco antigo, que
é o único que existe em produção.

Por isso os testes abaixo **fabricam o estado de produção**: um documento com o
texto de ontem, e então a função da migração é chamada de verdade.
"""

import importlib

import pytest

from apps.core.models import Documento

_migracao = importlib.import_module(
    "apps.core.migrations.0005_o_reembolso_no_texto_que_ja_esta_no_banco"
)


class _AppsFalso:
    """O `apps` que a migração recebe do Django, com o modelo de hoje.

    A migração pede `apps.get_model("core", "Documento")` porque é assim que uma
    migração enxerga a versão HISTÓRICA da tabela. Aqui entregamos a atual, que
    é o que este teste quer exercitar.
    """

    @staticmethod
    def get_model(app_label, model_name):
        assert (app_label, model_name) == ("core", "Documento")
        return Documento


ANTES_DA_ENTRADA = (
    "- **Reembolsado**: você devolveu o dinheiro e **continua entrando**. Foi uma\n"
    "  decisão da escola: quem já foi aluno mantém a voz na Caixa de Sugestões.\n"
    "- **Pausado**: o acesso está desligado por enquanto, e **volta sozinho** quando\n"
    "  a equipe religar. Você não precisa fazer nada, e não há o que pedir.\n"
    "- **Ex-aluno**: o acesso acabou. Sua ficha continua guardada, e **se você quiser\n"
    "  voltar, é só pedir de novo** (o mesmo formulário do começo)."
)


def _correr():
    _migracao.corrigir_o_reembolso(_AppsFalso, None)


@pytest.fixture
def documento_de_ontem(db):
    """O estado REAL de produção em 31/08/2026, reconstruído."""
    Documento.objects.filter(nome="como-funciona-a-entrada").delete()
    return Documento.objects.create(
        nome="como-funciona-a-entrada",
        titulo="Como funciona a entrada",
        publico=True,
        ordem=1,
        corpo="## Depois de ser aluno\n\n" + ANTES_DA_ENTRADA + "\n\n## O fim\n",
    )


def test_a_frase_errada_some_do_banco(documento_de_ontem):
    _correr()

    corpo = Documento.objects.get(pk=documento_de_ontem.pk).corpo
    assert "continua entrando" not in corpo
    assert "Você não entra mais" in corpo


def test_o_resto_do_documento_fica_intacto(documento_de_ontem):
    """A troca é do TRECHO, nunca do corpo inteiro.

    Trocar o corpo todo apagaria qualquer edição que o mantenedor tenha feito em
    outro ponto do mesmo documento pela tela do editor — e ele edita por lá desde
    31/08/2026.
    """
    _correr()

    corpo = Documento.objects.get(pk=documento_de_ontem.pk).corpo
    assert corpo.startswith("## Depois de ser aluno\n\n")
    assert corpo.endswith("\n\n## O fim\n")
    # E os vizinhos do parágrafo trocado continuam lá, uma vez cada.
    assert corpo.count("**Pausado**") == 1
    assert corpo.count("**Ex-aluno**") == 1


def test_o_reembolsado_passa_a_ser_o_ULTIMO_da_lista(documento_de_ontem):
    """A ordem é parte da correção, não estilo.

    A lista vai do que ainda dá acesso para o que não dá. Com o reembolso
    passando a tirar o acesso, deixá-lo logo abaixo de "Aluno" contaria a
    história na ordem errada para quem lê de cima para baixo.
    """
    _correr()

    corpo = Documento.objects.get(pk=documento_de_ontem.pk).corpo
    assert corpo.index("**Pausado**") < corpo.index("**Reembolsado**")
    assert corpo.index("**Ex-aluno**") < corpo.index("**Reembolsado**")


def test_um_documento_ja_reescrito_pelo_mantenedor_nao_e_tocado(db):
    """A propriedade que torna esta migração segura de rodar.

    O pior desfecho de uma migração de correção de texto é sobrescrever texto
    melhor. Ela casa o trecho ANTIGO inteiro: se ele não está lá, nada acontece.
    """
    Documento.objects.filter(nome="como-funciona-a-entrada").delete()
    dele = Documento.objects.create(
        nome="como-funciona-a-entrada",
        titulo="Como funciona a entrada",
        publico=True,
        ordem=1,
        corpo="Quem pede reembolso sai da escola. Escrevi isso do meu jeito.",
    )

    _correr()

    assert Documento.objects.get(pk=dele.pk).corpo == dele.corpo


def test_rodar_duas_vezes_nao_duplica_nada(documento_de_ontem):
    """Migração de dados é rodada de novo em toda restauração de banco."""
    _correr()
    primeira = Documento.objects.get(pk=documento_de_ontem.pk).corpo
    _correr()

    assert Documento.objects.get(pk=documento_de_ontem.pk).corpo == primeira


def test_banco_sem_o_documento_nao_estoura(db):
    """Banco novo (o do próprio CI) não tem o texto de ontem, e isso não é erro."""
    Documento.objects.filter(
        nome__in=["como-funciona-a-entrada", "jornada-do-aluno"]
    ).delete()

    _correr()  # não levanta
