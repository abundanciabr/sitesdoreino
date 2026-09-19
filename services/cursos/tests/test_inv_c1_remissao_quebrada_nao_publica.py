"""[INV-CUR-C1] Nenhuma aula publica com remissao "E[NN]" para aula inexistente.

Lei: `docs/decisoes/PLANO-CELULA-CURSOS.md` §9 (os invariantes do conteudo) e
§7 (a linha "Revisor de coerencia": "remissao quebrada **recusa publicar**").
Degrau 3.1 da escada (TAR-245).

O QUE ESTE ARQUIVO PROVA, E POR QUE CADA PEDACO
------------------------------------------------
O invariante e de PORTA, nao de tela: quem recusa e `publishLesson` e
`publishSiteLesson`, com 422, e qualquer tela futura herda a recusa sem
reescrever a regra. Por isso as medidas sao feitas na porta, pelos dois
caminhos, e nao no verificador.

Uma remissao para uma aula que EXISTE nunca impede publicar, e essa metade e
tao importante quanto a outra: o modo de falhar deste degrau e o falso
positivo, e um invariante que recusasse a aula certa seria pior do que nao
existir.

E as OUTRAS cinco conferencias nao vetam nada. O §7 poe o veto so na remissao,
e um guarda que deixasse "aviso" virar "recusa" fecharia a publicacao do curso
inteiro por uma divergencia de grafia.
"""

from __future__ import annotations

import pytest
from django.test import Client

from apps.cursos.models import Aula, Peca
from tests.conftest import SITE

pytestmark = pytest.mark.django_db

TOKEN = "token-do-editor-do-admin"
BASE = "/api/cursos"


@pytest.fixture(autouse=True)
def par_autorizado(settings):
    settings.TOKENS_ACEITOS = {TOKEN}


def publicar_pelo_curso(numero: str = "E00"):
    return Client().post(
        f"{BASE}/cursos/profissional/aulas/{numero}/publicar?site_id={SITE}",
        HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
    )


def publicar_pelo_site(numero: str = "E00"):
    return Client().post(
        f"{BASE}/aulas/{numero}/publicar?site_id={SITE}",
        HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
    )


def escrever(aula: Aula, texto: str, tipo: str = Peca.Tipo.DRILLS) -> None:
    Peca.objects.update_or_create(aula=aula, tipo=tipo, defaults={"texto": texto})


@pytest.fixture
def e00(esqueleto) -> Aula:
    return esqueleto.aulas.get(numero="E00")


def test_a_remissao_quebrada_recusa_publicar_pelo_caminho_do_curso(e00):
    escrever(e00, "Se voce travar, volte na E99 e refaca o cubo.")

    resposta = publicar_pelo_curso()

    assert resposta.status_code == 422
    assert "E99" in resposta.json()["detail"]
    e00.refresh_from_db()
    assert e00.estado == Aula.Estado.RASCUNHO
    assert e00.publicada_em is None


def test_a_remissao_quebrada_recusa_publicar_tambem_pelo_caminho_do_site(e00):
    escrever(e00, "Como voce fez na E77, comece pelo bloco maior.")

    resposta = publicar_pelo_site()

    assert resposta.status_code == 422
    assert "E77" in resposta.json()["detail"]
    e00.refresh_from_db()
    assert e00.estado == Aula.Estado.RASCUNHO


def test_a_recusa_nomeia_todas_as_remissoes_quebradas(e00):
    escrever(e00, "Volte na E88 e depois na E91 antes de continuar.")

    detalhe = publicar_pelo_curso().json()["detail"]

    assert "E88" in detalhe
    assert "E91" in detalhe


def test_a_remissao_para_aula_que_existe_publica_normalmente(e00):
    escrever(e00, "Isto foi visto na E01 e volta na E32.")

    resposta = publicar_pelo_curso()

    assert resposta.status_code == 200
    e00.refresh_from_db()
    assert e00.estado == Aula.Estado.PUBLICADA
    assert e00.publicada_em is not None


def test_aula_sem_texto_nenhum_publica(e00):
    resposta = publicar_pelo_curso()

    assert resposta.status_code == 200
    e00.refresh_from_db()
    assert e00.estado == Aula.Estado.PUBLICADA


def test_as_outras_cinco_conferencias_nao_impedem_publicar(e00):
    """Aviso e aviso: so a remissao veta (§7)."""
    e00.aceito_quando = ["o cubo tem bevel"]
    e00.save(update_fields=["aceito_quando"])
    escrever(e00, "O limite hoje e de 20000 triangulos por peca.", Peca.Tipo.PEDIDO)
    escrever(e00, "Sao 3 passos.", Peca.Tipo.EU_FACO)
    escrever(e00, "Sao 5 passos.", Peca.Tipo.NOS_FAZEMOS)
    escrever(
        e00,
        "Aceito quando\n\n- outra coisa completamente diferente",
        Peca.Tipo.VOCE_FAZ,
    )
    escrever(
        e00, "Entregue o cubo.blend e depois o Cubo-Final.blend.", Peca.Tipo.DRILLS
    )

    resposta = publicar_pelo_curso()

    assert resposta.status_code == 200
    e00.refresh_from_db()
    assert e00.estado == Aula.Estado.PUBLICADA


def test_publicar_de_novo_a_aula_com_remissao_quebrada_continua_recusando(e00):
    """A idempotencia nao e porta dos fundos: aula ja publicada que ganhou uma
    remissao quebrada nao passa por "ja esta publicada, devolvo como esta"."""
    escrever(e00, "Isto foi visto na E01.")
    assert publicar_pelo_curso().status_code == 200

    escrever(e00, "Isto foi visto na E01 e na E95.")

    assert publicar_pelo_curso().status_code == 422
