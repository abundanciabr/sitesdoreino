"""A oferta do aluno usa apenas informações que ele escolheu apresentar."""

import pytest

from apps.quiz.portfolio import _plano, _validar_respostas


def test_oferta_guarda_escolhas_concretas_sem_inventar_condicoes():
    respostas = _validar_respostas({
        "servico_proprio": "Faço acessórios sob encomenda",
        "publico": "equipes_marcas",
        "oferta_uso": "Experiência da marca no Roblox",
        "oferta_entregaveis": "Modelo 3D e imagens de prévia",
        "oferta_formatos": "RBXM",
        "oferta_prazo": "Prazo acertado após o briefing",
        "oferta_revisoes": "Uma revisão de proporções",
        "oferta_suporte": "Ajuste de importação por mensagem",
        "oferta_preco": "R$ 250",
        "oferta_moeda": "BRL",
        "oferta_exibir_preco": "sim",
        "oferta_condicoes": "Escopo combinado antes de começar",
        "oferta_continuidade": "Novos itens mediante orçamento",
        "oferta_contato": "Formulário na página",
    })
    oferta = _plano(respostas)["oferta_comercial"]

    assert oferta["encomenda"] == "Faço acessórios sob encomenda"
    assert oferta["comprador"] == "equipes de marcas que encomendam experiências ou itens Roblox"
    assert oferta["uso"] == "Experiência da marca no Roblox"
    assert oferta["entregaveis"] == "Modelo 3D e imagens de prévia"
    assert oferta["formatos"] == "RBXM"
    assert oferta["prazo"] == "Prazo acertado após o briefing"
    assert oferta["revisoes"] == "Uma revisão de proporções"
    assert oferta["suporte"] == "Ajuste de importação por mensagem"
    assert oferta["preco"] == "R$ 250"
    assert oferta["moeda"] == "BRL"
    assert oferta["exibir_preco"] == "sim"
    assert oferta["condicoes"] == "Escopo combinado antes de começar"
    assert oferta["continuidade"] == "Novos itens mediante orçamento"
    assert oferta["contato"] == "Formulário na página"


def test_oferta_vazia_nao_promete_preco_prazo_ou_suporte():
    oferta = _plano({})["oferta_comercial"]
    assert oferta["encomenda"]
    assert oferta["preco"] == oferta["prazo"] == oferta["suporte"] == ""
    assert oferta["exibir_preco"] == ""


def test_aluno_pode_substituir_sugestoes_sem_perder_respostas_antigas():
    respostas = _validar_respostas({
        "publico": "marcas",
        "servico_proprio": "Serviço antigo",
        "oferta_encomenda": "Pacote de personagens",
        "oferta_comprador": "Estúdios independentes",
        "oferta_exibir_preco": "nao",
    })
    plano = _plano(respostas)
    assert plano["servico"] == "Serviço antigo"
    assert plano["publico"] == "marcas e clientes"
    assert plano["oferta_comercial"]["encomenda"] == "Pacote de personagens"
    assert plano["oferta_comercial"]["comprador"] == "Estúdios independentes"


@pytest.mark.parametrize("valor", ["talvez", "garantido", "true"])
def test_visibilidade_do_preco_aceita_somente_escolha_explicita(valor):
    with pytest.raises(ValueError, match="oferta_exibir_preco"):
        _validar_respostas({"oferta_exibir_preco": valor})
