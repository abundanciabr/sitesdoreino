"""O conhecimento comercial dos agentes (`apps/agentes/conhecimento_comercial.py`).

As outras células (catálogo e cursos) são de mentira, com `respx`, na forma
dos contratos delas. Os testes provam: o que entra no índice e o que fica de
fora (preço, rascunho, depoimento sem autorização), que um site não enxerga
o outro, que preço vem ao vivo, que só o que mudou é regravado, e a
ferramenta, a tela e o comando.
"""

from __future__ import annotations

import json
from io import StringIO

import httpx
import pytest
import respx
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from apps.agentes import conhecimento, conhecimento_comercial as cc, ferramentas, trabalhos
from apps.agentes.models import (
    ChamadaDeFerramenta,
    Execucao,
    FonteDoConhecimento,
    LigacaoDoConhecimento,
    MaterialComercial,
    TrechoComercial,
)
from apps.core.models import Documento, MembroDaEquipe

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo"
CURSOS = "http://cursos:8000/api/cursos"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
LIVIA = "livia-conta-de-teste@exemplo.com"

SITE_A = {"id": "site-a", "host": "a.test", "name": "Site A", "active": True, "default_offer_slug": "anual"}
SITE_B = {"id": "site-b", "host": "b.test", "name": "Site B", "active": True, "default_offer_slug": "mensal"}
PRODUTOS = [
    {"id": "prod-blender", "name": "Escola de Blender", "price_cents": 0, "active": True},
    {"id": "prod-zbrush", "name": "Escultura no ZBrush", "price_cents": 0, "active": True},
]


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-do-par-admin-catalogo")
    monkeypatch.setenv("CURSOS_API_URL", CURSOS)
    monkeypatch.setenv("CURSOS_API_TOKEN", "token-do-par-admin-cursos")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CONHECIMENTO_COMERCIAL_HOSTS", raising=False)
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _aula(numero, titulo, letra, nome_do_bloco, estado="publicada", parte=1, ordem=1):
    return {
        "numero": numero,
        "ordem": ordem,
        "titulo_exibido": titulo,
        "bloco": {"letra": letra, "ordem": ord(letra) - 64, "parte": parte, "nome": nome_do_bloco, "boss_titulo": ""},
        "estado": estado,
        "versao": 1,
        "publicada_em": "2026-09-20T10:00:00Z" if estado == "publicada" else None,
        "e_boss": False,
        "banca_nivel": None,
    }


def _curso(slug, nome, produto_id, estado="publicado", progressao="livre"):
    return {
        "slug": slug, "nome": nome, "estado": estado, "progressao": progressao,
        "produto_id": produto_id, "total_de_aulas": 3, "aulas_publicadas": 2,
    }


def _pagina(slug_da_oferta, tempo="Seis meses de acesso, com duas horas por semana."):
    return {
        "id": 1, "site_id": "x", "slug": "oferta", "tipo": "oferta", "version": 3,
        "offer_slug": slug_da_oferta, "published_at": "2026-09-30T12:00:00Z",
        "secoes": [
            {"nome": "cubo", "slots": {"headline": "Aprenda Blender do zero", "cta_texto": "Quero entrar"}},
            {"nome": "tempo", "slots": {"headline": "Quanto tempo leva", "texto": tempo}},
            {"nome": "para_quem_nao_serve", "slots": {"recusa_1": "Quem não tem um computador com placa de vídeo."}},
            {"nome": "oferta", "slots": {
                "o_que_recebe": "Acesso às aulas e correção das entregas. Tudo por R$ 497 à vista.",
                "preco_texto": "R$ 497,00", "parcelamento": "ou 12x de R$ 49,70",
            }},
        ],
    }


def _oferta(site_id, slug, produto, preco=49700):
    return {
        "site_id": site_id, "slug": slug, "version": 2,
        "product": {"id": produto["id"], "name": produto["name"]},
        "price_cents": preco,
        "bumps": [{"id": "b1", "product_id": "p2", "name": "Pacote de texturas", "price_cents": 9700,
                   "headline": "Texturas prontas para os exercícios."}],
    }


