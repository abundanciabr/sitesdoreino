"""O bloco "Pronto para vender?", o interruptor da equipe comercial e o escopo
por quiz em `/admin/crm/agentes/`.

Cada linha do bloco diz `pronto`, `falta` ou `não consegui conferir`; uma fonte
fora do ar nunca derruba a página. O interruptor vive no banco e manda em
`coordenador.ligado()` sem reiniciar nada; o escopo manda nos eventos do quiz.
"""
import uuid
from decimal import Decimal

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.agentes import modelo, segredo
from apps.agentes.models import AutorizacaoDeGasto, Conexao
from apps.auditoria.models import Registro
from apps.comercial import coordenador, eventos, interruptor
from apps.comercial.models import ConfiguracaoComercial, TrabalhoComercial
from apps.core import crm_prontidao

IDENTIDADE = "http://identidade:8000/interno/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo"
QUIZ = "http://quiz:8000/interno/editor/quizzes"
CHECKOUT = "http://checkout:8000/api/checkout"
MENSAGERIA = "http://mensageria:8000/api/mensageria"
LEADS = "http://leads:8000/api/leads"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    settings.ADMIN_EMAILS = "dono@exemplo.com"
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "identidade-teste")
    monkeypatch.delenv("COMERCIAL_AGENTES", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.fixture
def fontes_ligadas(monkeypatch):
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "catalogo-teste")
    monkeypatch.setenv("QUIZ_API_URL", "http://quiz:8000")
    monkeypatch.setenv("QUIZ_API_TOKEN", "quiz-teste")
    monkeypatch.setenv("CHECKOUT_API_URL", CHECKOUT)
    monkeypatch.setenv("CHECKOUT_API_TOKEN", "checkout-teste")
    monkeypatch.setenv("MENSAGERIA_API_URL", MENSAGERIA)
    monkeypatch.setenv("MENSAGERIA_API_TOKEN", "mensageria-teste")
    monkeypatch.setenv("LEADS_API_URL", LEADS)
    monkeypatch.setenv("LEADS_API_TOKEN", "leads-teste")


def dentro(csrf=False):
    respx.get(IDENTIDADE).mock(
        return_value=httpx.Response(
            200, json={"autenticado": True, "id": "dono-id", "nome_exibido": "Dono", "email": "dono@exemplo.com", "papel": None}
        )
    )
    c = Client(enforce_csrf_checks=csrf)
    c.defaults["HTTP_COOKIE"] = "meshcraft_sessao=teste"
    return c


def _pagina(c=None):
    r = (c or dentro()).get(reverse("crm_agentes"))
    assert r.status_code == 200
    return r.content.decode()


def _linha(html, chave):
    """O texto da linha `pronto-<chave>` do bloco."""
    inicio = html.index(f'id="pronto-{chave}"')
    fim = html.index("</li>", inicio)
    return html[inicio:fim]


# ------------------------------------------------------------------- fontes

QUIZ_PRONTO = {
    "slug": "crivo", "title": "Crivo", "published": True, "directed": False, "versoes": ["original"], "ofertas": [],
    "faixas": [{"key": "alto", "titulo": "Alto", "pontos": "0 a 4", "destino": "/checkout/curso-a/", "rotulo": "Quero",
                "oferta_id": None, "divergente": False}],
}
QUIZ_SEM_OFERTA = {
    "slug": "sem-oferta", "title": "Sem oferta", "published": True, "directed": False, "versoes": ["original"],
    "ofertas": [],
    "faixas": [{"key": "unico", "titulo": "Único", "pontos": "0 a 4", "destino": "", "rotulo": "",
                "oferta_id": None, "divergente": False}],
}


def _site():
    respx.get(CATALOGO + "/sites/by-host/testserver").mock(
        return_value=httpx.Response(200, json={"id": "site-teste", "host": "testserver", "name": "Site", "menu": {}})
    )
    respx.get(f"{CATALOGO}/sites/site-teste/ofertas/curso-a").mock(
        return_value=httpx.Response(
            200,
            json={"site_id": "site-teste", "slug": "curso-a", "version": 1,
                  "product": {"id": "p1", "name": "Curso A"}, "price_cents": 19700, "bumps": []},
        )
    )


def _quizzes(*quizzes):
    respx.get(QUIZ + "/ofertas").mock(
        return_value=httpx.Response(200, json={"site_id": "site-teste", "items": list(quizzes)})
    )


def _condicoes(liberadas):
    respx.get(CHECKOUT + "/interno/condicoes-agente").mock(
        return_value=httpx.Response(
            200,
            json={"site_id": "site-teste", "ofertas": [
                {"oferta_ref": "curso-a", "disponivel": True, "itens": [], "liberadas_total": liberadas}]},
        )
    )


