"""As restrições do banco da Fila, e a prova de que elas MORDEM, uma a uma.

Cada `CheckConstraint`, cada `UniqueConstraint`, cada gatilho e cada chave
estrangeira composta de `apps/encomendas/models.py` e da migração `0001` existe
porque uma regra que vive só em código Python é uma promessa: basta um
`objects.update()` numa tela de administração futura, uma migração de dados, ou
uma linha editada à mão no `psql` numa madrugada de incidente, para a combinação
proibida existir sem ninguém saber (`armadilhas/023`,
`docs/decisoes/RETROSPECTIVA-FASE-D.md` §2). Este arquivo confere que o
PostgreSQL recusa.

Aqui isso protege três coisas concretas: o dinheiro de terceiros (a confirmação
de pagamento com autor), a justiça da fila (uma oferta pendente por encomenda e
por aluno) e a fronteira entre escolas (Lei 9).
"""

from datetime import datetime, timedelta, timezone as fuso

import pytest
from django.apps import apps
from django.db import IntegrityError, connection
from django.db import models as campos

from apps.encomendas.models import (
    Encomenda,
    MudancaDeStatus,
    Oferta,
    Parametro,
    PerfilProfissional,
    Pessoa,
)

# A ÚNICA entidade sem `site_id`, e a exceção é de desenho: o espelho copia a
# identidade da PLATAFORMA, que é uma só por pessoa em todos os sites (quem a
# emite é a célula `identidade`). A fronteira de site desta célula mora no
# `PerfilProfissional`, com `Unique(pessoa, site_id)`. Manter a exceção AQUI,
# numa lista de um item, é o que a deixa visível para sempre em vez de virar um
# esquecimento que ninguém nota.
SEM_SITE_ID = {"Pessoa"}

# O `AGORA` DESTES TESTES É O RELÓGIO REAL, e a troca não é estética.
#
# `Oferta.oferecida_em` é `auto_now_add`: quem o preenche é o relógio da
# máquina, nunca o teste. A restrição `oferta_expira_depois_de_oferecida`
# compara os dois. Com um instante FIXO aqui, `expira_em = AGORA + 3h` é um
# instante que o relógio real ultrapassa — e a partir daquele minuto dez testes
# ficam vermelhos sem ninguém ter tocado numa linha de código.
#
# Não é hipótese: aconteceu em 04/09/2026 às 15h UTC, três horas depois de o
# arquivo nascer com `AGORA = datetime(2026, 9, 4, 12, 0)`. A `main` já estava
# com a bomba armada quando o degrau seguinte (o motor, TAR-121) a encontrou.
# `armadilhas/323`.
AGORA = datetime.now(tz=fuso.utc)
SITE = "escola-a"


@pytest.fixture
def pessoa(db):
    return Pessoa.objects.create(id_da_plataforma="pes-1", nome_exibido="Ana")


@pytest.fixture
def perfil(pessoa):
    return PerfilProfissional.objects.create(pessoa=pessoa, site_id=SITE)


def cria_encomenda(**campos_extras):
    padrao = {
        "site_id": SITE,
        "origem": Encomenda.Origem.ESCOLA,
        "cliente_id": "cli-1",
        "cartao": Encomenda.Cartao.ITEM_SIMPLES,
        "nivel": Encomenda.Nivel.INICIANTE,
    }
    padrao.update(campos_extras)
    return Encomenda.objects.create(**padrao)


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
    for modelo in apps.get_app_config("encomendas").get_models():
        if modelo.__name__ in SEM_SITE_ID:
            continue
        nomes = {c.name for c in modelo._meta.get_fields()}
        if "site_id" not in nomes:
            faltando.append(modelo.__name__)

    assert faltando == [], (
        f"tabela sem `site_id`: {faltando}. Lei 9 / [INV-P11]. Se a tabela nova "
        "é mesmo de plataforma inteira, acrescente-a a `SEM_SITE_ID` com o "
        "motivo escrito, no MESMO PR: a exceção precisa ser visível."
    )


