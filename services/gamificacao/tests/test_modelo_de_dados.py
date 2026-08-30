"""As restrições do banco — e a prova de que elas MORDEM, uma a uma.

Cada `CheckConstraint` e cada `UniqueConstraint` de `apps/gamificacao/models.py`
existe porque uma regra que vive só em código Python é uma promessa: basta um
`objects.update()` numa tela de administração futura, ou uma linha editada à mão
no `psql` numa madrugada de incidente, para a combinação proibida existir sem
ninguém saber. Este arquivo confere que o PostgreSQL recusa.

É o mesmo raciocínio do `pagina_publica_so_a_escola_fala` do fórum, aplicado a
um sistema cujo público é criança e cujas regras protegem dinheiro, idade e
consentimento.
"""

from datetime import date, datetime, timedelta, timezone as fuso_padrao

import pytest
from django.apps import apps
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.gamificacao.models import (
    Concessao,
    ConquistaDefinicao,
    CriterioDesconhecido,
    Forja,
    LancamentoDeXP,
    LigaDefinicao,
    PedidoDeValidacao,
    PerfilJogador,
    Pessoa,
    Sequencia,
    dia_local_de,
)

# A ÚNICA entidade sem `site_id`, e a exceção é do desenho: o espelho copia a
# identidade da PLATAFORMA, que é uma só por pessoa em todos os sites (quem a
# emite é a célula `identidade`). A fronteira de site desta célula mora no
# `PerfilJogador`, com `Unique(pessoa, site_id)` — é assim que o §3 do plano a
# desenhou. Manter a exceção AQUI, numa lista de um item, é o que a deixa
# visível para sempre em vez de virar um esquecimento que ninguém nota.
SEM_SITE_ID = {"Pessoa"}


@pytest.fixture
def aluno(db):
    return Pessoa.objects.create(
        id_da_plataforma="pes-1", email="aluno@exemplo.com", nome_exibido="Aluno"
    )


def _conquista(**campos):
    padrao = {
        "slug": "medalha-teste",
        "site_id": "escola-a",
        "nome": "Medalha de teste",
        "classe": ConquistaDefinicao.Classe.MEDALHA,
        "familia": ConquistaDefinicao.Familia.OFICIO,
    }
    padrao.update(campos)
    return ConquistaDefinicao.objects.create(**padrao)


# ---------------------------------------------------------------------------
# Lei 9 / [INV-P11] — a fronteira de site
# ---------------------------------------------------------------------------


def test_site_id_em_toda_entidade():
    """Nenhuma tabela nova entra nesta célula sem fronteira de site.

    Lei 9: um deploy, N lojas. Dado de um site que aparece em outro é o
    vazamento clássico de multi-tenant, e ele é silencioso até acontecer em
    público.
    """
    faltando = []
    for modelo in apps.get_app_config("gamificacao").get_models():
        if modelo.__name__ in SEM_SITE_ID:
            continue
        campos = {c.name for c in modelo._meta.get_fields()}
        if "site_id" not in campos:
            faltando.append(modelo.__name__)

    assert faltando == [], (
        f"tabela sem `site_id`: {faltando}. Lei 9 / [INV-P11]: o `site_id` "
        "acompanha toda entidade. Se a tabela nova é mesmo de plataforma "
        "inteira, acrescente-a a `SEM_SITE_ID` com o motivo escrito, no MESMO "
        "PR — a exceção precisa ser visível, não silenciosa."
    )


def test_a_fronteira_de_site_da_pessoa_mora_no_perfil():
    """A exceção não é um buraco: ela apenas muda de tabela, e a prova é esta.

    `Pessoa` não tem `site_id` porque o espelho copia a identidade da
    PLATAFORMA, que é uma só por pessoa em todos os sites. Quem separa os sites
    é o `PerfilJogador`, e ele o faz com uma restrição de UNICIDADE — não com um
    campo solto que alguém poderia esquecer de filtrar.
    """
    campos_da_pessoa = {c.name for c in Pessoa._meta.get_fields()}
    assert "site_id" not in campos_da_pessoa

    chaves = {
        tuple(c.fields) for c in PerfilJogador._meta.constraints if hasattr(c, "fields")
    }
    assert ("pessoa", "site_id") in chaves, (
        "o `PerfilJogador` deixou de separar os sites. Sem esta unicidade, a "
        "exceção de `Pessoa` vira um vazamento entre escolas (Lei 9)."
    )


