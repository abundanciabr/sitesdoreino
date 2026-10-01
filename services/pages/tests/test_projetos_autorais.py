"""Escolha do aluno, histórico das tentativas e privacidade das obras."""

import uuid

import pytest

from apps.portfolio import projetos
from apps.portfolio.models import Portfolio, ProjetoAutoral


@pytest.mark.django_db
def test_clique_repetido_preserva_a_escolha_e_nova_tentativa_nao_apaga():
    tentativa = uuid.uuid4()
    primeiro = projetos.criar_do_aluno(
        "escola-a", "aluna-a", tentativa, "moveis",
        {"titulo": "Móveis para cafeteria", "intencao": "Criar cenário"},
    )
    repetido = projetos.criar_do_aluno(
        "escola-a", "aluna-a", tentativa, "outra",
        {"titulo": "Título de outro clique"},
    )
    novo = projetos.criar_do_aluno(
        "escola-a", "aluna-a", uuid.uuid4(), "veiculos",
        {"titulo": "Um veículo"},
    )

    assert primeiro.pk == repetido.pk
    assert repetido.titulo == "Móveis para cafeteria"
    assert novo.pk != primeiro.pk
    assert ProjetoAutoral.objects.do_aluno(site_id="escola-a", aluno_id="aluna-a").count() == 2


@pytest.mark.django_db
def test_projeto_direto_e_edicao_isolados_por_site_e_aluno():
    projeto = projetos.criar_do_aluno("escola-a", "aluna-a", proposta_dict={"titulo": "Minha obra"})
    projetos.editar_do_aluno("escola-a", "aluna-a", projeto.pk, titulo="Novo título")
    projeto.refresh_from_db()
    assert projeto.titulo == "Novo título"
    assert projeto.origem_exploracao is None
    assert Portfolio.objects.do_aluno(site_id="escola-a", aluno_id="aluna-a").exists()

    for site, aluno in (("escola-b", "aluna-a"), ("escola-a", "aluna-b")):
        with pytest.raises(projetos.ProjetoInvalido, match="não encontrado"):
            projetos.editar_do_aluno(site, aluno, projeto.pk, titulo="Invasão")
    with pytest.raises(projetos.ProjetoInvalido, match="200"):
        projetos.editar_do_aluno("escola-a", "aluna-a", projeto.pk, titulo="x" * 201)
    with pytest.raises(projetos.ProjetoInvalido, match="3000"):
        projetos.editar_do_aluno("escola-a", "aluna-a", projeto.pk, intencao="x" * 3001)


@pytest.mark.django_db
def test_snapshot_da_proposta_nao_muda_quando_origem_e_projeto_mudam():
    proposta = {"titulo": "Cafeteria", "direcao": "Objetos"}
    projeto = projetos.criar_do_aluno("escola-a", "aluna-a", uuid.uuid4(), "cafe", proposta)
    proposta["titulo"] = "Modificado fora"
    projetos.editar_do_aluno("escola-a", "aluna-a", projeto.pk, titulo="Outro nome")
    projeto.refresh_from_db()
    assert projeto.origem_proposta == {"titulo": "Cafeteria", "direcao": "Objetos"}
    assert projeto.titulo == "Outro nome"


@pytest.mark.django_db
def test_selecao_publica_de_uma_obra_independe_das_outras(criar_portfolio, criar_peca):
    portfolio = criar_portfolio("aluna-a")
    uma = criar_peca(portfolio)
    outra = criar_peca(portfolio, ordem=2)
    uma.mostrar_na_pagina_publica = False
    outra.mostrar_na_pagina_publica = False
    uma.save(update_fields=["mostrar_na_pagina_publica"])
    outra.save(update_fields=["mostrar_na_pagina_publica"])

    projetos.selecionar_peca_do_aluno(portfolio.site_id, portfolio.aluno_id, uma.pk, mostrar=True)
    uma.refresh_from_db()
    outra.refresh_from_db()
    portfolio.refresh_from_db()
    assert uma.mostrar_na_pagina_publica is True
    assert outra.mostrar_na_pagina_publica is False
    assert portfolio.vitrine_publicada is False
    with pytest.raises(projetos.ProjetoInvalido):
        projetos.selecionar_peca_do_aluno("outro-site", portfolio.aluno_id, outra.pk, mostrar=True)


@pytest.mark.django_db
def test_contexto_de_obra_e_texto_publico_tem_donos_e_limites(criar_peca):
    projeto = projetos.criar_do_aluno("site-a", "aluna-a", proposta_dict={"titulo": "Cadeiras"})
    alheio = projetos.criar_do_aluno("site-a", "aluna-b", proposta_dict={"titulo": "Barcos"})
    peca = criar_peca(projeto.portfolio)
    with pytest.raises(projetos.ProjetoInvalido, match="não encontrado"):
        projetos.editar_peca_do_aluno("site-a", "aluna-a", peca.pk, projeto_id=alheio.pk)
    with pytest.raises(projetos.ProjetoInvalido, match="3000"):
        projetos.editar_peca_do_aluno("site-a", "aluna-a", peca.pk, duvida="x" * 3001)
    projetos.editar_peca_do_aluno(
        "site-a", "aluna-a", peca.pk, projeto_id=projeto.pk,
        uso_pretendido="Cenário de Roblox",
    )
    peca.refresh_from_db()
    assert peca.projeto_id == projeto.pk
    assert peca.uso_pretendido == "Cenário de Roblox"
    projetos.editar_apresentacao_publica_do_aluno(
        "site-a", "aluna-a", apresentacao_publica="Crio móveis",
        servico_publico="Objetos para jogos",
    )
    projeto.portfolio.refresh_from_db()
    assert projeto.portfolio.apresentacao_publica == "Crio móveis"
    assert projeto.portfolio.servico_publico == "Objetos para jogos"
