"""A tela das ofertas dos quizzes: lê e grava só pela célula do quiz."""

import json

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro

IDENTIDADE = "http://identidade:8000/interno/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo"
QUIZ = "http://quiz:8000/interno/editor/quizzes"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    settings.ADMIN_EMAILS = "dono@exemplo.com"
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "identidade-teste")
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "catalogo-teste")
    monkeypatch.setenv("QUIZ_API_URL", "http://quiz:8000")
    monkeypatch.setenv("QUIZ_API_TOKEN", "quiz-teste")


def _cliente(csrf=False):
    respx.get(IDENTIDADE).mock(return_value=httpx.Response(200, json={
        "autenticado": True, "id": "dono-id", "nome_exibido": "Dono",
        "papel": None, "email": "dono@exemplo.com"}))
    respx.get(CATALOGO + "/sites/by-host/testserver").mock(return_value=httpx.Response(
        200, json={"id": "site-teste", "host": "testserver", "name": "Site Teste", "menu": {}}))
    cliente = Client(enforce_csrf_checks=csrf)
    cliente.defaults["HTTP_COOKIE"] = "meshcraft_sessao=teste"
    return cliente


def _oferta(slug, nome, centavos):
    return respx.get(f"{CATALOGO}/sites/site-teste/ofertas/{slug}").mock(
        return_value=httpx.Response(200, json={
            "site_id": "site-teste", "slug": slug, "version": 1,
            "product": {"id": "p1", "name": nome}, "price_cents": centavos, "bumps": []}))


def _faixa(chave, titulo, destino="", rotulo="", **extra):
    return {"key": chave, "titulo": titulo, "pontos": "0 a 4", "destino": destino,
            "rotulo": rotulo, "oferta_id": None, "divergente": False, **extra}


def _quiz(slug="crivo", faixas=None, **extra):
    return {"slug": slug, "title": "Crivo", "published": True, "directed": False,
            "versoes": ["original"], "ofertas": [], "faixas": faixas if faixas is not None else [], **extra}


def _lista(*quizzes):
    return respx.get(QUIZ + "/ofertas").mock(return_value=httpx.Response(
        200, json={"site_id": "site-teste", "items": list(quizzes)}))


@respx.mock
def test_mostra_cada_resultado_com_a_oferta_e_destaca_o_que_nao_tem():
    rota = _lista(
        _quiz(faixas=[_faixa("alto", "Alto", "/checkout/curso-a/", "Quero"), _faixa("baixo", "Baixo")]),
        _quiz("completo", [_faixa("unico", "Único", "/checkout/curso-a/", "Ir")]),
    )
    _oferta("curso-a", "Curso A", 19700)
    resposta = _cliente().get(reverse("crm_ofertas_dos_quizzes"))
    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert "Curso A" in html and "R$ 197,00" in html
    assert "Sem oferta: o resultado termina sem botão." in html
    assert "1 resultado sem oferta" in html
    # só o quiz com resultado sem oferta pede atenção
    assert html.count('class="ofq-quiz atencao"') == 1
    assert rota.calls.last.request.url.params["site_id"] == "site-teste"
    assert rota.calls.last.request.headers["Authorization"] == "Bearer quiz-teste"


@respx.mock
def test_oferta_que_nao_existe_no_catalogo_aparece_como_problema():
    _lista(_quiz(faixas=[_faixa("alto", "Alto", "/checkout/fantasma/", "Ir")]))
    respx.get(f"{CATALOGO}/sites/site-teste/ofertas/fantasma").mock(return_value=httpx.Response(404))
    html = _cliente().get(reverse("crm_ofertas_dos_quizzes")).content.decode()
    assert "não existe neste site" in html and "Oferta que não existe" in html


@respx.mock
def test_catalogo_fora_do_ar_nao_inventa_nome_nem_preco():
    _lista(_quiz(faixas=[_faixa("alto", "Alto", "/checkout/curso-a/", "Ir")]))
    respx.get(f"{CATALOGO}/sites/site-teste/ofertas/curso-a").mock(return_value=httpx.Response(503))
    resposta = _cliente().get(reverse("crm_ofertas_dos_quizzes"))
    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert "Não consegui conferir o nome e o preço" in html and "R$" not in html


