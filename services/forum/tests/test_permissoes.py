"""Guardas das permissões — a única pergunta que o fórum responde sozinho.

**Reconhecer não é autorizar.** A `identidade` diz quem é, a `alunos` diz a
categoria, e QUEM PODE é decidido aqui, fail-CLOSED
(`DECISAO-forum-da-escola.md` §3).

Todo teste deste arquivo tem a mesma forma: monta um mundo, e exige que o
**erro** feche a porta em vez de abri-la.
"""

import pytest

from apps.core.permissoes import areas_visiveis, pode_escrever, pode_ler
from apps.core.sessao import VISITANTE, Ator
from apps.forum.models import Area, Pessoa

pytestmark = pytest.mark.django_db


@pytest.fixture
def pessoa():
    return Pessoa.objects.create(
        id_da_plataforma="p1", email="a@b.com", nome_exibido="Alguém"
    )


@pytest.fixture
def cadastrado(pessoa):
    """Tem login, não comprou. É a categoria 2 da lei das categorias."""
    return Ator(pessoa=pessoa)


@pytest.fixture
def aluno(pessoa):
    return Ator(pessoa=pessoa, eh_aluno=True)


@pytest.fixture
def professor(pessoa):
    return Ator(pessoa=pessoa, eh_professor=True)


def area(**kwargs):
    base = {"slug": kwargs.pop("slug", "x"), "nome": "Área"}
    return Area.objects.create(**base, **kwargs)


# --------------------------------------------------------------- ler
def test_area_publica_e_lida_ate_por_visitante():
    """A aposta de crescimento: o Google precisa conseguir ler."""
    a = area(visibilidade=Area.Visibilidade.PUBLICA)
    assert pode_ler(a, VISITANTE) is True


def test_area_de_alunos_e_invisivel_para_visitante_e_para_cadastrado(cadastrado):
    a = area(visibilidade=Area.Visibilidade.ALUNOS)
    assert pode_ler(a, VISITANTE) is False
    assert pode_ler(a, cadastrado) is False


def test_area_de_alunos_abre_para_aluno_e_para_professor(aluno, professor):
    a = area(visibilidade=Area.Visibilidade.ALUNOS)
    assert pode_ler(a, aluno) is True
    assert pode_ler(a, professor) is True


def test_area_de_turma_fecha_ate_para_aluno_enquanto_o_curso_nao_for_conferido(aluno):
    """O caso que mais tenta a mão: 'deixa passar por enquanto'.

    Saber se alguém está NUM curso é pergunta que o fórum ainda não faz. Abrir
    'temporariamente' escancararia justamente a área mais restrita do sistema —
    a que promete ser de uma turma só.
    """
    a = area(
        visibilidade=Area.Visibilidade.TURMA, curso_id="curso_esqueleto", slug="turma"
    )
    assert pode_ler(a, aluno) is False


def test_area_desativada_some_para_quem_nao_modera(aluno, professor):
    """Arquivada é indistinguível de inexistente — para quem não pode reabrir.

    **Este guarda mudou em 30/08/2026, e a mudança é deliberada, não um
    afrouxamento para o código passar.** Ele nasceu dizendo "some para todo
    mundo", quando desativar uma área era gesto que só existia no banco. Desde
    que arquivar virou um BOTÃO (`apps/core/moderacao.py`), a regra ganhou a
    exceção sem a qual o botão seria porta de mão única: quem arquiva continua
    enxergando a área, marcada, senão reabrir exigiria alguém com acesso ao
    banco. O professor entrou nessa lista por decisão do mantenedor no mesmo
    dia (*"professor também, com tudo"*).

    A metade que NÃO afrouxou, e é a que este guarda existe para travar: para
    visitante e para aluno, área arquivada continua não existindo.
    """
    a = area(visibilidade=Area.Visibilidade.PUBLICA, ativa=False)
    assert pode_ler(a, VISITANTE) is False
    assert pode_ler(a, aluno) is False
    assert pode_ler(a, professor) is True


def test_visibilidade_desconhecida_fecha(aluno):
    """Dado novo com código velho **fecha** — nunca abre.

    Se alguém acrescentar um tipo de visibilidade e esquecer desta função, o
    lado seguro do esquecimento é ninguém entrar.
    """
    a = area(visibilidade=Area.Visibilidade.PUBLICA)
    # Curto de propósito: a coluna é `varchar(10)`, e o próprio banco já recusa
    # valor mais longo — foi assim que a primeira versão deste teste morreu.
    Area.objects.filter(pk=a.pk).update(visibilidade="futuro")
    a.refresh_from_db()
    assert pode_ler(a, aluno) is False