def test_a_fronteira_de_site_da_pessoa_mora_no_perfil():
    """A exceção não é um buraco: ela apenas muda de tabela, e a prova é esta."""
    assert "site_id" not in {c.name for c in Pessoa._meta.get_fields()}
    chaves = {
        tuple(c.fields)
        for c in PerfilProfissional._meta.constraints
        if hasattr(c, "fields")
    }
    assert ("pessoa", "site_id") in chaves, (
        "o `PerfilProfissional` deixou de separar os sites. Sem esta unicidade, "
        "a exceção de `Pessoa` vira um vazamento entre escolas (Lei 9)."
    )


def test_um_perfil_por_pessoa_por_site(pessoa, perfil):
    with pytest.raises(IntegrityError):
        PerfilProfissional.objects.create(pessoa=pessoa, site_id=SITE)


def test_a_mesma_pessoa_tem_um_perfil_em_cada_site(pessoa, perfil):
    """A trava é POR SITE, não por pessoa: a Lei 9 é uma fábrica, N lojas."""
    outro = PerfilProfissional.objects.create(pessoa=pessoa, site_id="escola-b")
    assert outro.pk != perfil.pk


def test_oferta_nao_aponta_para_encomenda_de_outro_site(perfil):
    """A chave estrangeira composta: a coluna `site_id` da oferta não pode mentir.

    `armadilhas/274`: denormalizar `site_id` na `Oferta` é o que permite as duas
    travas de oferta pendente (`UniqueConstraint` não atravessa chave
    estrangeira). Coluna denormalizada mente no dia em que alguém a escreve
    errado, e aqui mentir significa uma oferta de uma escola apontando para a
    encomenda de outra, invisível a toda consulta filtrada por site.
    """
    de_outra_escola = cria_encomenda(site_id="escola-b")
    with pytest.raises(IntegrityError, match="oferta_e_encomenda_do_mesmo_site"):
        Oferta.objects.create(
            site_id=SITE,
            encomenda=de_outra_escola,
            aluno=perfil,
            expira_em=AGORA + timedelta(hours=3),
        )


def test_oferta_nao_aponta_para_aluno_de_outro_site(pessoa):
    encomenda = cria_encomenda()
    de_outra_escola = PerfilProfissional.objects.create(
        pessoa=pessoa, site_id="escola-b"
    )
    with pytest.raises(IntegrityError, match="oferta_e_aluno_do_mesmo_site"):
        Oferta.objects.create(
            site_id=SITE,
            encomenda=encomenda,
            aluno=de_outra_escola,
            expira_em=AGORA + timedelta(hours=3),
        )


def test_encomenda_nao_e_atribuida_a_aluno_de_outro_site(pessoa):
    encomenda = cria_encomenda()
    de_outra_escola = PerfilProfissional.objects.create(
        pessoa=pessoa, site_id="escola-b"
    )
    with pytest.raises(IntegrityError, match="encomenda_e_aluno_do_mesmo_site"):
        Encomenda.objects.filter(pk=encomenda.pk).update(aluno=de_outra_escola)


# ---------------------------------------------------------------------------
# A encomenda: cartão, nível e a confirmação de pagamento com autor
# ---------------------------------------------------------------------------


def test_o_cartao_decide_o_nivel(db):
    """ "O cliente nunca escolhe nível de modelador" (plano §5.1), no banco."""
    with pytest.raises(IntegrityError, match="o_cartao_decide_o_nivel"):
        cria_encomenda(
            cartao=Encomenda.Cartao.ITEM_SIMPLES, nivel=Encomenda.Nivel.AVANCADO
        )


def test_a_tabela_de_niveis_do_codigo_e_a_do_banco(db):
    """As três combinações que o banco aceita são as três de `NIVEL_DO_CARTAO`."""
    for cartao, nivel in Encomenda.NIVEL_DO_CARTAO.items():
        assert cria_encomenda(cartao=cartao, nivel=nivel).pk is not None