@respx.mock
def test_endereco_fora_da_plataforma_e_campanha_aparecem_em_palavras():
    campanha = _quiz("campanha", [
        _faixa("inicio", "Início", "https://pay.exemplo.com/a", "Começar", oferta_id="curso-inicial"),
        _faixa("avanco", "Avanço", "", "", oferta_id="curso-avancado"),
    ], directed=True, ofertas=[
        {"id": "curso-inicial", "nome": "Inicial", "checkout_url": "https://pay.exemplo.com/a"},
        {"id": "curso-avancado", "nome": "Avançado", "checkout_url": ""}])
    _lista(campanha)
    html = _cliente().get(reverse("crm_ofertas_dos_quizzes")).content.decode()
    assert "Endereço fora da plataforma" in html and "https://pay.exemplo.com/a" in html
    assert "Campanha com duas ofertas" in html and 'name="oferta_curso-avancado"' in html
    assert "1 resultado sem oferta" in html


@respx.mock
def test_quiz_fora_do_ar_diz_isso_e_nao_mostra_zero():
    respx.get(QUIZ + "/ofertas").mock(return_value=httpx.Response(503))
    resposta = _cliente().get(reverse("crm_ofertas_dos_quizzes"))
    assert resposta.status_code == 503
    html = resposta.content.decode()
    assert "Não consegui consultar os quizzes" in html and "Quizzes neste site" not in html


@respx.mock
def test_sem_ligar_o_quiz_nao_abre_para_quem_nao_e_equipe(settings):
    respx.get(IDENTIDADE).mock(return_value=httpx.Response(200, json={"autenticado": False}))
    resposta = Client().get(reverse("crm_ofertas_dos_quizzes"))
    assert resposta.status_code in (302, 401, 403, 404)


@respx.mock
def test_salvar_manda_a_ligacao_pela_api_do_quiz_com_apelido_virando_checkout():
    _lista(_quiz(faixas=[_faixa("baixo", "Baixo"), _faixa("alto", "Alto")]))
    _oferta("curso-a", "Curso A", 19700)
    quiz = respx.get(QUIZ + "/crivo/ofertas").mock(return_value=httpx.Response(200, json=_quiz(
        faixas=[_faixa("baixo", "Baixo"), _faixa("alto", "Alto")])))
    put = respx.put(QUIZ + "/crivo/ofertas").mock(return_value=httpx.Response(200, json=_quiz()))
    resposta = _cliente().post(reverse("crm_ofertas_dos_quizzes_salvar", args=["crivo"]), {
        "chave_0": "baixo", "destino_0": "", "rotulo_0": "",
        "chave_1": "alto", "destino_1": "curso-a", "rotulo_1": ""})
    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("crm_ofertas_dos_quizzes") + "?salvo=crivo"
    assert json.loads(put.calls.last.request.content) == {"faixas": [
        {"key": "baixo", "destino": "", "rotulo": ""},
        {"key": "alto", "destino": "/checkout/curso-a/", "rotulo": "Quero saber mais"},
    ]}
    assert put.calls.last.request.url.params["site_id"] == "site-teste"
    assert quiz.called
    registro = Registro.objects.get(alvo="crivo")
    assert registro.desfecho == Registro.OK and registro.quem_email == "dono@exemplo.com"


@respx.mock
def test_salvar_recusa_oferta_que_o_catalogo_diz_que_nao_existe_e_nao_grava():
    _lista(_quiz(faixas=[_faixa("alto", "Alto")]))
    respx.get(QUIZ + "/crivo/ofertas").mock(return_value=httpx.Response(200, json=_quiz(faixas=[_faixa("alto", "Alto")])))
    respx.get(f"{CATALOGO}/sites/site-teste/ofertas/fantasma").mock(return_value=httpx.Response(404))
    put = respx.put(QUIZ + "/crivo/ofertas").mock(return_value=httpx.Response(200, json=_quiz()))
    resposta = _cliente().post(reverse("crm_ofertas_dos_quizzes_salvar", args=["crivo"]), {
        "chave_0": "alto", "destino_0": "fantasma", "rotulo_0": "Ir"})
    assert resposta.status_code == 422
    html = resposta.content.decode()
    assert "não existe neste site" in html and 'value="fantasma"' in html
    assert not put.called


