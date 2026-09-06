"""As restrições do banco do portfólio, e a prova de que elas MORDEM, uma a uma.

Cada `CheckConstraint` e cada `UniqueConstraint` de `apps/portfolio/models.py`
existe porque regra que vive só em Python é promessa: basta um
`objects.update()` numa tela futura, uma migração de dados ou uma linha editada
à mão no `psql` numa madrugada de incidente para a combinação proibida existir
sem ninguém saber (`armadilhas/023`, `RETROSPECTIVA-FASE-D.md` §2). Este arquivo
confere que o PostgreSQL recusa.

Aqui isso protege três coisas concretas: a fronteira entre escolas (Lei 9), a
privacidade do aluno (a vitrine é opt-in, AC-13) e a honestidade do selo da
escola (data e autor juntos, plano §6.2).
"""

import re

import pytest
from django.apps import apps
from django.db import IntegrityError, connection, transaction

from apps.portfolio.models import EstadoDoAluno, ItemDeConferencia, Peca, Portfolio

from conftest import OUTRO_SITE, SITE, agora

# Os nomes que o §7 do plano proíbe nesta obra, transcritos como PALAVRAS de
# nome de campo. `nivel` fica fora de propósito: o que a lei proíbe é trancar
# aula atrás de nível, não guardar um. Medir a coisa errada com precisão é como
# um portão morre.
PALAVRAS_PROIBIDAS = {
    "nota",
    "notas",
    "estrela",
    "estrelas",
    "ranking",
    "voto",
    "votos",
    "curtida",
    "curtidas",
    "pontuacao",
    "score",
    "rating",
    "xp",
}


def modelos_desta_app():
    return list(apps.get_app_config("portfolio").get_models())


# ---------------------------------------------------------------------------
# AC-02 — nenhuma chave estrangeira sai do banco desta célula
# ---------------------------------------------------------------------------


def test_nenhuma_chave_estrangeira_aponta_para_fora_desta_app():
    """O critério AC-02, medido no esquema e não na intenção.

    O banco desta célula não enxerga o das outras (Lei 2, Muralha 2). Quem é a
    pessoa se pergunta à `identidade`; se ela tem matrícula, à `alunos`. Uma
    chave estrangeira para lá não é só proibida: ela é impossível de satisfazer,
    e o dia em que alguém a escrevesse a migração quebraria em produção.
    """
    for modelo in modelos_desta_app():
        for campo in modelo._meta.get_fields():
            if not getattr(campo, "is_relation", False) or not campo.concrete:
                continue
            alvo = campo.related_model
            assert alvo._meta.app_label == "portfolio", (
                f"{modelo.__name__}.{campo.name} aponta para "
                f"{alvo._meta.app_label}.{alvo.__name__}, fora do banco desta "
                "célula — id de outra célula entra como texto opaco (AC-02)"
            )


def test_a_fronteira_de_site_e_de_aluno_mora_so_no_portfolio():
    """Uma casa para cada fronteira, e as filhas chegam por chave estrangeira.

    Copiar `site_id` e `aluno_id` para cada tabela filha criaria colunas
    denormalizadas capazes de MENTIR, e curar isso exigiria chave estrangeira
    composta escrita em `RunSQL` (`armadilhas/274`). Este guarda existe para que
    a próxima sessão, ao acrescentar uma tabela, não introduza a doença por
    hábito.
    """
    for modelo in modelos_desta_app():
        nomes = {campo.name for campo in modelo._meta.get_fields()}
        if modelo is Portfolio:
            assert {"site_id", "aluno_id"} <= nomes
            continue
        assert "site_id" not in nomes and "aluno_id" not in nomes, (
            f"{modelo.__name__} guarda cópia da fronteira — ela mora no "
            "Portfolio, e as filhas chegam a ela pela chave estrangeira"
        )