# --------------------------------------------------------------- escrever
def test_ninguem_escreve_onde_nao_pode_ler(cadastrado):
    """Escrever exige, SEMPRE, poder ler antes."""
    a = area(
        visibilidade=Area.Visibilidade.ALUNOS,
        quem_escreve=Area.QuemEscreve.CADASTRADO,
    )
    assert pode_ler(a, cadastrado) is False
    assert pode_escrever(a, cadastrado) is False


def test_em_pagina_publica_so_a_escola_fala(cadastrado, aluno, professor):
    """**O desenho mudou em 30/08/2026, por decisão do mantenedor.**

    Até aqui valia *"todos leem, aluno escreve"*. Ele decidiu o contrário para
    a página pública (registro `20260830-021`): a escola é de Roblox, o público
    é criança e adolescente, e mensagem de menor não fica exposta a estranho
    sem login. O que é aberto ao Google passa a ser **só a escola falando** — e
    o preço, aceito por ele na mesma escolha, é o fórum sair do alcance de
    buscador.

    A combinação antiga (`publica` + escrita de aluno) não é mais só recusada
    aqui: **o banco a recusa** (`Area.Meta.constraints`,
    `pagina_publica_so_a_escola_fala`), e por isso este teste não consegue nem
    montá-la — ver `tests/test_escrever.py`.
    """
    a = area(
        visibilidade=Area.Visibilidade.PUBLICA, quem_escreve=Area.QuemEscreve.EQUIPE
    )
    # Todo mundo lê — a página pública continua pública para LER.
    assert pode_ler(a, VISITANTE) is True
    assert pode_ler(a, cadastrado) is True
    assert pode_ler(a, aluno) is True
    # E ninguém escreve, a não ser a escola.
    assert pode_escrever(a, VISITANTE) is False
    assert pode_escrever(a, cadastrado) is False
    assert pode_escrever(a, aluno) is False
    assert pode_escrever(a, professor) is True


def test_o_aluno_escreve_atras_do_login_na_area_de_alunos(cadastrado, aluno):
    """Onde aluno escreve, exige login — e exige matrícula.

    É o outro lado do teste acima: o mandato não fechou a escrita do aluno,
    mudou o LUGAR dela. `duvidas` e `mostre-seu-trabalho` deixaram de ser
    públicas por isso (ver `apps/forum/management/commands/semear_areas.py`).
    """
    a = area(visibilidade=Area.Visibilidade.ALUNOS, quem_escreve=Area.QuemEscreve.ALUNO)
    assert pode_escrever(a, VISITANTE) is False
    assert pode_escrever(a, cadastrado) is False
    assert pode_escrever(a, aluno) is True


def test_area_de_avisos_so_aceita_a_equipe(aluno, professor):
    """A escola fala, a turma lê."""
    a = area(
        visibilidade=Area.Visibilidade.ALUNOS, quem_escreve=Area.QuemEscreve.EQUIPE
    )
    assert pode_escrever(a, aluno) is False
    assert pode_escrever(a, professor) is True


def test_visitante_nunca_escreve_em_lugar_nenhum():
    """Escrita é SEMPRE atrás do login — inclusive onde o dado diz `cadastrado`.

    O caso que este teste guarda é `quem_escreve="cadastrado"` numa área que
    ninguém trancou: sem o degrau do login em `pode_escrever`, "qualquer pessoa
    com login" seria lido como "qualquer pessoa".
    """
    for visibilidade in Area.Visibilidade.values:
        for quem in Area.QuemEscreve.values:
            # A combinação `publica` + escrita de não-equipe é proibida pelo
            # banco desde 30/08/2026: pular é o que o dado permite existir.
            if visibilidade == Area.Visibilidade.PUBLICA and quem != "equipe":
                continue
            a = area(
                slug=f"v-{visibilidade}-{quem}",
                visibilidade=visibilidade,
                quem_escreve=quem,
                curso_id="c" if visibilidade == Area.Visibilidade.TURMA else "",
            )
            assert pode_escrever(a, VISITANTE) is False, f"{visibilidade}/{quem}"


# --------------------------------------------------------------- a lista
def test_a_lista_de_areas_usa_a_mesma_regra_da_pagina(aluno):
    """Duas expressões da mesma regra divergem; aqui há uma só."""
    publica = area(slug="p", visibilidade=Area.Visibilidade.PUBLICA)
    de_alunos = area(slug="al", visibilidade=Area.Visibilidade.ALUNOS)
    de_turma = area(slug="tu", visibilidade=Area.Visibilidade.TURMA, curso_id="c")

    for quem, esperadas in [
        (VISITANTE, {publica.pk}),
        (aluno, {publica.pk, de_alunos.pk}),
    ]:
        vistas = {a.pk for a in areas_visiveis(quem)}
        assert vistas == esperadas
        assert de_turma.pk not in vistas