def _catalogo(*, cursos_a=None, cursos_b=None, cursos_status=200, preco_status=200):
    """O catálogo e a sala de aula de mentira, com dois sites."""
    cursos_a = [_curso("blender", "Blender Essencial", "prod-blender"),
                _curso("rascunho", "Curso Secreto", "prod-blender", estado="rascunho")] if cursos_a is None else cursos_a
    cursos_b = [_curso("zbrush", "ZBrush Avançado", "prod-zbrush")] if cursos_b is None else cursos_b
    for site in (SITE_A, SITE_B):
        respx.get(f"{CATALOGO}/sites/by-host/{site['host']}").mock(return_value=httpx.Response(200, json=site))
    respx.get(f"{CATALOGO}/produtos").mock(return_value=httpx.Response(200, json=PRODUTOS))
    respx.get(f"{CURSOS}/cursos", params={"site_id": "site-a"}).mock(
        return_value=httpx.Response(cursos_status, json=cursos_a))
    respx.get(f"{CURSOS}/cursos", params={"site_id": "site-b"}).mock(
        return_value=httpx.Response(200, json=cursos_b))
    respx.get(f"{CURSOS}/cursos/blender/aulas", params={"site_id": "site-a"}).mock(
        return_value=httpx.Response(200, json=[
            _aula("01", "Interface e navegação", "A", "Primeiros passos"),
            _aula("02", "Modelagem de uma caneca", "A", "Primeiros passos", ordem=2),
            _aula("03", "Aula ainda não lançada", "B", "Materiais", estado="rascunho", ordem=3),
        ]))
    respx.get(f"{CURSOS}/cursos/zbrush/aulas", params={"site_id": "site-b"}).mock(
        return_value=httpx.Response(200, json=[_aula("01", "Escultura de rosto", "A", "Anatomia")]))
    respx.get(f"{CATALOGO}/sites/site-a/paginas/oferta").mock(return_value=httpx.Response(200, json=_pagina("anual")))
    respx.get(f"{CATALOGO}/sites/site-b/paginas/oferta").mock(
        return_value=httpx.Response(200, json=_pagina("mensal", tempo="Três meses de acesso ao ZBrush.")))
    respx.get(f"{CATALOGO}/sites/site-a/ofertas/anual").mock(
        return_value=httpx.Response(preco_status, json=_oferta("site-a", "anual", PRODUTOS[0])))
    respx.get(f"{CATALOGO}/sites/site-b/ofertas/mensal").mock(
        return_value=httpx.Response(200, json=_oferta("site-b", "mensal", PRODUTOS[1], preco=19700)))


def _documento(nome, corpo, publico=True, titulo=None):
    return Documento.objects.create(nome=nome, titulo=titulo or nome.replace("-", " ").title(), corpo=corpo, publico=publico)


@respx.mock
def test_indexa_cursos_e_oferta_sem_preco_nem_rascunho():
    _catalogo()
    relatorio = cc.atualizar_host("a.test")
    assert relatorio["faltou"] == []
    assert relatorio["novas"] == 2  # o curso publicado e a oferta

    trechos = TrechoComercial.objects.filter(site_id="site-a")
    textos = " ".join(t.texto for t in trechos)
    assert "Blender Essencial" in textos and "Primeiros passos" in textos
    assert "Interface e navegação" in textos
    # Rascunho e aula não lançada ficam fora; preço e parcelas também.
    assert "Curso Secreto" not in textos and "ainda não lançada" not in textos
    assert "497" not in textos and "49,70" not in textos and "12x" not in textos
    assert "(preço e condições: consultar ao vivo)" in textos
    assert "Pacote de texturas" in textos and "9700" not in textos
    assert not TrechoComercial.objects.filter(site_id="site-b").exists()

    curso = trechos.filter(tipo="curso").first()
    assert curso.produto_ref == "prod-blender" and curso.produto_nome == "Escola de Blender"
    assert "a próxima aula abre quando o aluno conclui a anterior" in textos
    assert curso.vigente_desde.date().isoformat() == "2026-09-20"
    assert FonteDoConhecimento.objects.filter(chave="comercial:site-a:curso:blender").exists()

    # O catálogo entra no mapa da equipe como coisas e ligações, sem modelo nenhum.
    achado = conhecimento.consultar(["Blender Essencial"], com_privados=True)
    relacoes = {(l["de"], l["relacao"], l["para"]) for l in achado["ligacoes"]}
    assert ("Blender Essencial (a.test)", "faz parte do produto", "Escola de Blender") in relacoes
    assert ("Oferta anual (a.test)", "vende", "Escola de Blender") in relacoes
    assert ("Blender Essencial (a.test)", "tem módulo", "Primeiros passos (Blender Essencial, a.test)") in relacoes
    assert conhecimento.numeros()["comerciais"] == 2
    assert conhecimento.numeros()["documentos"] == 0