@respx.mock
def test_salvar_texto_de_botao_sem_oferta_pede_a_oferta():
    _lista(_quiz(faixas=[_faixa("alto", "Alto")]))
    respx.get(QUIZ + "/crivo/ofertas").mock(return_value=httpx.Response(200, json=_quiz(faixas=[_faixa("alto", "Alto")])))
    put = respx.put(QUIZ + "/crivo/ofertas").mock(return_value=httpx.Response(200, json=_quiz()))
    resposta = _cliente().post(reverse("crm_ofertas_dos_quizzes_salvar", args=["crivo"]), {
        "chave_0": "alto", "destino_0": "", "rotulo_0": "Ir"})
    assert resposta.status_code == 422 and "falta a oferta" in resposta.content.decode()
    assert not put.called


@respx.mock
def test_recusa_da_celula_do_quiz_volta_em_portugues_com_o_que_foi_digitado():
    _lista(_quiz(faixas=[_faixa("alto", "Alto")]))
    respx.get(QUIZ + "/crivo/ofertas").mock(return_value=httpx.Response(200, json=_quiz(faixas=[_faixa("alto", "Alto")])))
    respx.put(QUIZ + "/crivo/ofertas").mock(return_value=httpx.Response(
        422, json={"detail": "Destino do botão deve ser caminho local ou URL HTTP(S)."}))
    resposta = _cliente().post(reverse("crm_ofertas_dos_quizzes_salvar", args=["crivo"]), {
        "chave_0": "alto", "destino_0": "javascript:x", "rotulo_0": "Ir"})
    html = resposta.content.decode()
    assert resposta.status_code == 422
    assert "Destino do botão deve ser caminho local" in html and 'value="javascript:x"' in html
    assert Registro.objects.get(alvo="crivo").desfecho == Registro.RECUSADO_PELA_CELULA


@respx.mock
def test_quiz_que_nao_responde_ao_salvar_nao_diz_que_salvou():
    _lista(_quiz(faixas=[_faixa("alto", "Alto")]))
    respx.get(QUIZ + "/crivo/ofertas").mock(return_value=httpx.Response(200, json=_quiz(faixas=[_faixa("alto", "Alto")])))
    _oferta("x-y", "X", 1000)
    respx.put(QUIZ + "/crivo/ofertas").mock(return_value=httpx.Response(503))
    resposta = _cliente().post(reverse("crm_ofertas_dos_quizzes_salvar", args=["crivo"]), {
        "chave_0": "alto", "destino_0": "/checkout/x-y/", "rotulo_0": "Ir"})
    assert resposta.status_code == 503
    assert "Não consegui confirmar que a alteração foi salva" in resposta.content.decode()


@respx.mock
def test_quiz_inexistente_e_404():
    respx.get(QUIZ + "/nada/ofertas").mock(return_value=httpx.Response(404, json={"detail": "Quiz não encontrado."}))
    resposta = _cliente().post(reverse("crm_ofertas_dos_quizzes_salvar", args=["nada"]), {})
    assert resposta.status_code == 404


@respx.mock
def test_campanha_manda_os_dois_enderecos_e_exige_os_dois():
    campanha = _quiz("campanha", [_faixa("inicio", "Início", oferta_id="curso-inicial")], directed=True, ofertas=[
        {"id": "curso-inicial", "nome": "Inicial", "checkout_url": ""},
        {"id": "curso-avancado", "nome": "Avançado", "checkout_url": ""}])
    _lista(campanha)
    respx.get(QUIZ + "/campanha/ofertas").mock(return_value=httpx.Response(200, json=campanha))
    put = respx.put(QUIZ + "/campanha/ofertas").mock(return_value=httpx.Response(200, json=campanha))
    url = reverse("crm_ofertas_dos_quizzes_salvar", args=["campanha"])
    faltando = _cliente().post(url, {"oferta_curso-inicial": "https://pay.exemplo.com/a", "oferta_curso-avancado": ""})
    assert faltando.status_code == 422 and not put.called
    ok = _cliente().post(url, {"oferta_curso-inicial": "https://pay.exemplo.com/a", "oferta_curso-avancado": "https://pay.exemplo.com/b"})
    assert ok.status_code == 302
    assert json.loads(put.calls.last.request.content) == {"ofertas": {
        "curso-inicial": "https://pay.exemplo.com/a", "curso-avancado": "https://pay.exemplo.com/b"}}


