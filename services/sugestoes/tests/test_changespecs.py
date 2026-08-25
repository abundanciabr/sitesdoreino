"""A tela de quem aprova (EVO-40): quem entra, o que vale registro, e o prefixo.

O invariante — a trava em si — mora em
`test_inv_changespec_trava_o_desenvolvimento.py`. Aqui está o portão que a
sustenta e a superfície que a equipe usa:

* **fail-closed do aprovador**: `SUGESTOES_APROVADORES` ausente ⇒ ninguém
  registra, nem quem tem o crachá da equipe. É a decisão do mantenedor de
  25/08/2026, na forma mais travada que ele podia escolher: até o e-mail dele
  existir no servidor, nada anda. "Não sei quem pode aprovar" jamais vira
  "então pode qualquer um";
* **os dois papéis são dois**: estar em `SUGESTOES_STAFF_EMAILS` não dá o
  mandato de autorizar desenvolvimento;
* **o que vale registro** (formato §3/§4): CHANGE-ID na forma, documento com
  endereço, nome humano de quem aprovou, data;
* **o prefixo público** (`armadilhas/029`, `/081` e `/102`): sob `SCRIPT_NAME`
  todo `href`/`action` escrito à mão cai no `funil`, e a tela chega sem estilo
  ou o formulário posta para o vazio — em produção, e só lá.
"""

import re

import pytest
from django.test import Client
from django.urls import clear_script_prefix, reverse, set_script_prefix

from apps.sugestoes.models import ChangeSpecAprovado

pytestmark = pytest.mark.django_db

PREFIXO = "/forms/sugestoes"
LINK_INTERNO = re.compile(r'(?:href|action)="(/[^"]*)"')

VALIDO = {
    "change_id": "CS-SUGESTOES-0007",
    "documento": "docs/changespecs/CS-SUGESTOES-0007.md",
    "aprovado_por": "Davi (mantenedor)",
    "aprovado_em": "2026-08-25",
}


def _registrar(pessoa, sugestao, **mudancas):
    return pessoa.client.post(
        reverse("changespecs", args=[sugestao.id]), {**VALIDO, **mudancas}
    )


# ---------------------------------------------------------------------------
# Fail-closed: sem lista, ninguém — e o crachá da equipe não substitui a lista
# ---------------------------------------------------------------------------


def test_sem_lista_de_aprovadores_ninguem_registra(equipe, sugestao):
    """O estado de fábrica da célula: `SUGESTOES_APROVADORES` nem existe.

    Este é o teste que prova que o default é seguro. Ele roda no ambiente
    padrão da suíte, onde a variável é apagada (`conftest.py::ambiente`) —
    exatamente como a VPS estará até o mantenedor escrever o e-mail dele lá.
    """
    pagina = equipe.client.get(reverse("changespecs", args=[sugestao.id]))
    escrita = _registrar(equipe, sugestao)

    assert (pagina.status_code, escrita.status_code) == (403, 403)
    assert ChangeSpecAprovado.objects.count() == 0


def test_a_lista_vazia_vale_o_mesmo_que_ausente(equipe, sugestao, monkeypatch):
    """`SUGESTOES_APROVADORES=` (ou só vírgulas e espaços) não é "todo mundo"."""
    for valor in ("", "   ", ",", " , ,"):
        monkeypatch.setenv("SUGESTOES_APROVADORES", valor)
        assert _registrar(equipe, sugestao).status_code == 403, valor

    assert ChangeSpecAprovado.objects.count() == 0


def test_staff_que_nao_e_aprovador_leva_403(equipe, sugestao, lista_de_aprovadores):
    """Moderar é da equipe; autorizar desenvolvimento é do aprovador.

    A lista existe e tem alguém dentro — só que não esta pessoa, que ainda
    assim tem o crachá e modera tudo o mais. É a diferença entre os dois papéis
    medida onde ela passa.
    """
    lista_de_aprovadores("outra.pessoa@meshcraft.test")

    recusa = _registrar(equipe, sugestao)

    assert recusa.status_code == 403
    assert b"aprovadores" in recusa.content
    assert ChangeSpecAprovado.objects.count() == 0
    # E o crachá continua inteiro: a recusa é do mandato, não da sessão.
    assert equipe.client.get(reverse("fila")).status_code == 200