# ---------------------------------------------------------------------------
# A hierarquia da lei virando restrição: marco real rende ZERO XP
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_o_banco_recusa_um_marco_real_que_pague_xp():
    """Decisão fechada 7 da Sessão A: marco real vale 0 XP.

    Se conseguir o primeiro cliente pagasse 500 XP, o marco viraria mais um item
    do andaime, e o aluno aprenderia a perseguir o número em vez da coisa. A
    hierarquia inteira (`Realidade > Criação > Maestria > Comunidade > XP`)
    depende desta linha.
    """
    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            _conquista(
                slug="primeiro-cliente",
                classe=ConquistaDefinicao.Classe.MARCO,
                familia=ConquistaDefinicao.Familia.CARREIRA,
                pontos=500,
            )

    assert "marco_real_rende_zero_xp" in str(erro.value)


@pytest.mark.django_db
def test_marco_real_com_zero_xp_entra_normalmente():
    """A contraprova: a restrição recusa o proibido, não a tabela inteira."""
    marco = _conquista(
        slug="portfolio-publicado",
        classe=ConquistaDefinicao.Classe.MARCO,
        familia=ConquistaDefinicao.Familia.CARREIRA,
        pontos=0,
        cristais=0,
    )
    assert marco.pk and marco.pontos == 0


@pytest.mark.django_db
def test_o_banco_recusa_marco_de_dinheiro_fora_da_faixa_de_13_anos():
    """Lei §9: marco que envolve dinheiro é 13+, e é SEMPRE adulto quem valida.

    A trava está no banco porque a alternativa seria confiar em toda tela futura
    lembrar da regra, e o custo do esquecimento cai sobre uma criança.
    """
    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            _conquista(
                slug="primeiros-dolares",
                classe=ConquistaDefinicao.Classe.MARCO,
                familia=ConquistaDefinicao.Familia.CARREIRA,
                envolve_dinheiro=True,
                faixa_etaria=ConquistaDefinicao.FaixaEtaria.TODAS,
                exige_validador_adulto=True,
            )

    assert "marco_de_dinheiro_e_13mais_e_so_adulto_valida" in str(erro.value)


@pytest.mark.django_db
def test_o_banco_recusa_marco_de_dinheiro_validavel_por_colega():
    """A outra metade da mesma trava: 13+ não basta, precisa do adulto."""
    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            _conquista(
                slug="primeiro-cliente",
                classe=ConquistaDefinicao.Classe.MARCO,
                familia=ConquistaDefinicao.Familia.CARREIRA,
                envolve_dinheiro=True,
                faixa_etaria=ConquistaDefinicao.FaixaEtaria.TREZE_MAIS,
                exige_validador_adulto=False,
            )

    assert "marco_de_dinheiro_e_13mais_e_so_adulto_valida" in str(erro.value)


# ---------------------------------------------------------------------------
# O critério é vocabulário FECHADO, não DSL (critério de morte nº 1)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_criterio_fora_do_vocabulario_e_recusado():
    """A porta onde o motor de regras genérico bateria, e onde ele para."""
    with pytest.raises(CriterioDesconhecido) as erro:
        _conquista(criterio={"tipo": "expressao", "codigo": "xp > 100 and nivel < 3"})

    assert "vocabulário fechado" in str(erro.value)


@pytest.mark.django_db
def test_criterio_do_vocabulario_entra_normalmente():
    conquista = _conquista(criterio={"tipo": "forjas_seladas", "alvo": 10})
    assert conquista.criterio["tipo"] == "forjas_seladas"


# ---------------------------------------------------------------------------
# As quatro ligas, e o Diamante que está proibido
# ---------------------------------------------------------------------------


def test_as_ligas_sao_exatamente_bronze_prata_ouro_e_platina():
    """Decisão 1 do mantenedor na Sessão A. Diamante colidiria com os Cristais."""
    tiers = {valor for valor, _ in LigaDefinicao.Tier.choices}

    assert tiers == {"bronze", "prata", "ouro", "platina"}, (
        f"o conjunto de ligas mudou: {sorted(tiers)}. Diamante está PROIBIDO "
        "(ele colide com os Cristais, que são a moeda)."
    )


