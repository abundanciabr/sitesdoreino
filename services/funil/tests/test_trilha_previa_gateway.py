from contextlib import contextmanager
from types import SimpleNamespace

import httpx
from django.conf import settings
from django.test import Client, override_settings

from apps.core import trilha_previa_gateway as gateway


HOST = "meshcraft.top"


def _cliente():
    return Client(HTTP_HOST=HOST)


def _upstream(monkeypatch, *, status=200, body=b"preview", headers=None):
    chamadas = []

    @contextmanager
    def stream(method, url, **kwargs):
        chamadas.append((method, url, kwargs))
        yield SimpleNamespace(status_code=status, headers=httpx.Headers(headers or {}),
                              iter_bytes=lambda: iter((body,)))

    monkeypatch.setattr(gateway.httpx, "stream", stream)
    return chamadas


def test_runtime_ausente_fecha_gateway_sem_chamar_sidecar(rede, monkeypatch):
    chamadas = _upstream(monkeypatch)
    monkeypatch.setattr(gateway.httpx, "get", lambda *args, **kwargs: SimpleNamespace(status_code=503))
    resposta = _cliente().get("/trilha/previa/")
    assert resposta.status_code == 503
    assert not chamadas
    assert resposta["Cache-Control"] == "private, no-store"
    assert resposta["X-Robots-Tag"] == "noindex, nofollow"


def test_autorizacao_consulta_sessao_e_admin_do_runtime_real(monkeypatch):
    usados = []

    @contextmanager
    def serving(servico):
        usados.append(servico)
        yield

    modulos = {
        "config.registry": SimpleNamespace(ACTIVE_SERVICES=("funil", "gamificacao")),
        "config.runtime": SimpleNamespace(serving=serving),
        "modules.gamificacao.apps.core.sessao": SimpleNamespace(quem_e=lambda request: "pessoa-opaca"),
        "modules.gamificacao.apps.core.acesso": SimpleNamespace(
            e_admin=lambda request, pessoa: usados.append(pessoa) or True),
    }
    monkeypatch.setattr(gateway, "importlib", SimpleNamespace(import_module=lambda nome: modulos[nome]))
    assert gateway._admin_real(SimpleNamespace()) is True
    assert usados == ["gamificacao", "pessoa-opaca"]


def test_funil_isolado_consulta_autorizacao_fixa_antes_do_proxy(rede, monkeypatch):
    monkeypatch.setattr(gateway, "importlib", SimpleNamespace(import_module=lambda nome:
                        SimpleNamespace(ACTIVE_SERVICES=("funil",)) if nome == "config.registry"
                        else (_ for _ in ()).throw(AssertionError(nome))))
    consultas = []
    status_autorizacao = [204]

    def autorizar(url, **kwargs):
        consultas.append((url, kwargs))
        return SimpleNamespace(status_code=status_autorizacao[0])

    monkeypatch.setattr(gateway.httpx, "get", autorizar)
    proxy = _upstream(monkeypatch)
    cliente = _cliente()
    permitido = cliente.get("/trilha/previa/etapa/5/", HTTP_COOKIE="meshcraft_sessao=opaca")
    assert permitido.status_code == 200 and len(proxy) == 1
    url, kwargs = consultas[0]
    assert url == "http://trilha-previa:8000/trilha/previa/autorizar/"
    assert kwargs["headers"] == {"Host": "meshcraft.top", "X-Forwarded-Host": "meshcraft.top",
                                 "X-Forwarded-Proto": "https", "Cookie": "meshcraft_sessao=opaca"}
    assert kwargs["timeout"] == 3.0 and kwargs["trust_env"] is False
    assert kwargs["follow_redirects"] is False

    status_autorizacao[0] = 403
    negado = cliente.post("/trilha/previa/etapa/5/", b"x", content_type="text/plain")
    assert negado.status_code == 403 and len(proxy) == 1
    status_autorizacao[0] = 503
    indisponivel = cliente.get("/trilha/previa/etapa/5/")
    assert indisponivel.status_code == 503 and len(proxy) == 1
    status_autorizacao[0] = 302
    redirecionamento = cliente.get("/trilha/previa/etapa/5/")
    assert redirecionamento.status_code == 503 and len(proxy) == 1