def test_nenhum_campo_guarda_nota_estrela_ranking_ou_voto():
    """O §7 do plano vira mecanismo, e não só uma lista bem escrita.

    A constituição desta célula tem critério de morte declarado: se a construção
    começar a desenhar nota, estrela, ranking ou voto popular em portfólio de
    aluno, para-se e reabre-se a decisão com o mantenedor. Lei sem mecanismo é a
    doença-mãe desta casa.
    """
    for modelo in modelos_desta_app():
        for campo in modelo._meta.get_fields():
            palavras = set(re.split(r"[^a-z0-9]+", campo.name.lower()))
            proibidas = palavras & PALAVRAS_PROIBIDAS
            assert not proibidas, (
                f"{modelo.__name__}.{campo.name} usa {sorted(proibidas)} — "
                "nota, estrela, ranking e voto são proibidos em portfólio de "
                "aluno (PLANO-PORTFOLIO-DO-ALUNO §7)"
            )


# ---------------------------------------------------------------------------
# Lei 9 / [INV-P11] — a fronteira de site, e um portfólio por aluno
# ---------------------------------------------------------------------------


def test_um_portfolio_por_aluno_por_site(criar_portfolio):
    criar_portfolio("aluno-1")
    with pytest.raises(IntegrityError):
        criar_portfolio("aluno-1")


def test_o_mesmo_aluno_tem_um_portfolio_em_cada_site(criar_portfolio):
    """A mesma pessoa estuda em duas escolas do mesmo deploy, e são dois."""
    criar_portfolio("aluno-1")
    criar_portfolio("aluno-1", site_id=OUTRO_SITE)
    assert Portfolio.objects.filter(aluno_id="aluno-1").count() == 2


def test_um_apelido_por_site(criar_portfolio):
    criar_portfolio("aluno-1", apelido="ana3d")
    with pytest.raises(IntegrityError):
        criar_portfolio("aluno-2", apelido="ana3d")


def test_o_mesmo_apelido_em_dois_sites_nao_colide(criar_portfolio):
    criar_portfolio("aluno-1", apelido="ana3d")
    criar_portfolio("aluno-2", apelido="ana3d", site_id=OUTRO_SITE)
    assert Portfolio.objects.filter(apelido="ana3d").count() == 2


def test_muitos_alunos_sem_apelido_convivem(criar_portfolio):
    """Sem apelido é o estado NORMAL de quem nunca ligou a vitrine.

    Uma unicidade sem a condição parcial deixaria o segundo aluno da escola sem
    conseguir nascer, e o defeito só apareceria com o segundo cadastro real.
    """
    criar_portfolio("aluno-1")
    criar_portfolio("aluno-2")
    assert Portfolio.objects.filter(apelido="").count() == 2


@pytest.mark.parametrize("apelido", ["Ana3D", "ana 3d", "ana_3d", "-ana", "ana-"])
def test_apelido_fora_da_forma_de_endereco_e_recusado(criar_portfolio, apelido):
    """O apelido é o endereço que o aluno manda ao cliente no chat."""
    with pytest.raises(IntegrityError):
        criar_portfolio("aluno-1", apelido=apelido)


# ---------------------------------------------------------------------------
# AC-13 — a vitrine é opt-in, e o banco não admite meio-termo
# ---------------------------------------------------------------------------


def test_a_vitrine_nasce_desligada(criar_portfolio):
    portfolio = criar_portfolio("aluno-1")
    assert portfolio.vitrine_publicada is False
    assert portfolio.publicada_em is None


def test_vitrine_publicada_sem_apelido_e_recusada(db):
    with pytest.raises(IntegrityError):
        Portfolio.objects.create(
            site_id=SITE,
            aluno_id="aluno-1",
            vitrine_publicada=True,
            publicada_em=agora(),
        )


def test_vitrine_publicada_sem_data_e_recusada(db):
    with pytest.raises(IntegrityError):
        Portfolio.objects.create(
            site_id=SITE,
            aluno_id="aluno-1",
            apelido="ana3d",
            vitrine_publicada=True,
        )


