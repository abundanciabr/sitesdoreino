"""O cabeçalho de apêndice vivo — TAR-247, `PLANO-CELULA-CURSOS.md` §3.8 (degrau 3.3).

O que faltava na área de documentos, e o que este arquivo trava: um documento
marcado como apêndice vivo mostra no topo, para quem lê (público e admin), a
versão, quando foi verificado e quando a verificação vence; passada a data, o
PRÓPRIO documento mostra o aviso de verificação vencida — sem tela nova, sem
lista própria: o fato sai do documento (`documentos.cabecalho_de_apendice`, a
ÚNICA conta, lida pelas duas telas).

As seis coisas medidas aqui:

1. Documento comum não ganha cabeçalho nenhum, em nenhuma das duas telas.
2. Apêndice vivo com a verificação em dia mostra o cabeçalho com a versão e as
   duas datas em `DD/MM/AAAA`, sem aviso, nas duas telas.
3. Passada a data — o dia SEGUINTE ao vencimento — o aviso aparece, nas duas
   telas; no dia EXATO do vencimento, ainda não (a borda é `hoje >
   proxima_verificacao_em`, nunca `>=`).
4. A versão é calculada (`documento.versoes.count()`), nunca gravada: muda
   sozinha quando o documento é salvo de novo pelo editor.
5. O editor recusa apêndice vivo sem as duas datas, ou com a próxima não
   depois da última, com as frases certas — e aceita quando está certo. O
   `CheckConstraint` é a SEGUNDA tranca, contra gravação direta pelo modelo,
   por fora do editor.
6. Documento arquivado ou privado continua 404 no público, apêndice vivo ou
   não — a regra de visibilidade de sempre não muda por causa deste cabeçalho.
"""

from __future__ import annotations

import datetime as dt

import httpx
import pytest
import respx
from django.db import IntegrityError, transaction
from django.test import Client

from apps.core import views as vistas
from apps.core.models import Documento

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"