@respx.mock
def test_a_consulta_traz_trecho_com_fonte_e_vigencia():
    _catalogo()
    cc.atualizar_host("a.test")
    resposta = cc.consultar("a.test", "Quanto tempo dura o curso?")
    assert resposta["achou"] is True and resposta["site"] == {"id": "site-a", "host": "a.test"}
    primeiro = resposta["trechos"][0]
    assert primeiro["titulo"] == "Tempo e duração"
    assert "Seis meses" in primeiro["texto"]
    assert primeiro["fonte"]["tipo"] == "oferta" and primeiro["fonte"]["id"] == "anual"
    assert primeiro["vigencia"]["desde"] == "2026-09-30"
    assert primeiro["ao_vivo"] is False
    assert resposta["fatos_ao_vivo"] == []

    requisitos = cc.consultar("site-a", "Quais os requisitos? Preciso de computador?")
    assert "placa de vídeo" in requisitos["trechos"][0]["texto"]
    modulos = cc.consultar("site-a", "quais módulos tem?", "blender")
    assert modulos["trechos"][0]["fonte"] == {
        "tipo": "curso", "id": "blender", "titulo": "Curso Blender Essencial",
        "endereco": "https://a.test/cursos/blender/",
    }


@respx.mock
def test_um_site_nao_enxerga_o_outro():
    _catalogo()
    cc.atualizar_host("a.test")
    cc.atualizar_host("b.test")
    zbrush_em_a = cc.consultar("a.test", "ZBrush escultura anatomia")
    assert zbrush_em_a["achou"] is False
    assert all(t["fonte"]["id"] != "zbrush" for t in zbrush_em_a["trechos"])
    tempo_em_b = cc.consultar("b.test", "quanto tempo de acesso?")
    assert "Três meses" in tempo_em_b["trechos"][0]["texto"]
    assert all("Seis meses" not in t["texto"] for t in tempo_em_b["trechos"])
    # Pedir em B o produto de A não traz nada de A.
    cruzado = cc.consultar("b.test", "módulos", "Escola de Blender")
    assert "aviso" in cruzado
    assert all(t["produto"] is None or t["produto"]["ref"] != "prod-blender" for t in cruzado["trechos"])
    # Site que ninguém indexou: nada, e o aviso para não inventar.
    respx.get(f"{CATALOGO}/sites/by-host/c.test").mock(return_value=httpx.Response(404))
    assert cc.consultar("c.test", "tempo")["achou"] is False


@respx.mock
def test_preco_vem_ao_vivo_e_nunca_da_memoria():
    _catalogo()
    cc.atualizar_host("a.test")
    resposta = cc.consultar("a.test", "Qual o preço? Dá para parcelar?")
    assert all("497" not in t["texto"] for t in resposta["trechos"])
    precos = [f for f in resposta["fatos_ao_vivo"] if f.get("fonte", {}).get("tipo") == "oferta"]
    assert precos[0]["ao_vivo"] is True
    assert "R$ 497,00" in precos[0]["texto"]
    assert "consultado_em" in precos[0]["vigencia"]
    assert any(f["fonte"]["tipo"] == "checkout" for f in resposta["fatos_ao_vivo"])


@respx.mock
def test_sem_catalogo_o_preco_ao_vivo_vira_capacidade_indisponivel():
    _catalogo()
    cc.atualizar_host("a.test")
    respx.get(f"{CATALOGO}/sites/site-a/ofertas/anual").mock(return_value=httpx.Response(503))
    resposta = cc.consultar("a.test", "quanto custa?")
    indisponivel = [f for f in resposta["fatos_ao_vivo"] if f.get("capacidade_indisponivel")]
    assert indisponivel and indisponivel[0]["capacidade"] == "preco_ao_vivo"