def test_falha_de_rede_na_autorizacao_nao_abre_proxy(rede, monkeypatch):
    monkeypatch.setattr(gateway, "importlib", SimpleNamespace(import_module=lambda nome:
                        SimpleNamespace(ACTIVE_SERVICES=("funil",))))
    def falhar(*args, **kwargs):
        raise httpx.ConnectError("sidecar indisponivel")
    monkeypatch.setattr(gateway.httpx, "get", falhar)
    proxy = _upstream(monkeypatch)
    assert _cliente().get("/trilha/previa/").status_code == 503
    assert not proxy


def test_visitante_e_equipe_nao_chegam_ao_sidecar(rede, monkeypatch):
    chamadas = _upstream(monkeypatch)
    monkeypatch.setattr(gateway, "_admin_real", lambda request: False)
    for metodo in ("get", "head"):
        resposta = getattr(_cliente(), metodo)("/trilha/previa/controle/")
        assert resposta.status_code == 403
        assert resposta["Cache-Control"] == "private, no-store"
    assert not chamadas


def test_multipart_cookie_e_cabecalhos_seguem_ao_destino_fixo(rede, monkeypatch):
    monkeypatch.setattr(gateway, "_admin_real", lambda request: True)
    chamadas = _upstream(monkeypatch, headers=[("content-type", "text/plain"),
                                           ("set-cookie", "trilha_previa_csrf=novo; Path=/; HttpOnly"),
                                           ("set-cookie", "trilha_previa_etapa=7; Path=/"),
                                           ("set-cookie", "meshcraft_sessao=intruso; Path=/"),
                                           ("set-cookie", "outro=intruso; Path=/")])
    corpo = b"--b\r\nContent-Disposition: form-data; name=arquivo; filename=um.png\r\n\r\nPNG\x00\r\n--b--\r\n"
    resposta = _cliente().generic(
        "POST", "/trilha/previa/arquivo/?etapa=7", corpo,
        content_type="multipart/form-data; boundary=b",
        HTTP_COOKIE="meshcraft_sessao=opaco; trilha_previa_csrf=antigo; outro=1",
        HTTP_AUTHORIZATION="Bearer segredo",
        HTTP_CONNECTION="upgrade", HTTP_X_FORWARDED_PROTO="http",
        HTTP_ORIGIN="https://meshcraft.top", HTTP_REFERER="https://meshcraft.top/trilha/previa/",
        HTTP_X_CSRFTOKEN="token-opaco",
    )
    assert resposta.status_code == 200 and resposta.content == b"preview"
    metodo, url, opcoes = chamadas[0]
    assert metodo == "POST" and url == "http://trilha-previa:8000/trilha/previa/arquivo/?etapa=7"
    assert opcoes["content"] == corpo and opcoes["follow_redirects"] is False
    cabecalhos = opcoes["headers"]
    assert cabecalhos["Cookie"] == "meshcraft_sessao=opaco; trilha_previa_csrf=antigo; outro=1"
    assert cabecalhos["Content-Type"] == "multipart/form-data; boundary=b"
    assert cabecalhos["Origin"] == "https://meshcraft.top"
    assert cabecalhos["Referer"] == "https://meshcraft.top/trilha/previa/"
    assert cabecalhos["X-CSRFToken"] == "token-opaco"
    assert cabecalhos["Host"] == "meshcraft.top" and cabecalhos["X-Forwarded-Proto"] == "https"
    assert "Authorization" not in cabecalhos and "Connection" not in cabecalhos
    assert resposta.cookies["trilha_previa_csrf"].value == "novo"
    assert resposta.cookies["trilha_previa_csrf"]["path"] == "/trilha/previa/"
    assert resposta.cookies["trilha_previa_etapa"]["path"] == "/trilha/previa/"
    assert "meshcraft_sessao" not in resposta.cookies and "outro" not in resposta.cookies
    assert resposta["X-Robots-Tag"] == "noindex, nofollow"