def _ambiente_do_checkout(modo="producao", cartao=None, pix=None):
    respx.get(CHECKOUT + "/interno/ambiente").mock(
        return_value=httpx.Response(200, json={"cartao": cartao or modo, "pix": pix or modo, "modo": modo})
    )


def _mensageria(conexao="open", oficial="ligado", modelo_ok=True, email=True, motivo=""):
    respx.get(MENSAGERIA + "/prontidao-comercial/site-teste").mock(
        return_value=httpx.Response(
            200,
            json={"email": {"respostas_recebidas": email},
                  "whatsapp": {"conexao": conexao, "canal_oficial": oficial,
                               "modelo_primeiro_contato": modelo_ok, "motivo": motivo}},
        )
    )


def _contatos(reais=2, todos=18):
    def responder(request):
        total = todos if request.url.params.get("testes") == "mostrar" else reais
        return httpx.Response(200, json={"itens": [], "pagina": 1, "por_pagina": 1, "total": total, "tem_mais": False})

    respx.get(LEADS + "/leads").mock(side_effect=responder)


def _modelo_conectado():
    conexao = modelo.conexao()
    conexao.segredo_cifrado = segredo.cifrar("sk-teste-1234")
    conexao.final_da_chave = "1234"
    conexao.situacao = Conexao.Situacao.CONFERIDA
    conexao.detalhe = "Chave aceita."
    conexao.save()


def _autorizar(teto="10.00"):
    AutorizacaoDeGasto.objects.all().delete()
    AutorizacaoDeGasto.objects.create(descricao="Robôs da equipe", destino="equipe", teto_mensal_usd=Decimal(teto), fonte="teste")


# -------------------------------------------------------------------- página


def _tudo_fora_do_ar():
    """O login continua valendo (registrado primeiro); todo o resto cai."""
    c = dentro()
    respx.route().mock(side_effect=httpx.ConnectError("fora do ar"))
    return c


@respx.mock
def test_com_todas_as_fontes_fora_do_ar_a_pagina_abre_e_cada_linha_diz_que_nao_conseguiu_conferir(fontes_ligadas):
    html = _pagina(_tudo_fora_do_ar())
    for chave in ("quizzes", "condicoes", "checkout", "whatsapp", "modelo_whatsapp", "email", "contatos"):
        assert "Não consegui conferir" in _linha(html, chave), chave
    assert "Ainda não." in html
    # O que mora no próprio admin continua respondendo (sem chave e sem autorização aqui).
    assert "Falta" in _linha(html, "modelo")


@respx.mock
def test_sem_configuracao_nenhuma_a_pagina_abre(monkeypatch):
    for nome in ("CATALOGO_API_URL", "QUIZ_API_URL", "CHECKOUT_API_URL", "MENSAGERIA_API_URL", "LEADS_API_URL"):
        monkeypatch.delenv(nome, raising=False)
    html = _pagina()
    assert "Pronto para vender?" in html
    assert "Não consegui conferir" in _linha(html, "checkout")


@respx.mock
def test_uma_linha_que_quebra_nao_derruba_as_outras(fontes_ligadas, monkeypatch):
    c = _tudo_fora_do_ar()

    def quebra(*a, **k):
        raise RuntimeError("bug na linha")

    monkeypatch.setattr(crm_prontidao, "_linha_modelo", quebra)
    AutorizacaoDeGasto.objects.all().delete()  # a migração semeia uma autorização
    html = _pagina(c)
    assert "Não consegui conferir esta parte agora." in _linha(html, "modelo")
    assert "Falta" in _linha(html, "gasto")


@respx.mock
def test_tudo_certo_diz_sim(fontes_ligadas):
    _site()
    _quizzes(QUIZ_PRONTO)
    _condicoes(2)
    _ambiente_do_checkout("producao")
    _mensageria()
    _contatos()
    _modelo_conectado()
    _autorizar()
    html = _pagina()
    assert "<b>Sim.</b> Os 9 itens abaixo estão prontos." in html
    for chave in ("quizzes", "condicoes", "checkout", "modelo", "gasto", "whatsapp", "modelo_whatsapp", "email", "contatos"):
        assert "Pronto</span>" in _linha(html, chave), chave
    assert "2 contatos reais e 16 de teste" in _linha(html, "contatos")