@respx.mock
def test_materiais_e_depoimentos_marcados():
    _catalogo()
    _documento("guia-de-vendas", "O curso tem correção humana das entregas.\n\nPor apenas R$ 97 em 12x sem juros.",
               publico=False, titulo="Guia de vendas")
    _documento("depoimento-ana", "A Ana conseguiu o primeiro cliente depois do módulo de caneca.", titulo="Ana")
    _documento("depoimento-bia", "A Bia não autorizou o uso.", titulo="Bia")
    _documento("so-de-b", "Material que é só do site B: correção semanal.")
    MaterialComercial.objects.create(documento_nome="guia-de-vendas", site_id="site-a", site_host="a.test",
                                     tipo="material", produto="Escola de Blender")
    MaterialComercial.objects.create(documento_nome="depoimento-ana", site_id="site-a", site_host="a.test",
                                     tipo="depoimento", utilizavel=True)
    MaterialComercial.objects.create(documento_nome="depoimento-bia", site_id="site-a", site_host="a.test",
                                     tipo="depoimento", utilizavel=False)
    MaterialComercial.objects.create(documento_nome="so-de-b", site_id="site-b", site_host="b.test", tipo="material")
    cc.atualizar_host("a.test")

    tipos = set(TrechoComercial.objects.filter(site_id="site-a").values_list("tipo", "ref"))
    assert ("documento", "guia-de-vendas") in tipos and ("depoimento", "depoimento-ana") in tipos
    assert ("depoimento", "depoimento-bia") not in tipos
    guia = TrechoComercial.objects.get(ref="guia-de-vendas")
    assert "R$ 97" not in guia.texto and "correção humana" in guia.texto
    assert guia.produto_ref == "prod-blender" and guia.publico is False

    correcao = cc.consultar("a.test", "tem correção?")
    assert {t["fonte"]["id"] for t in correcao["trechos"]} >= {"guia-de-vendas"}
    assert all(t["fonte"]["id"] != "so-de-b" for t in correcao["trechos"])
    # Quem não administra o site não recebe documento interno.
    publica = cc.consultar("a.test", "tem correção?", com_privados=False)
    assert all(t["fonte"]["id"] != "guia-de-vendas" for t in publica["trechos"])
    depoimento = cc.consultar("a.test", "algum depoimento de cliente?")
    assert depoimento["trechos"][0]["fonte"]["tipo"] == "depoimento"

    # Documento arquivado sai do índice na próxima volta.
    Documento.objects.filter(nome="depoimento-ana").update(arquivado=True)
    relatorio = cc.atualizar_host("a.test")
    assert relatorio["sairam"] == 1
    assert not TrechoComercial.objects.filter(ref="depoimento-ana").exists()


@respx.mock
def test_so_regrava_o_que_mudou_e_tira_o_que_saiu():
    _catalogo()
    cc.atualizar_host("a.test")
    ids = set(TrechoComercial.objects.values_list("id", flat=True))
    segunda = cc.atualizar_host("a.test")
    assert (segunda["novas"], segunda["mudadas"], segunda["iguais"], segunda["sairam"]) == (0, 0, 2, 0)
    assert set(TrechoComercial.objects.values_list("id", flat=True)) == ids

    # A sala de aula fora do ar: o que já se sabia dos cursos continua.
    respx.get(f"{CURSOS}/cursos", params={"site_id": "site-a"}).mock(return_value=httpx.Response(500))
    caiu = cc.atualizar_host("a.test")
    assert caiu["faltou"] and caiu["sairam"] == 0
    assert TrechoComercial.objects.filter(site_id="site-a", tipo="curso").exists()

    # O curso mudou de nome: só ele é regravado. Depois saiu: sai do índice.
    respx.get(f"{CURSOS}/cursos", params={"site_id": "site-a"}).mock(
        return_value=httpx.Response(200, json=[_curso("blender", "Blender do Zero", "prod-blender")]))
    mudou = cc.atualizar_host("a.test")
    assert (mudou["mudadas"], mudou["iguais"]) == (1, 1)
    assert "Blender do Zero" in TrechoComercial.objects.filter(tipo="curso").first().texto
    respx.get(f"{CURSOS}/cursos", params={"site_id": "site-a"}).mock(return_value=httpx.Response(200, json=[]))
    assert cc.atualizar_host("a.test")["sairam"] == 1
    assert not FonteDoConhecimento.objects.filter(chave="comercial:site-a:curso:blender").exists()