def test_confirmacao_pelo_plantao_so_para_a_escola(db):
    """O contrato de `encomenda.paga.v1` diz isto com todas as letras.

    Sem a trava, alguém declararia paga à mão a encomenda de um cliente de
    verdade, sem o dinheiro ter entrado, e a fila trabalharia de graça.
    """
    with pytest.raises(
        IntegrityError, match="confirmacao_pelo_plantao_so_para_a_escola"
    ):
        cria_encomenda(
            origem=Encomenda.Origem.FILA,
            confirmacao_de_pagamento=Encomenda.Confirmacao.PLANTAO,
            pagamento_confirmado_em=AGORA,
            pagamento_confirmado_por="prof-1",
        )


def test_confirmacao_do_plantao_exige_autor(db):
    """[INV-ENC-D13] mede a confirmação REGISTRADA COM AUTOR, não o webhook."""
    with pytest.raises(
        IntegrityError, match="confirmacao_de_pagamento_tem_autor_e_data"
    ):
        cria_encomenda(
            origem=Encomenda.Origem.ESCOLA,
            confirmacao_de_pagamento=Encomenda.Confirmacao.PLANTAO,
            pagamento_confirmado_em=AGORA,
            pagamento_confirmado_por="",
        )


def test_confirmacao_pelo_webhook_nao_precisa_de_pessoa(db):
    """O webhook não tem pessoa atrás, e fingir uma seria inventar autoria."""
    encomenda = cria_encomenda(
        origem=Encomenda.Origem.FILA,
        confirmacao_de_pagamento=Encomenda.Confirmacao.WEBHOOK,
        pagamento_confirmado_em=AGORA,
    )
    assert encomenda.pagamento_confirmado_por == ""


def test_confirmacao_sem_data_e_recusada(db):
    with pytest.raises(
        IntegrityError, match="confirmacao_de_pagamento_tem_autor_e_data"
    ):
        cria_encomenda(
            origem=Encomenda.Origem.FILA,
            confirmacao_de_pagamento=Encomenda.Confirmacao.WEBHOOK,
        )


def test_prazo_prometido_nunca_antes_do_de_producao(db):
    with pytest.raises(
        IntegrityError, match="prazo_prometido_nunca_antes_do_de_producao"
    ):
        cria_encomenda(
            prazo_producao_ate=AGORA + timedelta(days=3),
            prazo_prometido_ate=AGORA + timedelta(days=2),
        )


def test_dinheiro_e_inteiro_em_centavos():
    """`contracts/README.md` item 7: float de dinheiro é proibido em contrato.

    Mede a CLASSE do campo, e não o nome: um `DecimalField` chamado
    `preco_cents` passaria por qualquer revisão de nome e quebraria o contrato
    do primeiro evento emitido.
    """
    proibidos = []
    for modelo in apps.get_app_config("encomendas").get_models():
        for campo in modelo._meta.get_fields():
            if isinstance(campo, (campos.FloatField, campos.DecimalField)):
                proibidos.append(f"{modelo.__name__}.{campo.name}")
    assert proibidos == [], (
        f"campo de ponto flutuante nesta célula: {proibidos}. Dinheiro é INTEIRO "
        "em centavos (`contracts/README.md`, item 7)."
    )


# ---------------------------------------------------------------------------
# O perfil profissional
# ---------------------------------------------------------------------------


def test_titulo_de_banca_tem_autor_e_data(perfil):
    """Lei §3.6: o professor dá o título, com data e autor. Título sem autor é
    um título que ninguém deu, e a Banca vai precisar saber de quem herdou."""
    with pytest.raises(IntegrityError, match="titulo_de_banca_tem_autor_e_data"):
        PerfilProfissional.objects.filter(pk=perfil.pk).update(
            titulo_banca=PerfilProfissional.Titulo.NIVEL_1
        )


def test_titulo_de_banca_com_autor_e_data_entra(perfil):
    PerfilProfissional.objects.filter(pk=perfil.pk).update(
        titulo_banca=PerfilProfissional.Titulo.NIVEL_2,
        titulo_dado_por="prof-1",
        titulo_dado_em=AGORA,
    )
    perfil.refresh_from_db()
    assert perfil.titulo_banca == "nivel_2"