def test_get_e_head_encaminham_sem_corpo_e_sem_cache(rede, monkeypatch):
    monkeypatch.setattr(gateway, "_admin_real", lambda request: True)
    chamadas = _upstream(monkeypatch, body=b"<p>privado</p>", headers={"content-type": "text/html"})
    cliente = _cliente()
    pagina = cliente.get("/trilha/previa/etapa/5/")
    cabeca = cliente.head("/trilha/previa/etapa/5/")
    assert pagina.status_code == 200 and pagina.content == b"<p>privado</p>"
    assert cabeca.status_code == 200 and cabeca.content == b""
    assert [chamada[0] for chamada in chamadas] == ["GET", "HEAD"]
    assert all(chamada[1] == "http://trilha-previa:8000/trilha/previa/etapa/5/" for chamada in chamadas)
    assert pagina["Cache-Control"] == cabeca["Cache-Control"] == "private, no-store"


def test_post_delega_csrf_ao_sidecar_sem_liberar_origem_externa(rede, monkeypatch):
    monkeypatch.setattr(gateway, "_admin_real", lambda request: True)
    chamadas = _upstream(monkeypatch)
    middleware = [*settings.MIDDLEWARE, "django.middleware.csrf.CsrfViewMiddleware"]
    with override_settings(MIDDLEWARE=middleware):
        cliente = Client(enforce_csrf_checks=True, HTTP_HOST=HOST)
        resposta = cliente.generic("POST", "/trilha/previa/arquivo/", b"conteudo",
                                   content_type="text/plain", HTTP_ORIGIN="https://meshcraft.top",
                                   HTTP_COOKIE="trilha_previa_csrf=opaco", HTTP_X_CSRFTOKEN="opaco")
        rejeitada = cliente.generic("POST", "/trilha/previa/arquivo/", b"conteudo",
                                    content_type="text/plain", HTTP_ORIGIN="https://outra.example")
    assert resposta.status_code == 200
    assert chamadas[0][2]["headers"]["X-CSRFToken"] == "opaco"
    assert chamadas[0][2]["headers"]["Cookie"] == "trilha_previa_csrf=opaco"
    assert rejeitada.status_code == 403
    assert len(chamadas) == 1


def test_caminho_preserva_arquivo_unicode_e_escapes_validos(rede, monkeypatch):
    monkeypatch.setattr(gateway, "_admin_real", lambda request: True)
    chamadas = _upstream(monkeypatch)
    resposta = _cliente().get("/trilha/previa/arquivos/Jo%C3%A3o%20Silva.png")
    assert resposta.status_code == 200
    assert chamadas[0][1] == "http://trilha-previa:8000/trilha/previa/arquivos/Jo%C3%A3o%20Silva.png"


def test_caminho_invalido_origem_externa_e_limites_fecham(rede, monkeypatch):
    monkeypatch.setattr(gateway, "_admin_real", lambda request: True)
    chamadas = _upstream(monkeypatch)
    cliente = _cliente()
    assert cliente.get("/trilha/previa/%252e%252e/secreto").status_code == 404
    assert cliente.generic("POST", "/trilha/previa/", b"x", content_type="text/plain",
                          HTTP_ORIGIN="https://outro.exemplo").status_code == 403
    assert cliente.generic("POST", "/trilha/previa/", b"x", content_type="text/plain",
                          CONTENT_LENGTH=str(gateway.LIMITE_ENTRADA + 1)).status_code == 413
    assert not chamadas


def test_falha_do_sidecar_e_redirecionamento_externo_fecham(rede, monkeypatch):
    monkeypatch.setattr(gateway, "_admin_real", lambda request: True)
    _upstream(monkeypatch, status=500)
    assert _cliente().get("/trilha/previa/").status_code == 503
    _upstream(monkeypatch, status=302, headers={"location": "https://fora.exemplo/"})
    assert _cliente().get("/trilha/previa/").status_code == 503


def test_resposta_acima_do_limite_nao_escapa(rede, monkeypatch):
    monkeypatch.setattr(gateway, "_admin_real", lambda request: True)
    monkeypatch.setattr(gateway, "LIMITE_SAIDA", 4)
    _upstream(monkeypatch, body=b"12345")
    resposta = _cliente().get("/trilha/previa/")
    assert resposta.status_code == 503
    assert resposta["Cache-Control"] == "private, no-store"


def test_rota_publica_da_trilha_continua_separada(rede, monkeypatch):
    chamadas = _upstream(monkeypatch)
    resposta = _cliente().get("/trilha/")
    assert resposta.status_code == 302
    assert not chamadas