@pytest.fixture(autouse=True)
def env(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", BASE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


@pytest.fixture(autouse=True)
def sem_os_semeados():
    """A migração `0003` semeia os documentos de verdade quando o banco de
    teste nasce, e o rollback volta para o estado SEMEADO. Cada teste daqui
    monta o próprio mundo."""
    Documento.objects.all().delete()


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
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _apendice(
    nome="apendice",
    *,
    publico=True,
    arquivado=False,
    verificado=dt.date(2026, 8, 1),
    proxima=dt.date(2026, 9, 10),
) -> Documento:
    return Documento.objects.create(
        nome=nome,
        titulo="Um documento vivo",
        corpo="O corpo do texto.",
        publico=publico,
        arquivado=arquivado,
        apendice_vivo=True,
        verificado_em=verificado,
        proxima_verificacao_em=proxima,
    )


# ------------------------------------------------ 1. documento comum


@respx.mock
def test_documento_comum_nao_ganha_cabecalho_em_nenhuma_tela():
    Documento.objects.create(
        nome="comum", titulo="Comum", corpo="Um texto qualquer.", publico=True
    )

    publico = Client().get("/docs/comum").content.decode()
    assert "Apêndice vivo" not in publico

    admin = _dentro().get("/documentos/comum").content.decode()
    assert "Apêndice vivo" not in admin


# --------------------------------------- 2. em dia: cabeçalho sem aviso


def test_apendice_vivo_em_dia_mostra_versao_e_datas_sem_aviso_no_publico(
    monkeypatch,
):
    monkeypatch.setattr(vistas.timezone, "localdate", lambda: dt.date(2026, 9, 5))
    _apendice("emdia")
    esperado = (
        "Apêndice vivo · versão 1 · verificado em 01/08/2026 · "
        "próxima verificação em 10/09/2026"
    )

    pagina = Client().get("/docs/emdia").content.decode()
    assert esperado in pagina
    assert "venceu" not in pagina


@respx.mock
def test_apendice_vivo_em_dia_mostra_versao_e_datas_sem_aviso_no_admin(monkeypatch):
    monkeypatch.setattr(vistas.timezone, "localdate", lambda: dt.date(2026, 9, 5))
    _apendice("emdia2")
    esperado = (
        "Apêndice vivo · versão 1 · verificado em 01/08/2026 · "
        "próxima verificação em 10/09/2026"
    )

    pagina = _dentro().get("/documentos/emdia2").content.decode()
    assert esperado in pagina
    assert "venceu" not in pagina


# --------------------------------------- 3. vencida: o aviso, e a borda


def test_o_dia_seguinte_ao_vencimento_mostra_o_aviso_no_publico(monkeypatch):
    monkeypatch.setattr(vistas.timezone, "localdate", lambda: dt.date(2026, 9, 11))
    _apendice("vencido")
    esperado = (
        "Esta verificação venceu em 10/09/2026. O texto continua no ar e "
        "pode estar desatualizado."
    )

    assert esperado in Client().get("/docs/vencido").content.decode()


@respx.mock
def test_o_dia_seguinte_ao_vencimento_mostra_o_aviso_no_admin(monkeypatch):
    monkeypatch.setattr(vistas.timezone, "localdate", lambda: dt.date(2026, 9, 11))
    _apendice("vencido2")
    esperado = (
        "Esta verificação venceu em 10/09/2026. O texto continua no ar e "
        "pode estar desatualizado."
    )

    assert esperado in _dentro().get("/documentos/vencido2").content.decode()


def test_no_dia_exato_do_vencimento_ainda_nao_ha_aviso(monkeypatch):
    monkeypatch.setattr(vistas.timezone, "localdate", lambda: dt.date(2026, 9, 10))
    _apendice("borda")

    pagina = Client().get("/docs/borda").content.decode()
    assert "venceu" not in pagina
    assert "Apêndice vivo · versão 1" in pagina


# --------------------------------------- 4. a versão é calculada


@respx.mock
def test_a_versao_muda_quando_o_documento_e_salvo_de_novo(monkeypatch):
    monkeypatch.setattr(vistas.timezone, "localdate", lambda: dt.date(2026, 9, 5))
    Documento.objects.create(nome="conta", titulo="Conta", corpo="Um texto.")
    cliente = _dentro()
    campos = {
        "titulo": "Conta",
        "corpo": "Um texto.",
        "ordem": "10",
        "apendice_vivo": "sim",
        "verificado_em": "2026-08-01",
        "proxima_verificacao_em": "2026-09-10",
    }

    cliente.post("/documentos/conta/salvar", campos)
    pagina = cliente.get("/documentos/conta").content.decode()
    assert (
        "Apêndice vivo · versão 1 · verificado em 01/08/2026 · "
        "próxima verificação em 10/09/2026"
    ) in pagina

    cliente.post("/documentos/conta/salvar", campos)
    pagina = cliente.get("/documentos/conta").content.decode()
    assert (
        "Apêndice vivo · versão 2 · verificado em 01/08/2026 · "
        "próxima verificação em 10/09/2026"
    ) in pagina


# --------------------------------------- 5. a recusa do editor, e a tranca do banco


@respx.mock
def test_o_editor_recusa_apendice_vivo_sem_as_duas_datas():
    Documento.objects.create(nome="semdata", titulo="X", corpo="c")
    resposta = _dentro().post(
        "/documentos/semdata/salvar",
        {"titulo": "X", "corpo": "c", "ordem": "10", "apendice_vivo": "sim"},
    )
    assert resposta.status_code == 422
    assert (
        "Um apêndice vivo precisa das duas datas: quando foi verificado e "
        "quando a verificação vence."
    ) in resposta.content.decode()
    assert Documento.objects.get(nome="semdata").apendice_vivo is False


@respx.mock
def test_o_editor_recusa_a_proxima_verificacao_nao_depois_da_ultima():
    Documento.objects.create(nome="ordemtorta", titulo="X", corpo="c")
    resposta = _dentro().post(
        "/documentos/ordemtorta/salvar",
        {
            "titulo": "X",
            "corpo": "c",
            "ordem": "10",
            "apendice_vivo": "sim",
            "verificado_em": "2026-09-10",
            "proxima_verificacao_em": "2026-09-10",
        },
    )
    assert resposta.status_code == 422
    assert (
        "A próxima verificação precisa ser depois da última."
        in resposta.content.decode()
    )
    assert Documento.objects.get(nome="ordemtorta").apendice_vivo is False


@respx.mock
def test_o_editor_aceita_apendice_vivo_com_as_datas_certas():
    Documento.objects.create(nome="certo", titulo="X", corpo="c")
    resposta = _dentro().post(
        "/documentos/certo/salvar",
        {
            "titulo": "X",
            "corpo": "c",
            "ordem": "10",
            "apendice_vivo": "sim",
            "verificado_em": "2026-08-01",
            "proxima_verificacao_em": "2026-09-10",
        },
    )
    assert resposta.status_code == 302
    documento = Documento.objects.get(nome="certo")
    assert documento.apendice_vivo is True
    assert documento.verificado_em == dt.date(2026, 8, 1)
    assert documento.proxima_verificacao_em == dt.date(2026, 9, 10)


def test_o_check_constraint_recusa_apendice_vivo_sem_data_pelo_modelo():
    """A segunda tranca: escrita direta pelo modelo, por fora do editor."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Documento.objects.create(nome="direto", titulo="Direto", apendice_vivo=True)


def test_o_check_constraint_recusa_proxima_nao_depois_da_ultima_pelo_modelo():
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Documento.objects.create(
                nome="direto2",
                titulo="Direto2",
                apendice_vivo=True,
                verificado_em=dt.date(2026, 9, 10),
                proxima_verificacao_em=dt.date(2026, 9, 10),
            )


# --------------------------------------- 6. arquivado e privado continuam 404


def test_documento_arquivado_continua_404_no_publico_mesmo_apendice_vivo():
    _apendice("arquivadoav", arquivado=True)
    assert Client().get("/docs/arquivadoav").status_code == 404


def test_documento_privado_continua_404_no_publico_mesmo_apendice_vivo():
    _apendice("privadoav", publico=False)
    assert Client().get("/docs/privadoav").status_code == 404