@respx.mock
def test_quiz_sem_oferta_diz_o_que_falta_e_leva_a_tela_certa(fontes_ligadas):
    _site()
    _quizzes(QUIZ_PRONTO, QUIZ_SEM_OFERTA)
    linha = _linha(_pagina(), "quizzes")
    assert "Falta" in linha and "1 de 2 quizzes publicados" in linha and "Sem oferta" in linha
    assert reverse("crm_ofertas_dos_quizzes") in linha
    assert "passa o lead para uma pessoa" in linha


@respx.mock
def test_sem_nenhum_quiz_publicado_falta(fontes_ligadas):
    _site()
    _quizzes(dict(QUIZ_PRONTO, published=False))
    linha = _linha(_pagina(), "quizzes")
    assert "Falta" in linha and "Nenhum quiz publicado" in linha


@respx.mock
def test_oferta_ligada_sem_condicao_liberada_falta(fontes_ligadas):
    _site()
    _quizzes(QUIZ_PRONTO)
    _condicoes(0)
    linha = _linha(_pagina(), "condicoes")
    assert "Falta" in linha and "Nenhuma condição liberada em: curso-a" in linha
    assert reverse("crm_condicoes") in linha


@respx.mock
def test_oferta_que_o_checkout_nunca_viu_tambem_falta(fontes_ligadas):
    _site()
    _quizzes(QUIZ_PRONTO)
    respx.get(CHECKOUT + "/interno/condicoes-agente").mock(
        return_value=httpx.Response(200, json={"site_id": "site-teste", "ofertas": []})
    )
    assert "Nenhuma condição liberada em: curso-a" in _linha(_pagina(), "condicoes")


@respx.mock
def test_checkout_em_teste_diz_que_nao_entra_dinheiro_real(fontes_ligadas):
    _ambiente_do_checkout("teste", cartao="producao", pix="teste")
    linha = _linha(_pagina(), "checkout")
    assert "Falta" in linha and "modo de teste" in linha
    assert "Cartão: produção; Pix: teste" in linha and "nenhum dinheiro real" in linha


@respx.mock
def test_checkout_em_producao_esta_pronto_e_a_tela_nunca_mostra_chave(fontes_ligadas):
    _ambiente_do_checkout("producao")
    html = _pagina()
    assert "Pronto" in _linha(html, "checkout") and "o dinheiro é real" in _linha(html, "checkout")


@respx.mock
def test_checkout_antigo_sem_a_rota_vira_nao_consegui_conferir(fontes_ligadas):
    respx.get(CHECKOUT + "/interno/ambiente").mock(return_value=httpx.Response(404))
    assert "Não consegui conferir" in _linha(_pagina(), "checkout")


@respx.mock
def test_modelo_sem_chave_recusado_e_sem_saldo(fontes_ligadas):
    linha = _linha(_pagina(), "modelo")
    assert "Falta" in linha and "Nenhuma chave do modelo guardada" in linha and reverse("robos_admin") in linha
    _modelo_conectado()
    conexao = modelo.conexao()
    conexao.situacao = Conexao.Situacao.RECUSADA
    conexao.save()
    assert "A conta recusou a chave" in _linha(_pagina(), "modelo")
    conexao.situacao = Conexao.Situacao.A_CONFERIR
    conexao.save()
    assert "Não consegui conferir" in _linha(_pagina(), "modelo")


@respx.mock
def test_autorizacao_de_gasto_ausente_ou_sem_saldo_falta():
    AutorizacaoDeGasto.objects.all().delete()
    assert "Nenhum limite de gasto autorizado" in _linha(_pagina(), "gasto")
    _autorizar("0.00")
    assert "Falta" in _linha(_pagina(), "gasto")
    _autorizar("10.00")
    linha = _linha(_pagina(), "gasto")
    assert "Pronto" in linha and "US$ 10.00" in linha


@respx.mock
def test_whatsapp_desconectado_e_sem_modelo_aprovado(fontes_ligadas):
    _site()
    _mensageria(conexao="nao_configurado", oficial="nao_ligado", modelo_ok=False, motivo="canal oficial ainda nao ligado")
    html = _pagina()
    assert "Nenhum número de WhatsApp configurado" in _linha(html, "whatsapp")
    assert reverse("whatsapp") in _linha(html, "whatsapp")
    linha = _linha(html, "modelo_whatsapp")
    assert "Falta" in linha and "canal oficial do WhatsApp ainda não está ligado" in linha and "cai para o e-mail" in linha
    assert reverse("crm_modelos") in linha