def test_pausa_so_existe_em_perfil_pausado(perfil):
    """Duas leituras possíveis do mesmo perfil é o bug que ninguém reproduz."""
    with pytest.raises(IntegrityError, match="pausa_so_existe_em_perfil_pausado"):
        PerfilProfissional.objects.filter(pk=perfil.pk).update(
            pausa_ate=AGORA + timedelta(days=30)
        )


def test_o_perfil_nao_tem_responsavel(perfil):
    """A escola é 18+ (lei §3.1). O campo do plano não existe, e isso é decisão.

    O guarda mede a AUSÊNCIA para que ela não volte por acidente numa migração
    futura: o plano mestre continua pedindo `responsavel_id` em papel, e quem o
    ler sem a lei ao lado vai querer criá-lo.
    """
    nomes = {c.name for c in PerfilProfissional._meta.get_fields()}
    assert "responsavel_id" not in nomes and "responsavel" not in nomes, (
        "a escola é 18+ (lei §3.1, reconfirmada em 03/09/2026). Se a escola "
        "passar a admitir menores, a trava volta ao §3.1 da lei ANTES de o "
        "campo voltar."
    )


# ---------------------------------------------------------------------------
# A oferta: as duas travas de justiça, no banco
# ---------------------------------------------------------------------------


def _oferta(encomenda, aluno, **extras):
    padrao = {
        "site_id": SITE,
        "encomenda": encomenda,
        "aluno": aluno,
        "expira_em": AGORA + timedelta(hours=3),
    }
    padrao.update(extras)
    return Oferta.objects.create(**padrao)


def test_uma_oferta_pendente_por_encomenda(pessoa, perfil):
    """[INV-ENC-J1], no banco (o invariante e o guarda dele nascem no degrau 2.3).

    A trava é do PostgreSQL porque a corrida que ela impede é entre dois
    processos do motor rodando ao mesmo tempo, e nenhum `if` em Python resolve
    isso.
    """
    encomenda = cria_encomenda()
    outro = PerfilProfissional.objects.create(
        pessoa=Pessoa.objects.create(id_da_plataforma="pes-2"), site_id=SITE
    )
    _oferta(encomenda, perfil)
    with pytest.raises(IntegrityError, match="uma_oferta_pendente_por_encomenda"):
        _oferta(encomenda, outro)


def test_uma_oferta_pendente_por_aluno(perfil):
    """[INV-ENC-J2], no banco."""
    primeira = cria_encomenda()
    segunda = cria_encomenda()
    _oferta(primeira, perfil)
    with pytest.raises(IntegrityError, match="uma_oferta_pendente_por_aluno"):
        _oferta(segunda, perfil)


def test_oferta_respondida_libera_a_vaga(perfil):
    """As ofertas fechadas se acumulam de propósito: elas são o histórico."""
    primeira = cria_encomenda()
    segunda = cria_encomenda()
    oferta = _oferta(primeira, perfil)
    oferta.responder(Oferta.Resultado.EXPIROU, em=AGORA)
    assert _oferta(segunda, perfil).pk is not None
    assert Oferta.objects.filter(aluno=perfil).count() == 2


def test_motivo_de_passe_so_em_oferta_passada(perfil):
    encomenda = cria_encomenda()
    with pytest.raises(IntegrityError, match="motivo_de_passe_so_em_oferta_passada"):
        _oferta(
            encomenda,
            perfil,
            motivo_passe=Oferta.MotivoDoPasse.SEM_TEMPO,
        )


def test_oferta_passada_sem_motivo_e_recusada(perfil):
    """Passe sem motivo não alimenta nenhum dos três usos do plano §6.11."""
    encomenda = cria_encomenda()
    oferta = _oferta(encomenda, perfil)
    with pytest.raises(IntegrityError, match="motivo_de_passe_so_em_oferta_passada"):
        Oferta.objects.filter(pk=oferta.pk).update(
            resultado=Oferta.Resultado.PASSOU, respondida_em=AGORA
        )