@respx.mock
def test_a_volta_automatica_e_o_comando(monkeypatch):
    _catalogo()
    monkeypatch.setenv("CONHECIMENTO_COMERCIAL_HOSTS", "a.test,b.test")
    feitos = cc.manter_em_dia(forcar=True)
    assert {r["site"]["host"] for r in feitos} == {"a.test", "b.test"}
    assert cc.manter_em_dia() is None  # dentro da meia hora, não volta ao catálogo
    saida = StringIO()
    call_command("atualizar_conhecimento_comercial", "--host", "a.test", stdout=saida)
    assert "a.test: 0 nova(s), 0 mudada(s), 2 igual(is)" in saida.getvalue()


def test_sem_o_par_com_o_catalogo_a_volta_nao_faz_nada(monkeypatch):
    monkeypatch.delenv("CATALOGO_API_URL", raising=False)
    assert cc.manter_em_dia(forcar=True) is None


def test_trecho_longo_e_preco_no_meio():
    assert cc.sem_preco("Aulas ao vivo. Custa R$ 50 por mês. Correção semanal.") == (
        "Aulas ao vivo. Correção semanal. (preço e condições: consultar ao vivo)"
    )
    assert cc.sem_preco("Acesso 100% on-line.") == "Acesso 100% on-line."
    longo = "palavra " * 400
    assert all(len(p) <= cc.TAMANHO_DO_TRECHO * 2 for p in cc.pedacos(longo))
    assert len(cc.chave("x" * 64, "documento", "y" * 80)) <= 120


def test_preco_sem_cifrao_tambem_sai():
    for frase in (
        "O curso custa 497 reais.",
        "Investimento: 12 vezes de 49,70.",
        "Valor: 497.",
        "Mensalidade de 49,90 por mês.",
        "Sai por 1.497,00 no cartão de crédito.",
        "A anuidade é de 970.",
    ):
        assert cc.sem_preco(frase) == "(preço e condições: consultar ao vivo)", frase
    # O que não é preço continua.
    for frase in ("Tem 12 aulas em 3 módulos.", "Seis meses de acesso, com duas horas por semana.",
                  "Acesso 100% on-line."):
        assert cc.sem_preco(frase) == frase
    for pergunta in ("Qual o investimento?", "quanto é a mensalidade?", "quais os valores?",
                     "tem preços diferentes?", "quanto pago?"):
        assert cc._PERGUNTA_DE_PRECO.search(cc._normal(pergunta)), pergunta


@respx.mock
def test_preco_sem_cifrao_em_documento_nao_vira_trecho_lembrado():
    _catalogo()
    _documento("guia", "O curso Blender custa 497 reais em 12 vezes.\n\nTem correção humana.", titulo="Guia")
    MaterialComercial.objects.create(documento_nome="guia", site_id="site-a", site_host="a.test", tipo="material")
    cc.atualizar_host("a.test")
    assert all("497" not in t.texto for t in TrechoComercial.objects.all())
    resposta = cc.consultar("a.test", "quanto custa o curso blender?")
    assert all("497" not in t["texto"] for t in resposta["trechos"])
    assert any(f.get("ao_vivo") and "R$ 497,00" in f.get("texto", "") for f in resposta["fatos_ao_vivo"])


@respx.mock
def test_produtos_fora_do_ar_nao_mexe_em_cursos_nem_no_mapa():
    _catalogo()
    _documento("guia", "Correção humana das entregas.", titulo="Guia")
    MaterialComercial.objects.create(documento_nome="guia", site_id="site-a", site_host="a.test",
                                     tipo="material", produto="Escola de Blender")
    cc.atualizar_host("a.test")
    ids = set(TrechoComercial.objects.values_list("id", flat=True))
    respx.get(f"{CATALOGO}/produtos").mock(return_value=httpx.Response(503))
    relatorio = cc.atualizar_host("a.test")
    assert relatorio["faltou"] and relatorio["mudadas"] == 0 and relatorio["sairam"] == 0
    assert set(TrechoComercial.objects.values_list("id", flat=True)) == ids
    curso = TrechoComercial.objects.filter(site_id="site-a", tipo="curso").first()
    assert curso.produto_nome == "Escola de Blender"
    assert TrechoComercial.objects.get(ref="guia", ordem=0).produto_ref == "prod-blender"
    assert LigacaoDoConhecimento.objects.filter(relacao="faz parte do produto").exists()