def test_o_aluno_nem_chega_ao_segundo_portao(dentro, sugestao):
    """Quem não tem crachá recebe a recusa do crachá, que é a verdade dele."""
    recusa = dentro.client.get(reverse("changespecs", args=[sugestao.id]))

    assert recusa.status_code == 403
    assert b"lista de quem modera" in recusa.content


def test_o_anonimo_vai_para_a_porta(client, sugestao):
    """Como em toda a célula: 302, nunca 403 (`apps/core/participacao.py`)."""
    resposta = client.get(reverse("changespecs", args=[sugestao.id]))

    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("entrar")


def test_o_mandato_sai_com_a_variavel_de_ambiente(aprovador, sugestao, monkeypatch):
    """Derivado a cada requisição, como o crachá — nunca gravado.

    Tirar alguém da lista no servidor e reiniciar tira o mandato no ato, mesmo
    de quem já está com a sessão aberta. É a mesma promessa da `DECISAO-EVO-01`
    §4, e ela só é verdadeira se nada disto for persistido.
    """
    assert _registrar(aprovador, sugestao).status_code == 302

    monkeypatch.delenv("SUGESTOES_APROVADORES")

    assert (
        _registrar(aprovador, sugestao, change_id="CS-SUGESTOES-0008").status_code
        == 403
    )
    assert ChangeSpecAprovado.objects.count() == 1


def test_o_email_do_aprovador_e_comparado_normalizado(
    entrar_como_staff, lista_de_aprovadores, sugestao
):
    """Maiúsculas e espaços na variável não podem custar o mandato de alguém —
    ela é digitada à mão num `.env`."""
    lista_de_aprovadores("  MANTENEDOR@Meshcraft.TEST  ")
    pessoa = entrar_como_staff(email="mantenedor@meshcraft.test", nome="Mantenedor")

    assert _registrar(pessoa, sugestao).status_code == 302


# ---------------------------------------------------------------------------
# O que vale registro
# ---------------------------------------------------------------------------


def test_o_registro_guarda_as_duas_pessoas(aprovador, sugestao):
    """Quem aprovou e quem registrou são campos diferentes (formato §1)."""
    assert _registrar(aprovador, sugestao).status_code == 302

    registro = ChangeSpecAprovado.objects.get()
    assert registro.change_id == "CS-SUGESTOES-0007"
    assert registro.aprovado_por == "Davi (mantenedor)"
    assert registro.registrado_por_id == aprovador.identidade.id
    assert registro.registrado_em is not None
    assert str(registro.aprovado_em) == "2026-08-25"


@pytest.mark.parametrize(
    "campo,valor,pedaco_do_recado",
    [
        ("change_id", "melhoria do portfolio", "CS-{CELULA}"),
        ("change_id", "cs-sugestoes-0007", "CS-{CELULA}"),
        ("change_id", "", "CS-{CELULA}"),
        ("documento", "o documento que escrevi ontem", "docs/changespecs/"),
        ("documento", "", "docs/changespecs/"),
        ("aprovado_por", "", "aprovação humana e nominal"),
        ("aprovado_por", "mantenedor@meshcraft.test", "e-mail vive numa linha só"),
        ("aprovado_em", "ontem", "AAAA-MM-DD"),
        ("aprovado_em", "", "AAAA-MM-DD"),
    ],
)
def test_registro_incompleto_e_recusado_dizendo_o_que_falta(
    aprovador, sugestao, campo, valor, pedaco_do_recado
):
    """Cada recusa devolve a REGRA, não um "campo inválido".

    O `aprovado_por` com e-mail dentro tem motivo próprio: nesta célula o
    e-mail vive numa linha só (`DECISAO-EVO-01` §3), e um campo de texto livre
    é exatamente por onde ele voltaria a se espalhar.
    """
    resposta = _registrar(aprovador, sugestao, **{campo: valor})

    assert resposta.status_code == 400
    assert pedaco_do_recado in resposta.content.decode()
    assert ChangeSpecAprovado.objects.count() == 0