def test_oferta_respondida_tem_data(perfil):
    encomenda = cria_encomenda()
    oferta = _oferta(encomenda, perfil)
    with pytest.raises(IntegrityError, match="oferta_respondida_tem_data"):
        Oferta.objects.filter(pk=oferta.pk).update(resultado=Oferta.Resultado.ACEITA)


def test_oferta_expira_depois_de_oferecida(perfil):
    encomenda = cria_encomenda()
    oferta = _oferta(encomenda, perfil)
    with pytest.raises(IntegrityError, match="oferta_expira_depois_de_oferecida"):
        Oferta.objects.filter(pk=oferta.pk).update(
            expira_em=oferta.oferecida_em - timedelta(hours=1)
        )


# ---------------------------------------------------------------------------
# O histórico é append-only NO BANCO
# ---------------------------------------------------------------------------


def test_o_historico_de_status_nao_se_edita(perfil):
    """Histórico que pode ser editado não é histórico (`armadilhas/079`).

    Quando uma mediação precisar responder "quem mandou esta encomenda de volta
    para a fila, e quando", esta tabela é a resposta.
    """
    encomenda = cria_encomenda(status=Encomenda.Status.NA_FILA)
    encomenda.mudar_status(Encomenda.Status.CANCELADA, ator_id="prof-1")
    linha = MudancaDeStatus.objects.get(encomenda=encomenda)
    with pytest.raises(IntegrityError, match="append-only"):
        MudancaDeStatus.objects.filter(pk=linha.pk).update(ator_id="outro")


def test_o_historico_de_status_nao_se_apaga(perfil):
    encomenda = cria_encomenda(status=Encomenda.Status.NA_FILA)
    encomenda.mudar_status(Encomenda.Status.CANCELADA)
    with pytest.raises(IntegrityError, match="append-only"):
        MudancaDeStatus.objects.filter(encomenda=encomenda).delete()


def test_a_mudanca_de_status_registra_quem_e_quando(perfil):
    encomenda = cria_encomenda(status=Encomenda.Status.NA_FILA)
    encomenda.mudar_status(
        Encomenda.Status.OFERECIDA, ator_id="", motivo="o motor ofereceu"
    )
    linha = MudancaDeStatus.objects.get(encomenda=encomenda)
    assert (linha.de, linha.para) == ("na_fila", "oferecida")
    # Vazio é o relógio ou o motor, casando com o `ator_id: null` dos eventos.
    assert linha.ator_id == ""
    assert linha.em is not None


def test_o_historico_nao_aponta_para_encomenda_de_outro_site(perfil):
    de_outra_escola = cria_encomenda(site_id="escola-b")
    with pytest.raises(IntegrityError, match="historico_e_encomenda_do_mesmo_site"):
        MudancaDeStatus.objects.create(
            encomenda=de_outra_escola, site_id=SITE, de="na_fila", para="cancelada"
        )


# ---------------------------------------------------------------------------
# Os índices que a guarda de site depende, e que "parecem redundantes"
# ---------------------------------------------------------------------------


def test_os_pares_referenciaveis_continuam_de_pe(db):
    """`uniq_encomenda_id_com_site` e `uniq_perfil_id_com_site` parecem redundantes.

    É essa aparência que faz alguém apagá-los um dia, derrubando as quatro
    chaves estrangeiras compostas sem que nada pareça errado (`armadilhas/274`).
    Este teste é o bilhete que explica por que eles existem.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT conname FROM pg_constraint WHERE conname IN "
            "('uniq_encomenda_id_com_site', 'uniq_perfil_id_com_site', "
            "'oferta_e_encomenda_do_mesmo_site', 'oferta_e_aluno_do_mesmo_site', "
            "'encomenda_e_aluno_do_mesmo_site', 'historico_e_encomenda_do_mesmo_site')"
        )
        achadas = {linha[0] for linha in cursor.fetchall()}
    assert len(achadas) == 6, f"faltam restrições de fronteira de site: {achadas}"
