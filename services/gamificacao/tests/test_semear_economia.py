"""A semeadura da economia: idempotente, e com TUDO nascendo desligado.

O guarda que importa aqui é o do `ativa=False`. Se semear já ligasse as regras,
um `deploy` viraria uma mudança de economia sem ninguém decidir nada — e a lei
§10.5 diz o contrário: economia é DADO, ajustada por UPDATE + versão, anunciada
e nunca retroativa. Ligar é decisão do mantenedor.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.gamificacao.models import (
    ConquistaDefinicao,
    ItemCosmetico,
    LigaDefinicao,
    MissaoDefinicao,
    NivelDefinicao,
    RegraDePontuacao,
)

TABELAS_DE_ECONOMIA = (
    NivelDefinicao,
    RegraDePontuacao,
    MissaoDefinicao,
    ConquistaDefinicao,
    LigaDefinicao,
    ItemCosmetico,
)


def _semear(site="escola-a"):
    saida = StringIO()
    call_command("semear_economia", "--site", site, stdout=saida)
    return saida.getvalue()


@pytest.mark.django_db
def test_a_semeadura_termina_com_a_linha_que_o_pipeline_procura():
    saida = _semear()
    assert "SEMEADURA DA ECONOMIA OK" in saida


@pytest.mark.django_db
def test_tudo_nasce_desligado():
    """A asserção que protege o aluno de uma economia ligada por acidente."""
    _semear()

    ligadas = {
        modelo.__name__: list(
            modelo.objects.filter(ativa=True).values_list("slug", flat=True)[:5]
        )
        for modelo in TABELAS_DE_ECONOMIA
        if modelo.objects.filter(ativa=True).exists()
    }

    assert ligadas == {}, (
        f"a semeadura LIGOU linhas de economia: {ligadas}. Semear é preparar; "
        "ligar é decisão do mantenedor (lei §10.5)."
    )


@pytest.mark.django_db
def test_a_semeadura_e_idempotente_e_nao_pisa_em_edicao_humana():
    """Rodar duas vezes não duplica, e não desfaz o que uma pessoa mudou."""
    _semear()
    antes = {m.__name__: m.objects.count() for m in TABELAS_DE_ECONOMIA}

    # O mantenedor liga uma regra e muda um número, como fará na vida real — e
    # "como na vida real" agora inclui a DATA: o banco recusa regra ligada sem
    # `vigente_desde`, que é o mecanismo do "nunca retroativo" da lei §10.5.
    # Quem carimba de verdade é `interruptores.mudar()`, pela tela do painel.
    RegraDePontuacao.objects.filter(slug="quiz-aprovado").update(
        ativa=True, pontos=45, vigente_desde=timezone.now()
    )

    saida = _semear()
    depois = {m.__name__: m.objects.count() for m in TABELAS_DE_ECONOMIA}
    regra = RegraDePontuacao.objects.get(slug="quiz-aprovado")

    assert depois == antes, "semear de novo criou linhas duplicadas"
    assert regra.ativa is True, "semear desligou o que o mantenedor tinha ligado"
    assert regra.pontos == 45, "semear sobrescreveu o número que o mantenedor mudou"
    assert "ja existiam" in saida
    assert "ATENCAO" in saida, (
        "semear encontrou linha LIGADA e não avisou. Silêncio aqui esconde a "
        "diferença entre 'o mantenedor ligou' e 'alguém ligou por código'."
    )


@pytest.mark.django_db
def test_cada_site_recebe_a_propria_economia():
    """Lei 9: uma fábrica, N lojas. A escola A não herda os números da B."""
    _semear("escola-a")
    _semear("escola-b")

    assert RegraDePontuacao.objects.filter(site_id="escola-a").count() == 6
    assert RegraDePontuacao.objects.filter(site_id="escola-b").count() == 6

    RegraDePontuacao.objects.filter(site_id="escola-a", slug="quiz-aprovado").update(
        pontos=99
    )
    outra = RegraDePontuacao.objects.get(site_id="escola-b", slug="quiz-aprovado")
    assert outra.pontos == 30, "mexer na escola A mudou a escola B"


@pytest.mark.django_db
def test_nenhum_marco_semeado_paga_xp():
    """Decisão fechada 7: marco real vale 0 XP. Aqui vale para os dados, não só
    para a restrição."""
    _semear()

    pagantes = list(
        ConquistaDefinicao.objects.filter(
            classe=ConquistaDefinicao.Classe.MARCO, pontos__gt=0
        ).values_list("slug", "pontos")
    )

    assert pagantes == [], f"marco semeado pagando XP: {pagantes}"


@pytest.mark.django_db
def test_todo_marco_de_dinheiro_semeado_so_a_equipe_valida():
    """Lei §9, conferida nos DADOS semeados e não só no esquema."""
    _semear()

    frouxos = list(
        ConquistaDefinicao.objects.filter(envolve_dinheiro=True)
        .exclude(exige_validador_da_equipe=True)
        .values_list("slug", flat=True)
    )

    assert frouxos == [], f"marco de dinheiro sem a trava: {frouxos}"
    assert ConquistaDefinicao.objects.filter(envolve_dinheiro=True).count() >= 1, (
        "nenhum marco de dinheiro foi semeado — a trava acima passou a ser "
        "vácuo, e um teste que não vê nada não prova nada"
    )


@pytest.mark.django_db
def test_nao_existe_regra_que_pague_por_login():
    """Login vale 0 XP, sempre — e a garantia é a AUSÊNCIA de regra.

    Uma regra de login valendo zero seria uma linha que alguém edita para 5 numa
    tarde. Não haver a linha é o que torna a decisão durável.
    """
    _semear()

    suspeitas = [
        (slug, evento)
        for slug, evento in RegraDePontuacao.objects.values_list(
            "slug", "evento_gatilho"
        )
        if "login" in slug or "login" in evento or "sessao" in evento
    ]

    assert suspeitas == [], f"nasceu regra de presença ou de login: {suspeitas}"


@pytest.mark.django_db
def test_as_quatro_ligas_semeadas_e_nenhum_diamante():
    _semear()
    tiers = set(LigaDefinicao.objects.values_list("tier", flat=True))

    assert tiers == {"bronze", "prata", "ouro", "platina"}


@pytest.mark.django_db
def test_nenhum_cosmetico_semeado_vende_protecao():
    """O escudo não está na loja, nem por Cristais (decisão fechada 7)."""
    _semear()
    slugs = list(ItemCosmetico.objects.values_list("slug", flat=True))

    assert not [
        s for s in slugs if "escudo" in s or "protecao" in s
    ], f"a loja semeada passou a vender proteção: {slugs}"


@pytest.mark.django_db
def test_a_escada_de_niveis_comeca_barata_e_nao_promete_credencial():
    """Curva acelerada no comecinho, e nenhum título com cara de certificado."""
    _semear()
    niveis = list(NivelDefinicao.objects.order_by("nivel"))

    assert [n.nivel for n in niveis] == list(range(1, 11))
    assert niveis[0].xp_necessario == 0
    # O segundo degrau custa menos que um décimo do último: é ali que a pessoa
    # decide se isto vale o tempo dela.
    assert niveis[1].xp_necessario * 10 < niveis[-1].xp_necessario

    proibido = ("certificad", "diploma", "profission", "formad", "graduad")
    achados = [
        n.titulo
        for n in niveis
        if any(
            p in n.titulo.lower() or p in n.titulo_feminino.lower() for p in proibido
        )
    ]
    assert achados == [], f"título de nível prometendo credencial: {achados}"