@respx.mock
def test_salvar_exige_csrf():
    _lista(_quiz())
    resposta = _cliente(csrf=True).post(reverse("crm_ofertas_dos_quizzes_salvar", args=["crivo"]), {})
    assert resposta.status_code == 403


@respx.mock
def test_crm_aponta_para_a_tela():
    respx.get("http://leads:8000/api/leads/crm").mock(return_value=httpx.Response(503))
    html = _cliente().get(reverse("crm")).content.decode()
    assert reverse("crm_ofertas_dos_quizzes") in html


@respx.mock
def test_formulario_velho_grava_na_faixa_certa_e_nao_esvazia_a_nova():
    # A tela abriu com [baixo, alto]; depois o quiz ganhou "novo" no meio.
    atual = _quiz(faixas=[_faixa("baixo", "Baixo", "/checkout/x/", "Ir"), _faixa("novo", "Novo"),
                          _faixa("alto", "Alto", "/checkout/y/", "Ir")])
    respx.get(QUIZ + "/crivo/ofertas").mock(return_value=httpx.Response(200, json=atual))
    _oferta("curso-a", "Curso A", 19700)
    _oferta("x", "X", 1000)
    put = respx.put(QUIZ + "/crivo/ofertas").mock(return_value=httpx.Response(200, json=atual))
    resposta = _cliente().post(reverse("crm_ofertas_dos_quizzes_salvar", args=["crivo"]), {
        "chave_0": "baixo", "destino_0": "/checkout/x/", "rotulo_0": "Ir",
        "chave_1": "alto", "destino_1": "curso-a", "rotulo_1": "Ir"})
    assert resposta.status_code == 302
    assert json.loads(put.calls.last.request.content) == {"faixas": [
        {"key": "baixo", "destino": "/checkout/x/", "rotulo": "Ir"},
        {"key": "alto", "destino": "/checkout/curso-a/", "rotulo": "Ir"},
    ]}


@respx.mock
def test_formulario_sem_nenhuma_faixa_conhecida_nao_grava_nada():
    atual = _quiz(faixas=[_faixa("novo", "Novo", "/checkout/x/", "Ir")])
    respx.get(QUIZ + "/crivo/ofertas").mock(return_value=httpx.Response(200, json=atual))
    _lista(atual)
    _oferta("x", "X", 1000)
    put = respx.put(QUIZ + "/crivo/ofertas").mock(return_value=httpx.Response(200, json=atual))
    resposta = _cliente().post(reverse("crm_ofertas_dos_quizzes_salvar", args=["crivo"]), {
        "chave_0": "velho", "destino_0": "", "rotulo_0": ""})
    assert resposta.status_code == 422 and "mudou desde que a tela abriu" in resposta.content.decode()
    assert not put.called


@respx.mock
def test_externo_com_caminho_de_checkout_nao_vira_oferta_da_casa():
    _lista(_quiz(faixas=[_faixa("a", "A", "https://outro-site.com/checkout/curso-a/", "Ir"),
                         _faixa("b", "B", "http://testserver/checkout/curso-a/", "Ir")]))
    _oferta("curso-a", "Curso A", 19700)
    html = _cliente().get(reverse("crm_ofertas_dos_quizzes")).content.decode()
    assert html.count("Endereço fora da plataforma") == 1
    assert html.count("Curso A") == 1


@respx.mock
def test_salvar_endereco_externo_com_apelido_inexistente_nao_e_barrado():
    atual = _quiz(faixas=[_faixa("a", "A")])
    respx.get(QUIZ + "/crivo/ofertas").mock(return_value=httpx.Response(200, json=atual))
    respx.get(f"{CATALOGO}/sites/site-teste/ofertas/fantasma").mock(return_value=httpx.Response(404))
    put = respx.put(QUIZ + "/crivo/ofertas").mock(return_value=httpx.Response(200, json=atual))
    resposta = _cliente().post(reverse("crm_ofertas_dos_quizzes_salvar", args=["crivo"]), {
        "chave_0": "a", "destino_0": "https://outro-site.com/checkout/fantasma/", "rotulo_0": "Ir"})
    assert resposta.status_code == 302 and put.called