def test_vitrine_desligada_com_data_e_recusada(db):
    """Despublicar tira a página do ar E apaga o desde quando (AC-13)."""
    with pytest.raises(IntegrityError):
        Portfolio.objects.create(
            site_id=SITE,
            aluno_id="aluno-1",
            apelido="ana3d",
            vitrine_publicada=False,
            publicada_em=agora(),
        )


def test_a_vitrine_ligada_com_apelido_e_data_entra(criar_portfolio):
    portfolio = criar_portfolio("aluno-1", apelido="ana3d", publicada=True)
    assert portfolio.vitrine_publicada is True


# ---------------------------------------------------------------------------
# A peça: o link colado, a ordem e o destaque
# ---------------------------------------------------------------------------


def test_uma_peca_por_posicao(criar_portfolio, criar_peca):
    """Duas peças na mesma posição são recusadas, e a recusa chega no fim.

    A restrição é `DEFERRED`, então o banco só a confere quando a transação
    fecha, e não na linha do `INSERT`. `connection.check_constraints()` é o que
    força essa conferência aqui dentro: sem ele o teste passaria por engano, e o
    erro apareceria no desmonte da suíte, longe da linha que o causou.
    """
    portfolio = criar_portfolio("aluno-1")
    criar_peca(portfolio, ordem=1)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            criar_peca(portfolio, ordem=1)
            connection.check_constraints()


def test_duas_pecas_de_alunos_diferentes_ocupam_a_mesma_posicao(
    criar_portfolio, criar_peca
):
    criar_peca(criar_portfolio("aluno-1"), ordem=1)
    criar_peca(criar_portfolio("aluno-2"), ordem=1)
    assert Peca.objects.filter(ordem=1).count() == 2


def test_reordenar_duas_pecas_pela_troca_e_permitido(criar_portfolio, criar_peca):
    """A unicidade da ordem é adiada, e é por isso que a troca cabe.

    Reordenar é trocar duas posições, e no meio da troca as duas peças ocupam o
    mesmo lugar por um instante. Com a restrição imediata, o degrau 08 teria de
    inventar posições temporárias para conseguir arrastar um cartão na tela.
    """
    portfolio = criar_portfolio("aluno-1")
    primeira = criar_peca(portfolio, ordem=1)
    segunda = criar_peca(portfolio, ordem=2)

    with transaction.atomic():
        primeira.ordem = 2
        primeira.save(update_fields=["ordem"])
        segunda.ordem = 1
        segunda.save(update_fields=["ordem"])

    assert list(
        Peca.objects.filter(portfolio=portfolio)
        .order_by("ordem")
        .values_list("id", flat=True)
    ) == [segunda.id, primeira.id]


def test_a_ordem_comeca_em_um(criar_portfolio, criar_peca):
    with pytest.raises(IntegrityError):
        criar_peca(criar_portfolio("aluno-1"), ordem=0)


def test_a_peca_tem_link(criar_portfolio, criar_peca):
    """A foto entra por LINK colado, e peça sem link é peça que não existe."""
    with pytest.raises(IntegrityError):
        criar_peca(criar_portfolio("aluno-1"), link="")


def test_a_peca_nasce_sem_destaque(criar_portfolio, criar_peca):
    assert criar_peca(criar_portfolio("aluno-1")).destaque is False


# ---------------------------------------------------------------------------
# AC-06 — a marcação da lista de conferência, no banco, por aluno
# ---------------------------------------------------------------------------


def test_uma_marcacao_por_item_por_portfolio(criar_portfolio, criar_item):
    portfolio = criar_portfolio("aluno-1")
    criar_item(portfolio, chave="tres-tipos-escolhidos")
    with pytest.raises(IntegrityError):
        criar_item(portfolio, chave="tres-tipos-escolhidos")


@pytest.mark.parametrize("etapa", [0, 6])
def test_o_item_esta_numa_das_cinco_etapas(criar_portfolio, criar_item, etapa):
    with pytest.raises(IntegrityError):
        criar_item(criar_portfolio("aluno-1"), etapa=etapa)