@respx.mock
def test_mapa_da_equipe_nao_junta_ofertas_de_mesmo_apelido_em_sites_diferentes():
    _catalogo(cursos_b=[_curso("blender", "Blender Essencial", "prod-zbrush")])
    respx.get(f"{CURSOS}/cursos/blender/aulas", params={"site_id": "site-b"}).mock(
        return_value=httpx.Response(200, json=[_aula("01", "Escultura de rosto", "A", "Primeiros passos")]))
    respx.get(f"{CATALOGO}/sites/site-b/paginas/oferta").mock(return_value=httpx.Response(200, json=_pagina("anual")))
    respx.get(f"{CATALOGO}/sites/site-b/ofertas/anual").mock(
        return_value=httpx.Response(200, json=_oferta("site-b", "anual", PRODUTOS[1], preco=19700)))
    cc.atualizar_host("a.test")
    cc.atualizar_host("b.test")
    de_a = conhecimento.consultar(["Oferta anual (a.test)"], com_privados=True, profundidade=1)
    relacoes = {(l["de"], l["relacao"], l["para"]) for l in de_a["ligacoes"]}
    assert relacoes == {("Oferta anual (a.test)", "vende", "Escola de Blender")}
    todas = {(l.origem, l.destino) for l in LigacaoDoConhecimento.objects.all()}
    assert ("Oferta anual (b.test)", "Escultura no ZBrush") in todas
    # O curso de mesmo nome e o módulo de mesmo nome também não viram um nó só.
    assert ("Blender Essencial (b.test)", "Escultura no ZBrush") in todas
    assert ("Blender Essencial (a.test)", "Primeiros passos (Blender Essencial, a.test)") in todas
    assert ("Blender Essencial (b.test)", "Primeiros passos (Blender Essencial, b.test)") in todas


@respx.mock
def test_preco_ao_vivo_e_so_do_produto_perguntado_e_diz_qual():
    _catalogo(cursos_a=[_curso("blender", "Blender Essencial", "prod-blender"),
                        _curso("zbrush", "ZBrush Avançado", "prod-zbrush")])
    respx.get(f"{CURSOS}/cursos/zbrush/aulas", params={"site_id": "site-a"}).mock(
        return_value=httpx.Response(200, json=[_aula("01", "Escultura de rosto", "A", "Anatomia")]))
    cc.atualizar_host("a.test")
    resposta = cc.consultar("a.test", "quanto custa o ZBrush Avançado?")
    assert resposta["trechos"][0]["fonte"]["id"] == "zbrush"
    assert all(f.get("fonte", {}).get("tipo") != "oferta" for f in resposta["fatos_ao_vivo"])
    assert all("497" not in (f.get("texto") or "") for f in resposta["fatos_ao_vivo"])
    sem_oferta = [f for f in resposta["fatos_ao_vivo"] if f.get("fonte", {}).get("tipo") == "produto"]
    assert sem_oferta and "Escultura no ZBrush" in sem_oferta[0]["texto"]

    blender = cc.consultar("a.test", "quanto custa o Blender Essencial?")
    precos = [f for f in blender["fatos_ao_vivo"] if f.get("fonte", {}).get("tipo") == "oferta"]
    assert len(precos) == 1 and "R$ 497,00" in precos[0]["texto"]
    assert "Escola de Blender" in precos[0]["texto"]
    assert precos[0]["produto"] == {"ref": "prod-blender", "nome": "Escola de Blender"}


@respx.mock
def test_a_tela_dos_robos_nao_espera_o_catalogo(monkeypatch):
    from apps.agentes import executor

    chamadas = []
    monkeypatch.setattr(cc, "manter_em_dia", lambda **_: chamadas.append(1))
    executor.reacordar()  # é o que os botões de /admin/robos/ chamam
    assert chamadas == []


# ------------------------------------------------------------- a ferramenta