@pytest.mark.django_db
def test_o_banco_recusa_uma_liga_diamante():
    """SQL cru também é recusado: a decisão mora no PostgreSQL."""
    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO gamificacao_ligadefinicao "
                    "(slug, site_id, tier, ordem, limiar_de_promocao, "
                    " tamanho_do_grupo, ativa, versao) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    ["diamante", "escola-a", "diamante", 5, 2000, 15, False, 1],
                )

    assert "tier_de_liga_e_um_dos_quatro" in str(erro.value)


def test_nao_existe_rebaixamento_no_modelo_de_liga():
    """Ninguém desce por ter tido uma semana ruim, e a garantia é a ausência.

    O limiar de promoção é ABSOLUTO (faça X pontos e suba), não relativo (os
    três primeiros sobem, os três últimos descem). Um campo `rebaixado` seria a
    primeira peça da versão relativa.
    """
    from apps.gamificacao.models import ParticipacaoNaLiga

    campos = {c.name for c in ParticipacaoNaLiga._meta.get_fields()}
    proibidos = {"rebaixado", "rebaixada", "rebaixamento", "queda", "descenso"}

    assert not (campos & proibidos), (
        f"nasceu rebaixamento na liga: {sorted(campos & proibidos)}. A liga não "
        "rebaixa: o limiar é absoluto (lei da Sessão A)."
    )


# ---------------------------------------------------------------------------
# O ledger: idempotência por construção e quarentena com data para acabar
# ---------------------------------------------------------------------------


def _lancamento(aluno, **campos):
    padrao = {
        "pessoa": aluno,
        "site_id": "escola-a",
        "pontos": 30,
        "origem_event_id": "evt-1",
        "regra_slug": "quiz-aprovado",
        "regra_versao": 1,
        "occurred_at": timezone.now(),
        "dia_local": timezone.localdate(),
    }
    padrao.update(campos)
    return LancamentoDeXP.objects.create(**padrao)


def test_o_mesmo_evento_nao_paga_duas_vezes(aluno):
    """Idempotência POR CONSTRUÇÃO: o banco não deixa, e não é o código que lembra.

    Evento reentregue é o caso normal de uma fila, não a exceção.
    """
    _lancamento(aluno)

    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            _lancamento(aluno)

    assert "um_lancamento_por_evento_por_regra_por_pessoa" in str(erro.value)


def test_o_mesmo_evento_paga_duas_pessoas_por_regras_distintas(aluno):
    """A razão de a chave ter TRÊS colunas, e não uma.

    Um voto credita quem votou (uma regra) e quem escreveu (outra regra). Uma
    chave só em `origem_event_id` transformaria isso num bug de "sumiu meu XP".
    """
    outro = Pessoa.objects.create(id_da_plataforma="pes-2", email="b@exemplo.com")
    _lancamento(aluno, regra_slug="voto-dado", pontos=2)
    segundo = _lancamento(outro, regra_slug="sugestao-votada", pontos=5)

    assert segundo.pk
    assert LancamentoDeXP.objects.filter(origem_event_id="evt-1").count() == 2


def test_quarentena_sem_data_de_liberacao_e_recusada(aluno):
    """Quarentena sem prazo é quarentena eterna: o aluno nunca veria o ponto."""
    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            _lancamento(aluno, status=LancamentoDeXP.Status.PENDENTE, liberado_em=None)

    assert "quarentena_tem_data_para_acabar" in str(erro.value)


def test_o_dia_do_lancamento_e_o_dia_de_sao_paulo():
    """`dia_local` é materializado, e materializado no fuso certo.

    Dois instantes, escolhidos para trocar de DIA. Com o fuso errado, o esforço
    da madrugada cairia no dia anterior e a Sequência quebraria para quem não
    faltou (`armadilhas/099`).
    """
    # 04:00 UTC é 25/08 01:00 em São Paulo (e 24/08 23:00 em Chicago, o default
    # de fábrica do Django).
    de_madrugada = datetime(2026, 8, 25, 4, 0, tzinfo=fuso_padrao.utc)
    assert dia_local_de(de_madrugada) == date(2026, 8, 25)

    # 02:00 UTC é 24/08 23:00 em São Paulo. Aqui o dia local DIFERE do dia em
    # UTC — é o que prova que a conta é o fuso, e não um `.date()` disfarçado.
    tarde_da_noite = datetime(2026, 8, 25, 2, 0, tzinfo=fuso_padrao.utc)
    assert tarde_da_noite.date() == date(2026, 8, 25)
    assert dia_local_de(tarde_da_noite) == date(2026, 8, 24)


# ---------------------------------------------------------------------------
# Perfil, sequência, forja, concessão e fila de validação
# ---------------------------------------------------------------------------


