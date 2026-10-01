"""A escola responde ao contexto visto, mesmo antes de haver uma obra pronta."""

import pytest

from apps.portfolio import conferencia, projetos
from apps.portfolio.models import EstadoDoAluno, EstadoDoPedido, MotivoDaDevolucao


@pytest.mark.django_db
def test_feedback_de_projeto_sem_obra_guarda_contexto_e_nao_carimba_portfolio():
    projeto = projetos.criar_do_aluno(
        "site-a", "aluna-a", proposta_dict={"titulo": "Cafeteria", "intencao": "Criar móveis"}
    )
    pedido = conferencia.pedir(
        projeto.portfolio, projeto=projeto,
        duvida_aluno="Como começo pela cadeira?",
    )
    assert pedido.contexto["projeto"]["titulo"] == "Cafeteria"
    assert pedido.contexto["trabalhos"] == []
    assert projetos.contexto_atual(pedido)

    conferencia.aceitar(
        pedido=pedido, conferido_por="professora",
        feedback_pontos_fortes="A intenção é clara.",
        feedback_proximo_passo="Comece pela cadeira.",
    )
    pedido.refresh_from_db()
    assert pedido.estado == EstadoDoPedido.ACEITO
    assert pedido.feedback_pontos_fortes == "A intenção é clara."
    assert not EstadoDoAluno.objects.filter(portfolio=projeto.portfolio, selo_conferido_em__isnull=False).exists()

    projetos.editar_do_aluno("site-a", "aluna-a", projeto.pk, intencao="Agora quero veículos")
    pedido.refresh_from_db()
    assert pedido.contexto["projeto"]["intencao"] == "Criar móveis"
    assert not projetos.contexto_atual(pedido)


@pytest.mark.django_db
def test_devolucao_com_orientacao_escrita_e_historico_imutavel():
    projeto = projetos.criar_do_aluno("site-a", "aluna-a", proposta_dict={"titulo": "Meu plano"})
    pedido = conferencia.pedir(projeto.portfolio, projeto=projeto)
    with pytest.raises(conferencia.ConferenciaRecusada, match="Escreva a orientação"):
        conferencia.devolver(
            pedido=pedido, conferido_por="professora", motivo=MotivoDaDevolucao.ORIENTACAO
        )
    conferencia.devolver(
        pedido=pedido, conferido_por="professora", motivo=MotivoDaDevolucao.ORIENTACAO,
        feedback_melhorar="Defina onde usará o objeto.",
        feedback_proximo_passo="Teste um modelo simples no Roblox.",
    )
    pedido.refresh_from_db()
    assert pedido.estado == EstadoDoPedido.DEVOLVIDO
    assert pedido.feedback_proximo_passo == "Teste um modelo simples no Roblox."
    assert pedido.contexto["projeto"]["titulo"] == "Meu plano"


@pytest.mark.django_db
def test_mudar_selecao_publica_nao_invalida_avaliacao(criar_peca):
    projeto = projetos.criar_do_aluno("site-a", "aluna-a", proposta_dict={"titulo": "Cadeiras"})
    peca = criar_peca(projeto.portfolio, projeto=projeto, legenda="Primeira cadeira")
    pedido = conferencia.pedir(projeto.portfolio, projeto=projeto)
    assert projetos.contexto_atual(pedido)
    projetos.selecionar_peca_do_aluno("site-a", "aluna-a", peca.pk, mostrar=True)
    assert projetos.contexto_atual(pedido)
    peca.legenda = "Cadeira revisada"
    peca.save(update_fields=["legenda"])
    assert not projetos.contexto_atual(pedido)


@pytest.mark.django_db
def test_texto_publico_posterior_nao_recebe_selo_da_versao_anterior(criar_peca):
    projeto = projetos.criar_do_aluno("site-a", "aluna-a", proposta_dict={"titulo": "Objetos"})
    criar_peca(projeto.portfolio, projeto=projeto)
    pedido = conferencia.pedir(projeto.portfolio)
    projetos.editar_apresentacao_publica_do_aluno(
        "site-a", "aluna-a", apresentacao_publica="Nova apresentação",
        servico_publico="Objetos de cena",
    )
    assert not projetos.contexto_atual(pedido)
    conferencia.aceitar(pedido=pedido, conferido_por="professora")
    assert not EstadoDoAluno.objects.filter(
        portfolio=projeto.portfolio, selo_conferido_em__isnull=False
    ).exists()
