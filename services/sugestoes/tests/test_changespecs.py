"""Registro de decisão pela API autenticada e leitura do histórico imutável."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.sugestoes.models import ChangeSpecAprovado

pytestmark = pytest.mark.django_db

PREFIXO = "/forms/sugestoes"

VALIDO = {
    "change_id": "CS-SUGESTOES-0007",
    "documento": "docs/changespecs/CS-SUGESTOES-0007.md",
    "aprovado_por": "Davi (mantenedor)",
    "aprovado_em": "2026-08-25",
}


def _registrar(pessoa, sugestao, **mudancas):
    """Registra pela mesma API usada pela gestão."""
    return pessoa.gestao.assinar(pessoa, sugestao, **{**VALIDO, **mudancas})


# ---------------------------------------------------------------------------
# A lista antiga não condiciona a escrita autenticada
# ---------------------------------------------------------------------------


def test_sem_lista_de_aprovadores_registra_com_autoria(equipe, sugestao):
    escrita = equipe.gestao.assinar(equipe, sugestao)

    assert escrita.status_code == 200, escrita.content
    assert ChangeSpecAprovado.objects.get().registrado_por_id == equipe.identidade.id


def test_a_lista_vazia_nao_impede_registro(equipe, sugestao, monkeypatch):
    for valor in ("", "   ", ",", " , ,"):
        monkeypatch.setenv("SUGESTOES_APROVADORES", valor)
        assert equipe.gestao.assinar(equipe, sugestao).status_code == 200, valor

    assert ChangeSpecAprovado.objects.count() == 4


def test_staff_fora_da_lista_registra_pela_api(equipe, sugestao, lista_de_aprovadores):
    lista_de_aprovadores("outra.pessoa@meshcraft.test")

    resposta = equipe.gestao.assinar(equipe, sugestao)

    assert resposta.status_code == 200
    assert ChangeSpecAprovado.objects.get().registrado_por_id == equipe.identidade.id


def test_o_aluno_nem_chega_ao_segundo_portao(dentro, sugestao):
    """Quem não tem crachá recebe a recusa do crachá, que é a verdade dele.

    Medido no endereço aposentado, que continua atrás do mesmo `exige_staff`.
    """
    recusa = dentro.client.get(reverse("changespecs", args=[sugestao.id]))

    assert recusa.status_code == 403
    assert b"lista de quem modera" in recusa.content


def test_o_anonimo_vai_para_a_porta(client, sugestao):
    """Como em toda a célula: 302, nunca 403 (`apps/core/participacao.py`)."""
    resposta = client.get(reverse("changespecs", args=[sugestao.id]))

    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("entrar")


def test_remover_lista_nao_apaga_nem_impede_proximo_registro(aprovador, sugestao, monkeypatch):
    assert aprovador.gestao.assinar(aprovador, sugestao).status_code == 200

    monkeypatch.delenv("SUGESTOES_APROVADORES")

    assert aprovador.gestao.assinar(aprovador, sugestao).status_code == 200
    assert ChangeSpecAprovado.objects.count() == 2


def test_lista_antiga_nao_altera_autoria(
    entrar_como_staff, lista_de_aprovadores, sugestao
):
    lista_de_aprovadores("  MANTENEDOR@Meshcraft.TEST  ")
    pessoa = entrar_como_staff(email="mantenedor@meshcraft.test", nome="Mantenedor")

    assert pessoa.gestao.assinar(pessoa, sugestao).status_code == 200
    assert ChangeSpecAprovado.objects.get().registrado_por_id == pessoa.identidade.id


# ---------------------------------------------------------------------------
# O que vale registro
# ---------------------------------------------------------------------------


def test_o_registro_guarda_as_duas_pessoas(aprovador, sugestao):
    """Metadados explícitos não substituem a identidade responsável."""
    assert _registrar(aprovador, sugestao).status_code == 200

    registro = ChangeSpecAprovado.objects.get()
    assert registro.change_id == "CS-SUGESTOES-0007"
    assert registro.aprovado_por == "Davi (mantenedor)"
    assert registro.registrado_por_id == aprovador.identidade.id
    assert registro.registrado_em is not None
    assert str(registro.aprovado_em) == "2026-08-25"


def test_identificador_fornecido_pode_ser_texto_livre(aprovador, sugestao):
    resposta = _registrar(aprovador, sugestao, change_id="melhoria do portfólio")

    assert resposta.status_code == 200, resposta.content
    assert ChangeSpecAprovado.objects.get().change_id == "melhoria do portfólio"


@pytest.mark.parametrize(
    "campo,valor,pedaco_do_recado",
    [
        ("change_id", "x" * 61, "60 caracteres"),
        ("documento", "x" * 301, "300 caracteres"),
        ("aprovado_por", "x" * 121, "120 caracteres"),
        ("aprovado_por", "mantenedor@meshcraft.test", "e-mail fica na identidade"),
    ],
)
def test_metadado_invalido_e_recusado_sem_gravar(
    aprovador, sugestao, campo, valor, pedaco_do_recado
):
    """A largura do banco e a privacidade continuam válidas."""
    resposta = _registrar(aprovador, sugestao, **{campo: valor})

    assert resposta.status_code == 422, resposta.content
    assert pedaco_do_recado in resposta.json()["erro"]
    assert ChangeSpecAprovado.objects.count() == 0


@pytest.mark.parametrize("valor", ["ontem", "2026-13-45"])
def test_uma_data_que_nao_e_data_e_recusada_ANTES_de_qualquer_escrita(
    aprovador, sugestao, valor
):
    """Uma data fornecida precisa ser válida."""
    resposta = _registrar(aprovador, sugestao, aprovado_em=valor)

    assert resposta.status_code == 422, resposta.content
    assert ChangeSpecAprovado.objects.count() == 0


def test_o_mesmo_changespec_duas_vezes_vira_uma_linha_e_uma_frase(aprovador, sugestao):
    """A unicidade impede sobrescrever um registro anterior."""
    assert _registrar(aprovador, sugestao).status_code == 200
    repetido = _registrar(aprovador, sugestao)

    assert repetido.status_code == 422
    assert "já está registrado" in repetido.json()["erro"]
    assert ChangeSpecAprovado.objects.count() == 1


def test_o_mesmo_changespec_pode_referenciar_outra_ideia(
    aprovador, sugestao, categoria, aluno
):
    """Formato §2: ChangeSpec nascido de várias sugestões referencia todas.

    A unicidade é do PAR (sugestão, change_id) por causa disto — `change_id`
    único sozinho proibiria o caso que o formato manda existir.
    """
    from apps.sugestoes.models import Sugestao

    outra = Sugestao.objects.create(
        quadro=sugestao.quadro,
        categoria=categoria,
        autor=aluno,
        titulo="A mesma dor, com outras palavras",
        problema="nenhum",
    )

    assert _registrar(aprovador, sugestao).status_code == 200
    assert _registrar(aprovador, outra).status_code == 200
    assert ChangeSpecAprovado.objects.count() == 2


def test_o_que_foi_registrado_pode_ser_CONFERIDO_depois(aprovador, sugestao):
    """A razão de a TAR-023 existir, medida do lado de cá.

    Registrar sem poder conferir depois seria uma assinatura que ninguém audita
    — e foi exatamente isso que travou a aposentadoria destas telas (registro
    `20260830-019`). A ficha inteira volta pela mesma porta por onde entrou.
    """
    _registrar(aprovador, sugestao)

    corpo = aprovador.gestao.uma_ideia(sugestao.id).json()

    (ficha,) = corpo["changespecs"]
    assert ficha["change_id"] == "CS-SUGESTOES-0007"
    assert ficha["documento"] == "docs/changespecs/CS-SUGESTOES-0007.md"
    assert ficha["aprovado_por"] == "Davi (mantenedor)"


def test_o_urlconf_continua_sem_conhecer_o_prefixo(sugestao):
    """A célula é dona do próprio endereço por configuração, não por código.

    Continua valendo depois da aposentadoria: o endereço não sumiu, ele só
    passou a redirecionar — e quem lhe dá o prefixo público segue sendo o
    `FORCE_SCRIPT_NAME`, nunca uma string no urlconf.
    """
    cliente = Client()

    assert (
        cliente.get(f"{PREFIXO}/moderacao/{sugestao.id}/changespec").status_code == 404
    )
    assert reverse("changespecs", args=[sugestao.id]) == (
        f"/moderacao/{sugestao.id}/changespec"
    )