def test_um_perfil_por_pessoa_por_site(aluno):
    PerfilJogador.objects.create(pessoa=aluno, site_id="escola-a")
    # Site diferente é perfil diferente, e isso é a Lei 9 funcionando.
    PerfilJogador.objects.create(pessoa=aluno, site_id="escola-b")

    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            PerfilJogador.objects.create(pessoa=aluno, site_id="escola-a")

    assert "um_perfil_por_pessoa_por_site" in str(erro.value)


def test_o_perfil_nasce_no_modo_junior_e_fora_das_ligas(aluno):
    """Fail-closed é o lado protegido: júnior por padrão, liga desligada.

    Um perfil que nascesse `teen` por omissão daria ao menor tudo o que o Modo
    Júnior existe para não dar (lei §9).
    """
    perfil = PerfilJogador.objects.create(pessoa=aluno, site_id="escola-a")

    assert perfil.modo == PerfilJogador.Modo.JUNIOR
    assert perfil.participa_de_ligas is False
    assert perfil.celebracoes_pendentes == []


def test_a_sequencia_recusa_recorde_menor_que_a_contagem_atual(aluno):
    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            Sequencia.objects.create(
                pessoa=aluno,
                site_id="escola-a",
                semana_corrente=timezone.localdate(),
                semanas_atuais=5,
                recorde_semanas=2,
            )

    assert "o_recorde_nunca_e_menor_que_a_sequencia_atual" in str(erro.value)


def test_a_sequencia_recusa_meta_que_nao_cabe_numa_semana(aluno):
    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            Sequencia.objects.create(
                pessoa=aluno,
                site_id="escola-a",
                semana_corrente=timezone.localdate(),
                meta_dias=9,
            )

    assert "meta_da_semana_cabe_numa_semana" in str(erro.value)


def test_a_forja_recusa_medidor_acima_do_teto(aluno):
    """O medidor só cresce, e cresce até um teto: senão vira competição de cliques."""
    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            Forja.objects.create(
                pessoa=aluno,
                site_id="escola-a",
                desafio_ref="d-1",
                medidor=100,
                teto=10,
            )

    assert "o_medidor_da_forja_respeita_o_teto" in str(erro.value)


def test_a_concessao_nasce_privada(aluno):
    """Decisão fechada 7: consentimento padrão é PRIVADO.

    Nada é exposto sem ação explícita do aluno. O default fechado é o que impede
    uma tela nova de publicar conquista de criança por omissão.
    """
    conquista = _conquista()
    concessao = Concessao.objects.create(
        pessoa=aluno, site_id="escola-a", conquista=conquista
    )

    assert concessao.consentimento == Concessao.Consentimento.PRIVADO
    assert concessao.validador_papel == Concessao.PapelDoValidador.SISTEMA


def test_concessao_humana_sem_validador_e_recusada(aluno):
    """Quando um marco é contestado, "quem disse que sim?" precisa ter resposta."""
    conquista = _conquista()

    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            Concessao.objects.create(
                pessoa=aluno,
                site_id="escola-a",
                conquista=conquista,
                validador_papel=Concessao.PapelDoValidador.PAR,
                validador_id="",
            )

    assert "concessao_humana_diz_quem_validou" in str(erro.value)


def test_devolucao_sem_motivo_estruturado_e_recusada(aluno):
    """ "Não" sem razão, vindo de um colega, é bullying com verniz de processo."""
    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            PedidoDeValidacao.objects.create(
                pessoa=aluno,
                site_id="escola-a",
                tipo=PedidoDeValidacao.Tipo.OBRA,
                estado=PedidoDeValidacao.Estado.DEVOLVIDO,
                motivo_da_devolucao="",
            )

    assert "motivo_da_devolucao_e_obrigatorio" in str(erro.value)


def test_o_pedido_nasce_em_analise_e_com_evidencia_privada(aluno):
    """ "Em análise" nunca parece recusa, e a evidência nasce fora do alcance dos pares."""
    pedido = PedidoDeValidacao.objects.create(
        pessoa=aluno,
        site_id="escola-a",
        tipo=PedidoDeValidacao.Tipo.MARCO,
        prazo_ate=timezone.now() + timedelta(days=5),
    )

    assert pedido.estado == PedidoDeValidacao.Estado.EM_ANALISE
    assert pedido.evidencia_privada is True
    assert pedido.escalado_para_adulto is False