@respx.mock
def test_canal_oficial_ligado_mas_sem_modelo_aprovado(fontes_ligadas):
    _site()
    _mensageria(conexao="close", oficial="ligado", modelo_ok=False, motivo="nenhum modelo aprovado com nome iniciado por primeiro_contato")
    html = _pagina()
    assert "não conectado (estado: close)" in _linha(html, "whatsapp")
    assert "Nenhum modelo aprovado serve ao primeiro contato" in _linha(html, "modelo_whatsapp")


@respx.mock
def test_gateway_do_whatsapp_fora_do_ar_nao_consegui_conferir(fontes_ligadas):
    _site()
    _mensageria(conexao="indisponivel")
    assert "Não consegui conferir" in _linha(_pagina(), "whatsapp")


@respx.mock
def test_email_sem_token_de_entrada_falta_e_nunca_mostra_valor(fontes_ligadas):
    _site()
    _mensageria(email=False)
    linha = _linha(_pagina(), "email")
    assert "Falta" in linha and "token de entrada" in linha


@respx.mock
def test_sem_contato_real_falta(fontes_ligadas):
    _contatos(reais=0, todos=3)
    linha = _linha(_pagina(), "contatos")
    assert "Falta" in linha and "0 contatos reais e 3 de teste" in linha


@respx.mock
def test_escopo_vale_para_a_linha_dos_quizzes(fontes_ligadas):
    _site()
    _quizzes(QUIZ_PRONTO, QUIZ_SEM_OFERTA)
    interruptor.definir_escopo(["crivo"], "dono@exemplo.com")
    linha = _linha(_pagina(), "quizzes")
    assert "Pronto" in linha and "1 de 1 quiz publicado" in linha


# -------------------------------------------------------------- interruptor


def test_sem_linha_no_banco_vale_o_ambiente(monkeypatch):
    assert coordenador.ligado() is True
    monkeypatch.setenv("COMERCIAL_AGENTES", "desligado")
    assert coordenador.ligado() is False
    assert interruptor.origem() == "ambiente"


def test_o_interruptor_muda_ligado_sem_reiniciar(monkeypatch):
    monkeypatch.setenv("COMERCIAL_AGENTES", "desligado")
    assert coordenador.ligado() is False
    interruptor.definir_ligada(True, "dono")
    assert coordenador.ligado() is True  # a linha vale por cima do ambiente
    interruptor.definir_ligada(False, "dono")
    monkeypatch.delenv("COMERCIAL_AGENTES")
    assert coordenador.ligado() is False  # e também desliga com o ambiente liberado
    assert interruptor.origem() == "tela"


def test_linha_so_com_escopo_deixa_o_ambiente_mandar(monkeypatch):
    interruptor.definir_escopo(["crivo"], "dono")
    assert ConfiguracaoComercial.objects.get().ligada is None
    monkeypatch.setenv("COMERCIAL_AGENTES", "desligado")
    assert coordenador.ligado() is False
    monkeypatch.delenv("COMERCIAL_AGENTES")
    assert coordenador.ligado() is True


@respx.mock
def test_ligar_sem_confirmacao_nao_liga(monkeypatch):
    monkeypatch.setenv("COMERCIAL_AGENTES", "desligado")
    r = dentro().post(reverse("crm_agentes_interruptor"), {"acao": "ligar"})
    assert r.status_code == 302 and "recado=confirmar" in r["Location"]
    assert coordenador.ligado() is False
    assert not ConfiguracaoComercial.objects.exists()


@respx.mock
def test_ligar_confirmado_liga_registra_quem_e_audita(monkeypatch):
    monkeypatch.setenv("COMERCIAL_AGENTES", "desligado")
    r = dentro().post(reverse("crm_agentes_interruptor"), {"acao": "ligar", "confirmo": "sim"})
    assert r.status_code == 302 and "recado=ligada" in r["Location"]
    assert coordenador.ligado() is True
    linha = ConfiguracaoComercial.objects.get()
    assert linha.ligada is True and linha.ligada_por == "dono@exemplo.com" and linha.ligada_em is not None
    registro = Registro.objects.get(alvo="comercial:interruptor", detalhe__contains="ligada")
    assert "usa o modelo e fala com leads reais" in registro.detalhe


@respx.mock
def test_desligar_nao_pede_confirmacao_e_audita():
    interruptor.definir_ligada(True, "dono")
    r = dentro().post(reverse("crm_agentes_interruptor"), {"acao": "desligar"})
    assert r.status_code == 302 and "recado=desligada" in r["Location"]
    assert coordenador.ligado() is False
    assert Registro.objects.filter(alvo="comercial:interruptor", detalhe="CRM agentes: equipe comercial desligada").exists()