def test_o_que_foi_digitado_volta_na_tela(aprovador, sugestao):
    """Quem errou um campo não reescreve os outros três."""
    corpo = _registrar(aprovador, sugestao, aprovado_em="ontem").content.decode()

    assert 'value="CS-SUGESTOES-0007"' in corpo
    assert 'value="Davi (mantenedor)"' in corpo


def test_o_mesmo_changespec_duas_vezes_vira_uma_linha_e_uma_frase(aprovador, sugestao):
    """A imutabilidade do §4 pela porta da frente: registrar de novo não edita."""
    assert _registrar(aprovador, sugestao).status_code == 302
    repetido = _registrar(aprovador, sugestao)

    assert repetido.status_code == 400
    assert "-v2" in repetido.content.decode()
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

    assert _registrar(aprovador, sugestao).status_code == 302
    assert _registrar(aprovador, outra).status_code == 302
    assert ChangeSpecAprovado.objects.count() == 2


def test_a_tela_mostra_o_que_ja_esta_registrado(aprovador, sugestao):
    _registrar(aprovador, sugestao)

    corpo = aprovador.client.get(
        reverse("changespecs", args=[sugestao.id])
    ).content.decode()

    assert "CS-SUGESTOES-0007" in corpo
    assert "docs/changespecs/CS-SUGESTOES-0007.md" in corpo
    assert "Davi (mantenedor)" in corpo


def test_a_tela_vazia_explica_a_consequencia(aprovador, sugestao):
    """Lista vazia não é um vazio mudo: ela diz o que está barrado por isso."""
    corpo = aprovador.client.get(
        reverse("changespecs", args=[sugestao.id])
    ).content.decode()

    assert "Nenhum ChangeSpec registrado" in corpo
    assert "Em desenvolvimento" in corpo


# ---------------------------------------------------------------------------
# O prefixo público (armadilhas/029, /081, /102)
# ---------------------------------------------------------------------------


@pytest.fixture
def sob_prefixo(settings):
    settings.FORCE_SCRIPT_NAME = PREFIXO
    set_script_prefix(PREFIXO)
    yield
    clear_script_prefix()  # o prefixo é de THREAD e vaza entre testes


def test_todo_link_e_action_da_tela_levam_o_prefixo(aprovador, sugestao, sob_prefixo):
    """Inclusive o `action` do formulário: sem prefixo, o registro posta para
    um endereço que em `meshcraft.top` pertence ao `funil`.

    O endereço é escrito à mão aqui, e nunca por `reverse()`: com o prefixo
    ligado, o `reverse()` devolve `/forms/sugestoes/…`, que para o client
    síncrono é o `path_info` INTEIRO — e a requisição daria 404 dentro de um
    teste que não é sobre resolução de URL (`armadilhas/081`).
    """
    endereco = f"/moderacao/{sugestao.id}/changespec"
    assert aprovador.client.post(endereco, VALIDO).status_code == 302
    corpo = aprovador.client.get(endereco).content.decode()
    internos = LINK_INTERNO.findall(corpo)

    assert f"{PREFIXO}/moderacao/{sugestao.id}/changespec" in internos
    sem_prefixo = [link for link in internos if not link.startswith(f"{PREFIXO}/")]
    assert sem_prefixo == [], (
        f"links sem o prefixo público: {sem_prefixo}. Todo endereço interno sai "
        "de {% url %}, nunca escrito à mão."
    )


def test_a_folha_de_estilo_da_tela_sai_com_o_prefixo(aprovador, sugestao, sob_prefixo):
    """`{% static %}` devolveria `/static/…` — endereço do `funil`
    (`armadilhas/102`, paga em produção pelo EVO-30)."""
    corpo = aprovador.client.get(
        f"/moderacao/{sugestao.id}/changespec"
    ).content.decode()

    assert f'href="{PREFIXO}/static/sugestoes/caixa.css"' in corpo


def test_o_urlconf_continua_sem_conhecer_o_prefixo(sugestao):
    """A célula é dona do próprio endereço por configuração, não por código."""
    cliente = Client()

    assert (
        cliente.get(f"{PREFIXO}/moderacao/{sugestao.id}/changespec").status_code == 404
    )
    assert reverse("changespecs", args=[sugestao.id]) == (
        f"/moderacao/{sugestao.id}/changespec"
    )