def _pessoa(nome: str, email: str) -> MembroDaEquipe:
    pessoa = MembroDaEquipe.objects.get(nome=nome)
    pessoa.email = email
    pessoa.save()
    return pessoa


@respx.mock
def test_a_ferramenta_do_robo():
    _catalogo()
    _documento("guia-interno", "Correção das entregas em até dois dias.", publico=False)
    MaterialComercial.objects.create(documento_nome="guia-interno", site_id="site-a", site_host="a.test")
    cc.atualizar_host("a.test")
    assert any(d["name"] == "consultar_conhecimento_comercial" for d in ferramentas.DEFINICOES)
    assert "consultar_conhecimento_comercial" in ferramentas.ROTULOS

    livia = _pessoa("Lívia", LIVIA)
    robo = trabalhos.robo_de(livia)
    execucao = Execucao.objects.create(robo=robo, tipo=Execucao.Tipo.CONVERSA)
    ctx = ferramentas.Contexto(robo=robo, membro=livia, execucao=execucao)
    texto = ferramentas.executar(ctx, "c1", "consultar_conhecimento_comercial", json.dumps(
        {"site": "a.test", "produto": None, "pergunta": "Como funciona a correção das entregas?"}))
    resultado = json.loads(texto)
    assert resultado["achou"] is True
    # A Lívia não administra o site: o guia interno não vem.
    assert all(t["fonte"]["id"] != "guia-interno" for t in resultado["trechos"])
    assert ChamadaDeFerramenta.objects.get(call_id="c1").situacao == "feita"

    vazio = json.loads(ferramentas.executar(ctx, "c2", "consultar_conhecimento_comercial", json.dumps(
        {"site": "", "produto": None, "pergunta": ""})))
    assert "erro" in vazio and ChamadaDeFerramenta.objects.get(call_id="c2").situacao == "recusada"
    assert cc.executar_ferramenta({"site": "a.test", "produto": "blender", "pergunta": "módulos"})["achou"]


# ------------------------------------------------------------------ a tela


def _cliente(email: str, nome: str) -> Client:
    respx.get(SESSAO).mock(return_value=httpx.Response(200, json={
        "autenticado": True, "id": "id-opaco-123", "nome_exibido": nome, "papel": None, "email": email,
    }))
    cliente = Client(HTTP_HOST="a.test")
    cliente.defaults["HTTP_COOKIE"] = COOKIE
    return cliente


@respx.mock
def test_a_tela_marca_atualiza_e_procura(settings):
    settings.ALLOWED_HOSTS = ["*"]
    _catalogo()
    _documento("depoimento-caio", "O Caio terminou o módulo de caneca em uma semana.", titulo="Caio")
    dono = _cliente(DONO, "Dono")
    assert dono.get(reverse("conhecimento_comercial")).status_code == 200
    resposta = dono.post(reverse("conhecimento_comercial"), {
        "acao": "marcar", "documento": "depoimento-caio", "tipo": "depoimento", "utilizavel": "1",
        "produto": "prod-blender", "oferta": "",
    })
    assert resposta.status_code == 302 and "resultado=marcado" in resposta["Location"]
    marca = MaterialComercial.objects.get(documento_nome="depoimento-caio")
    assert marca.site_id == "site-a" and marca.utilizavel and marca.produto == "prod-blender"
    assert TrechoComercial.objects.filter(tipo="depoimento", ref="depoimento-caio").exists()
    assert TrechoComercial.objects.filter(tipo="curso").exists()  # a marca já atualiza o site todo

    pagina = dono.get(reverse("conhecimento_comercial") + "?q=caneca").content.decode()
    assert "O Caio terminou" in pagina and "vigente desde" in pagina

    dono.post(reverse("conhecimento_comercial"), {"acao": "marcar", "documento": "depoimento-caio", "tipo": ""})
    assert not MaterialComercial.objects.exists()
    assert not TrechoComercial.objects.filter(ref="depoimento-caio").exists()
    assert "resultado=atualizado" in dono.post(reverse("conhecimento_comercial"), {"acao": "atualizar"})["Location"]

    _pessoa("Lívia", LIVIA)
    assert _cliente(LIVIA, "Lívia").get(reverse("conhecimento_comercial")).status_code == 404