@respx.mock
def test_a_pagina_mostra_o_estado_o_botao_certo_e_a_frase_da_confirmacao(fontes_ligadas, monkeypatch):
    monkeypatch.setenv("COMERCIAL_AGENTES", "desligado")
    html = _pagina()
    assert "Equipe comercial: desligada" in html and "Desligado neste ambiente (COMERCIAL_AGENTES=desligado)" in html
    assert "passa a usar o modelo de IA" in html and "falar com leads reais" in html and "Ligar a equipe comercial" in html
    interruptor.definir_ligada(True, "dono@exemplo.com")
    html = _pagina()
    assert "Equipe comercial: ligada" in html and "Ligada por dono@exemplo.com" in html
    assert "Desligar a equipe comercial" in html and "Desligado neste ambiente" not in html


@respx.mock
def test_interruptor_exige_o_token_do_formulario_e_so_aceita_post():
    c = dentro(csrf=True)
    assert c.post(reverse("crm_agentes_interruptor"), {"acao": "ligar", "confirmo": "sim"}).status_code == 403
    assert dentro().get(reverse("crm_agentes_interruptor")).status_code == 405


@respx.mock
def test_visitante_nao_liga():
    r = Client().post(reverse("crm_agentes_interruptor"), {"acao": "ligar", "confirmo": "sim"})
    assert r.status_code in (302, 403)
    assert not ConfiguracaoComercial.objects.exists()


# ------------------------------------------------------------------- escopo


def _quiz_completado(slug, event_id=None, email="ana@exemplo.org"):
    data = {"site_id": "site-1", "quiz_slug": slug, "result_key": "iniciante",
            "lead": {"email": email, "name": "Ana Souza", "phone": "11999990000"},
            "submissao_id": f"sub-{slug}", "sessao": f"sess-{slug}", "respostas": []}
    return {"event": "quiz.completado", "version": 1, "event_id": event_id or str(uuid.uuid4()),
            "occurred_at": timezone.now().isoformat(), "data": data}


def test_sem_escopo_todos_os_quizzes_criam_trabalho():
    eventos.ao_quiz_completado(_quiz_completado("crivo"))
    eventos.ao_quiz_completado(_quiz_completado("outro", email="bia@exemplo.org"))
    assert TrabalhoComercial.objects.count() == 2


def test_escopo_so_deixa_passar_o_quiz_escolhido():
    interruptor.definir_escopo(["crivo"], "dono")
    fora = eventos.ao_quiz_completado(_quiz_completado("outro"))
    dentro_ = eventos.ao_quiz_completado(_quiz_completado("crivo", email="bia@exemplo.org"))
    assert fora is None and dentro_ is not None
    assert list(TrabalhoComercial.objects.values_list("entrada__quiz", flat=True)) == ["crivo"]


def test_escopo_vale_tambem_para_a_captura_parcial():
    interruptor.definir_escopo(["crivo"], "dono")
    envelope = _quiz_completado("outro")
    envelope["event"] = "quiz.captura_parcial"
    assert eventos.ao_quiz_captura_parcial(envelope) is None
    assert not TrabalhoComercial.objects.exists()


def test_escopo_vazio_volta_a_valer_para_todos():
    interruptor.definir_escopo(["crivo"], "dono")
    interruptor.definir_escopo([], "dono")
    assert interruptor.quiz_no_escopo("qualquer") is True


@respx.mock
def test_salvar_o_escopo_pela_tela_audita_e_aparece_marcado(fontes_ligadas):
    _site()
    _quizzes(QUIZ_PRONTO, QUIZ_SEM_OFERTA)
    c = dentro()
    r = c.post(reverse("crm_agentes_escopo"), {"quiz": ["crivo", "../../x", "crivo"]})
    assert r.status_code == 302 and "recado=escopo_salvo" in r["Location"]
    assert interruptor.escopo() == ["crivo"]  # o que não parece slug é descartado; repetido vira um
    assert Registro.objects.filter(alvo="comercial:escopo", detalhe__contains="crivo").exists()
    html = _pagina(c)
    assert "Hoje: só crivo." in html
    assert 'value="crivo" checked' in html and 'value="sem-oferta" checked' not in html
    r = c.post(reverse("crm_agentes_escopo"), {})
    assert "recado=escopo_todos" in r["Location"] and interruptor.escopo() == []


@respx.mock
def test_escopo_escolhido_antes_nao_some_quando_os_quizzes_nao_respondem(fontes_ligadas):
    c = _tudo_fora_do_ar()
    interruptor.definir_escopo(["crivo"], "dono")
    html = _pagina(c)
    assert "Não consegui consultar os quizzes agora" in html
    assert 'value="crivo" checked' in html
