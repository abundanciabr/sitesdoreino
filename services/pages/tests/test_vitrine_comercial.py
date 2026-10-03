"""A apresentação pública mostra apenas escolhas comerciais e obras selecionadas."""

from types import SimpleNamespace

from django.template.loader import render_to_string


def contexto_comercial():
    primeira = SimpleNamespace(
        pk=1,
        link="https://imagens.exemplo.test/chapeu.png",
        legenda="Chapéu antigo",
        titulo_comercial="Chapéu de aventura",
        texto_comercial="Modelo e textura criados por mim.",
        contribuicao="Modelagem",
        uso_pretendido="Acessório UGC",
        destaque=True,
        provas_visiveis=[
            {
                "tipo": "wireframe",
                "link": "https://imagens.exemplo.test/chapeu-wireframe.png",
                "descricao": "Ver wireframe",
            }
        ],
    )
    segunda = SimpleNamespace(
        pk=2,
        link="https://imagens.exemplo.test/cabelo.png",
        legenda="Cabelo",
        titulo_comercial="",
        texto_comercial="",
        contribuicao="",
        uso_pretendido="",
        destaque=False,
        provas_visiveis=[],
    )
    return {
        "portfolio": SimpleNamespace(
            apresentacao_publica="Texto legado",
            servico_publico="Serviço legado",
            aluno_id="p_privado_123",
            email="segredo@exemplo.test",
            plano_privado="META_INTERNA_NAO_PUBLICAR",
        ),
        "apelido": "ana-3d",
        "obras": [primeira, segunda],
        "hero": primeira,
        "comercial": {
            "titulo": "Acessórios 3D para experiências Roblox",
            "subtitulo": "Peças sob encomenda",
            "apresentacao": "Produzo modelos para projetos de clientes.",
            "oferta": "Chapéus individuais ou conjuntos combinados.",
            "continuidade": "Novas peças podem ser combinadas.",
            "diferenciais": "Apresento o modelo e seu wireframe.",
            "condicoes": "Escopo combinado antes de começar.",
            "duvidas": "Você já tem referências? Podemos conversar.",
            "cta": "Enviar meu projeto",
        },
        "oferta": {
            "encomenda": "Chapéus",
            "comprador": "Criadores de experiências",
            "uso": "Roblox",
            "entregaveis": "Modelo e textura",
            "formatos": ".rbxm",
            "prazo": "A combinar",
            "revisoes": "Uma revisão",
            "suporte": "Entrega por mensagem",
            "preco": "R$ 250",
            "moeda": "BRL",
            "condicoes": "Pagamento combinado",
            "continuidade": "",
            "exibir_preco": False,
        },
        "contato_url": "https://contato.exemplo.test/ana",
        "url_da_capa": "https://escola.exemplo.test/",
        "selo_em": None,
    }


def test_comercial_mostra_obra_real_oferta_prova_e_contato_sem_preco_oculto():
    contexto = contexto_comercial()
    html = render_to_string("pages/vitrine.html", contexto)
    galeria = html.split('<ol class="obras">', 1)[1]

    assert "<h1 id=\"titulo-principal\">Acessórios 3D para experiências Roblox</h1>" in html
    assert galeria.index("chapeu.png") < galeria.index("cabelo.png")
    assert 'href="https://imagens.exemplo.test/chapeu-wireframe.png"' in html
    assert 'href="https://contato.exemplo.test/ana"' in html
    assert "Chapéus individuais ou conjuntos combinados." in html
    assert ".rbxm" in html
    assert "250" not in html
    assert "p_privado_123" not in html
    assert "segredo@exemplo.test" not in html
    assert "META_INTERNA_NAO_PUBLICAR" not in html
    assert "Minha jornada" not in html


def test_preco_aparece_somente_quando_autor_escolheu_exibir():
    contexto = contexto_comercial()
    contexto["oferta"]["exibir_preco"] = True

    html = render_to_string("pages/vitrine.html", contexto)

    assert '<p class="preco">BRL R$ 250</p>' in html


def test_comercial_escapa_textos_e_sem_contato_nao_mostra_botao_morto():
    contexto = contexto_comercial()
    contexto["comercial"]["titulo"] = '<script>alert("x")</script>'
    contexto["obras"][0].texto_comercial = "<b>privado?</b>"
    contexto["contato_url"] = ""
    html = render_to_string("pages/vitrine.html", contexto)

    assert "<script" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;privado?&lt;/b&gt;" in html
    assert "O autor ainda não informou um canal de contato" in html
    assert "Enviar meu projeto</a>" not in html


def test_legado_mantem_textos_e_selecao_sem_exibir_dados_comerciais():
    contexto = contexto_comercial()
    contexto.pop("comercial")
    contexto.pop("oferta")
    contexto.pop("hero")
    contexto.pop("contato_url")
    html = render_to_string("pages/vitrine.html", contexto)

    assert "Texto legado" in html
    assert "Serviço legado" in html
    assert "Chapéu antigo" in html
    assert "Cabelo" in html
    assert "Detalhes da encomenda" not in html
    assert "p_privado_123" not in html