def test_o_item_tem_chave(criar_portfolio, criar_item):
    with pytest.raises(IntegrityError):
        criar_item(criar_portfolio("aluno-1"), chave="")


def test_a_marca_sem_data_e_recusada(criar_portfolio, criar_item):
    with pytest.raises(IntegrityError):
        criar_item(criar_portfolio("aluno-1"), marcado=True)


def test_a_data_sem_a_marca_e_recusada(criar_portfolio, criar_item):
    with pytest.raises(IntegrityError):
        criar_item(criar_portfolio("aluno-1"), marcado=False, marcado_em=agora())


def test_a_marcacao_atravessa_aparelhos(criar_portfolio, criar_item):
    """O AC-06 em uma frase: marcou no celular, abre no computador e está lá.

    A prova é reler do BANCO, e não da instância que acabou de gravar: é o banco
    que atravessa o aparelho. Guardar isso em `request.session` passaria num
    teste de unidade escrito com a instância na mão, reprovaria este, e
    deslogaria a plataforma inteira em produção ([INV-P12],
    `armadilhas/143`).
    """
    portfolio = criar_portfolio("aluno-1")
    item = criar_item(portfolio, chave="tres-tipos-escolhidos")
    item.marcado = True
    item.marcado_em = agora()
    item.save()

    outro_aparelho = ItemDeConferencia.objects.get(pk=item.pk)
    assert outro_aparelho.marcado is True
    assert outro_aparelho.marcado_em is not None


def test_desmarcar_nao_apaga_a_linha(criar_portfolio, criar_item):
    portfolio = criar_portfolio("aluno-1")
    item = criar_item(
        portfolio, chave="tres-tipos-escolhidos", marcado=True, marcado_em=agora()
    )
    item.marcado = False
    item.marcado_em = None
    item.save()

    assert ItemDeConferencia.objects.filter(pk=item.pk).exists()


# ---------------------------------------------------------------------------
# O estado do aluno e o selo da escola
# ---------------------------------------------------------------------------


def test_um_estado_por_portfolio(criar_portfolio, criar_estado):
    portfolio = criar_portfolio("aluno-1")
    criar_estado(portfolio)
    with pytest.raises(IntegrityError):
        criar_estado(portfolio)


def test_o_aluno_comeca_na_primeira_etapa(criar_portfolio, criar_estado):
    assert criar_estado(criar_portfolio("aluno-1")).etapa_atual == 1


@pytest.mark.parametrize("etapa", [0, 6])
def test_a_etapa_atual_e_uma_das_cinco(criar_portfolio, criar_estado, etapa):
    with pytest.raises(IntegrityError):
        criar_estado(criar_portfolio("aluno-1"), etapa_atual=etapa)


def test_o_portfolio_nasce_sem_selo(criar_portfolio, criar_estado):
    estado = criar_estado(criar_portfolio("aluno-1"))
    assert estado.selo_conferido_em is None
    assert estado.selo_conferido_por == ""


def test_selo_sem_quem_conferiu_e_recusado(criar_portfolio, criar_estado):
    """O selo vale para o que o MONITOR viu no dia (plano §6.2).

    Selo com data e sem autor é selo que ninguém assinou, e ele iria para a
    página que o aluno manda ao cliente pagante.
    """
    with pytest.raises(IntegrityError):
        criar_estado(criar_portfolio("aluno-1"), selo_conferido_em=agora())


def test_selo_sem_data_e_recusado(criar_portfolio, criar_estado):
    with pytest.raises(IntegrityError):
        criar_estado(criar_portfolio("aluno-1"), selo_conferido_por="monitor-1")


def test_o_selo_com_data_e_autor_entra(criar_portfolio, criar_estado):
    estado = criar_estado(
        criar_portfolio("aluno-1"),
        selo_conferido_em=agora(),
        selo_conferido_por="monitor-1",
    )
    assert EstadoDoAluno.objects.get(pk=estado.pk).selo_conferido_por == "monitor-1"
