"""O plano mestre local da administração."""

from pathlib import Path

import httpx
import pytest
import respx
from django.http import Http404
from django.test import Client, RequestFactory, override_settings
from django.urls import reverse

from apps.core import planos_para_ia
from apps.core.views import acesso_local

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch, tmp_path):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("ADMIN_PLANOS_DIR", str(tmp_path))
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"
    settings.ADMIN_LINK_TOKEN = "convite-local"


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": DONO,
            },
        )
    )
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = COOKIE
    return cliente


def _md(pasta: Path, nome: str, texto: str) -> None:
    (pasta / nome).write_text(texto, encoding="utf-8")


@override_settings(
    ADMIN_LINK_TOKEN="convite-local",
    ADMIN_LOCAL_EMAIL=DONO,
    ADMIN_LOCAL_ID="id-local",
    ADMIN_LOCAL_NOME="Mantenedor local",
)
def test_convite_local_assina_cookie_e_abre_a_tela_sem_google():
    cliente = Client()
    entrada = acesso_local(
        RequestFactory().get("/acesso-local/convite-local/?next=/plano-mestre/"),
        "convite-local",
    )
    assert entrada.status_code == 302
    assert entrada["Location"] == "/plano-mestre/"
    assert "admin_acesso_local" in entrada.cookies

    cliente.cookies.update(entrada.cookies)
    pagina = cliente.get("/plano-mestre/")
    assert pagina.status_code == 200
    assert "/entrar/google" not in pagina.content.decode()


@override_settings(ADMIN_LINK_TOKEN="convite-local")
def test_convite_local_invalido_recusa_e_explica_o_proximo_passo():
    resposta = acesso_local(
        RequestFactory().get("/acesso-local/outro-token/"), "outro-token"
    )
    assert resposta.status_code == 404
    assert "Gere outro pelo lançador local" in resposta.content.decode()


@override_settings(
    ADMIN_LINK_TOKEN="convite-local",
    ADMIN_LOCAL_EMAIL=DONO,
    ADMIN_EMAILS="outro@exemplo.com",
)
def test_cookie_local_fora_da_lista_oficial_nao_autoriza():
    cliente = Client()
    entrada = acesso_local(
        RequestFactory().get("/acesso-local/convite-local/"), "convite-local"
    )
    cliente.cookies.update(entrada.cookies)
    resposta = cliente.get("/plano-mestre/")
    assert resposta.status_code == 302
    assert "/entrar/google" in resposta["Location"]


@respx.mock
def test_lista_os_markdowns_da_pasta_sem_nome_digitado(tmp_path):
    _md(
        tmp_path,
        "10-DESENHO-ponte-privada.md",
        "# A ponte privada\n\nResumo que veio do documento.\n",
    )
    html = _dentro().get(reverse("plano_mestre")).content.decode()
    assert "10-DESENHO-ponte-privada.md" in html
    assert "A ponte privada" in html
    assert "Resumo que veio do documento." in html
    assert "10-DESENHO-A-ponte-privada.md" not in html


@respx.mock
def test_pasta_ausente_ou_vazia_diz_o_caminho(monkeypatch, tmp_path):
    ausente = tmp_path / "nao-existe"
    monkeypatch.setenv("ADMIN_PLANOS_DIR", str(ausente))
    html = _dentro().get(reverse("plano_mestre")).content.decode()
    assert str(ausente) in html
    assert "Crie a pasta ou ajuste o caminho no lançador local." in html


@respx.mock
def test_documento_local_nao_exige_marca_publica_e_renderiza_tabela(tmp_path):
    _md(
        tmp_path,
        "00-SINTESE.md",
        "# Síntese\n\n| Coluna | Valor |\n|---|---|\n| A | B |\n",
    )
    resposta = _dentro().get(reverse("plano_mestre_documento", args=["00-SINTESE.md"]))
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["titulo"] == "Síntese"
    assert "<table>" in corpo["html"]
    assert "<td>B</td>" in corpo["html"]


@respx.mock
def test_leitor_local_nao_aceita_caminho_fora_da_pasta(tmp_path):
    _md(tmp_path, "00-SINTESE.md", "# Síntese\n")
    for nome in ("..%2fsegredo", "00-SINTESE.txt", "00/SINTESE"):
        resposta = _dentro().get(f"/plano-mestre/documentos/{nome}")
        assert resposta.status_code == 404
        assert str(tmp_path) not in resposta.content.decode(errors="ignore")


def test_resolvedor_local_confere_que_o_alvo_continua_na_pasta(monkeypatch, tmp_path):
    segredo = tmp_path.parent / "segredo.md"
    segredo.write_text("# Segredo\n", encoding="utf-8")
    monkeypatch.setenv("ADMIN_PLANOS_DIR", str(tmp_path))
    monkeypatch.setattr(
        planos_para_ia,
        "RE_NOME",
        type("Tudo", (), {"match": lambda self, nome: True})(),
    )
    with pytest.raises(Http404):
        planos_para_ia._arquivo_local("../segredo")


@override_settings(DEBUG=True)
@respx.mock
def test_mtime_existe_so_em_debug(tmp_path):
    _md(tmp_path, "00-SINTESE.md", "# Síntese\n")
    resposta = _dentro().get(reverse("plano_mestre_mtime"))
    assert resposta.status_code == 200
    assert resposta.json()["mtime"] > 0


@override_settings(DEBUG=False)
@respx.mock
def test_mtime_nao_existe_fora_do_debug(tmp_path):
    _md(tmp_path, "00-SINTESE.md", "# Síntese\n")
    assert _dentro().get(reverse("plano_mestre_mtime")).status_code == 404


def test_a_view_nao_guarda_nome_de_arquivo_do_plano():
    fonte = Path(planos_para_ia.__file__).read_text(encoding="utf-8")
    assert "10-DESENHO-A-ponte-privada.md" not in fonte
    assert "35-" not in fonte and "36-" not in fonte
