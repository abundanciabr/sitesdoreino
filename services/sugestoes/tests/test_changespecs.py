"""O corredor do ChangeSpec (EVO-40): quem registra e o que vale registro.

O invariante — a trava em si — mora em
`test_inv_changespec_trava_o_desenvolvimento.py`. Aqui está o **portão** que a
sustenta e o **formato** que ele exige:

* **fail-closed do aprovador**: `SUGESTOES_APROVADORES` ausente ⇒ ninguém
  registra, nem quem tem o crachá da equipe. É a decisão do mantenedor de
  25/08/2026, na forma mais travada que ele podia escolher: até o e-mail dele
  existir no servidor, nada anda. "Não sei quem pode aprovar" jamais vira
  "então pode qualquer um";
* **os dois papéis são dois**: estar em `SUGESTOES_STAFF_EMAILS` — e, desde a
  mudança de casa, estar no Admin — não dá o mandato de autorizar
  desenvolvimento;
* **o que vale registro** (formato §3/§4): CHANGE-ID na forma, documento com
  endereço, nome humano de quem aprovou, data.

**A TELA saiu daqui em 30/08/2026** (TAR-023 degrau 4). Quem registra é o Admin,
em `/admin/caixa/ideia/<id>`, e ele chega pelo contrato — então é por lá que
estes guardas provocam o fato, pela `conftest.Gestao`. O portão **não mudou de
dono nem afrouxou**: quem decide continua sendo `e_aprovador()`, com a mesma
frase (`SEM_MANDATO`) e o mesmo 403.

O que saiu junto com a tela, e onde foi parar:

| O que media | Onde vive agora |
|---|---|
| a lista do que já está registrado | a ficha em `services/admin` (`caixa_ideia.html`) e o campo `changespecs` do contrato |
| o rascunho voltando no formulário recusado | é do formulário, e formulário é do Admin |
| `href`/`action` com o prefixo público | não há mais página desta célula com formulário de moderação |

Os guardas de prefixo que sobraram são os do endereço aposentado, em
`test_moderacao_script_name.py`.
"""

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
    """A jornada REAL de hoje: o Admin pedindo à Caixa pelo contrato."""
    return pessoa.gestao.assinar(pessoa, sugestao, **{**VALIDO, **mudancas})


# ---------------------------------------------------------------------------
# Fail-closed: sem lista, ninguém — e o crachá da equipe não substitui a lista
# ---------------------------------------------------------------------------


def test_sem_lista_de_aprovadores_ninguem_registra(equipe, sugestao):
    """O estado de fábrica da célula: `SUGESTOES_APROVADORES` nem existe.

    Este é o teste que prova que o default é seguro. Ele roda no ambiente
    padrão da suíte, onde a variável é apagada (`conftest.py::ambiente`) —
    exatamente como a VPS estará até o mantenedor escrever o e-mail dele lá.
    """
    escrita = _registrar(equipe, sugestao)

    assert escrita.status_code == 403, escrita.content
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
    assert "aprovadores" in recusa.json()["erro"]
    assert ChangeSpecAprovado.objects.count() == 0
    # E a MODERAÇÃO continua inteira: a recusa é do mandato, não do crachá. 301
    # e não 403 — o endereço antigo redireciona para quem tem crachá.
    assert equipe.client.get(reverse("fila")).status_code == 301


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


def test_o_mandato_sai_com_a_variavel_de_ambiente(aprovador, sugestao, monkeypatch):
    """Derivado a cada requisição, como o crachá — nunca gravado.

    Tirar alguém da lista no servidor e reiniciar tira o mandato no ato, mesmo
    de quem já está com a sessão aberta. É a mesma promessa da `DECISAO-EVO-01`
    §4, e ela só é verdadeira se nada disto for persistido.
    """
    assert _registrar(aprovador, sugestao).status_code == 200

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

    assert _registrar(pessoa, sugestao).status_code == 200


# ---------------------------------------------------------------------------
# O que vale registro
# ---------------------------------------------------------------------------


def test_o_registro_guarda_as_duas_pessoas(aprovador, sugestao):
    """Quem aprovou e quem registrou são campos diferentes (formato §1)."""
    assert _registrar(aprovador, sugestao).status_code == 200

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
    ],
)
def test_registro_incompleto_e_recusado_dizendo_o_que_falta(
    aprovador, sugestao, campo, valor, pedaco_do_recado
):
    """Cada recusa devolve a REGRA, não um "campo inválido".

    O `aprovado_por` com e-mail dentro tem motivo próprio: nesta célula o
    e-mail vive numa linha só (`DECISAO-EVO-01` §3), e um campo de texto livre
    é exatamente por onde ele voltaria a se espalhar.

    422 e não mais 400: a recusa deixou de ser uma página redesenhada e passou
    a ser a `Recusa` do contrato. A FRASE é a mesma — ela nasce em
    `changespecs._conferir` e atravessa a fronteira inteira.
    """
    resposta = _registrar(aprovador, sugestao, **{campo: valor})

    assert resposta.status_code == 422, resposta.content
    assert pedaco_do_recado in resposta.json()["erro"]
    assert ChangeSpecAprovado.objects.count() == 0


@pytest.mark.parametrize("valor", ["ontem", "", "2026-13-45"])
def test_uma_data_que_nao_e_data_e_recusada_ANTES_de_qualquer_escrita(
    aprovador, sugestao, valor
):
    """A data é a única recusa que NÃO carrega a frase em português, e é aqui
    que isso fica escrito para quem vier depois.

    `ChangeSpecEscrito.aprovado_em` é `date` no contrato congelado
    (`format: date`), então quem recusa é a validação do django-ninja, ANTES de
    `changespecs._conferir` — a resposta vem como `{"detail": [...]}`, não como
    `{"erro": "…"}`. O Admin traduz isso em "a Caixa recusou, sem dizer o
    motivo" (`clients.CaixaClient._escrever`).

    **Não é regressão desta mudança** — a porta de máquina se comporta assim
    desde que nasceu (28/08/2026), e na prática o campo é um `<input
    type="date">`, que só envia data válida ou vazio. Ficou anotado porque a
    diferença é real e a próxima pessoa merece encontrá-la escrita em vez de
    descobri-la. O que este guarda garante, e é o que importa: **nada é
    escrito**.
    """
    resposta = _registrar(aprovador, sugestao, aprovado_em=valor)

    assert resposta.status_code == 422, resposta.content
    assert ChangeSpecAprovado.objects.count() == 0


def test_o_mesmo_changespec_duas_vezes_vira_uma_linha_e_uma_frase(aprovador, sugestao):
    """A imutabilidade do §4 pela porta da frente: registrar de novo não edita."""
    assert _registrar(aprovador, sugestao).status_code == 200
    repetido = _registrar(aprovador, sugestao)

    assert repetido.status_code == 422
    assert "-v2" in repetido.json()["erro"]
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
