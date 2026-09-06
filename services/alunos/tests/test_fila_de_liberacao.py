"""A fila de liberação — `docs/decisoes/DECISAO-fila-de-liberacao.md`.

O teste mais importante deste arquivo não é nenhuma das três portas novas: é
`test_matricula_aguardando_nao_abre_a_caixa`. A lei §3 mediu que
`GET /alunos/{email}/matriculas` filtrava só por e-mail, sem status, e que a
Caixa de Sugestões faz `bool(...)` de qualquer linha devolvida — então o status
`aguardando` NÃO PODE existir no banco antes de a consulta de acesso passar a
excluí-lo. As duas coisas entram no mesmo PR, e é este arquivo que prova.
"""

import json
from datetime import date, timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.matriculas.handlers import ao_pagamento_aprovado
from apps.matriculas.models import Matricula
from apps.matriculas.services import (
    OrderIdReservado,
    entrar_na_fila,
    matricular,
)

PRE_MATRICULAS = "/api/alunos/pre-matriculas"

# [INV-ALU-C1] Desde 06/09/2026 liberar exige dizer o curso
# (`docs/decisoes/DECISAO-cursos-matriculas-e-alunos.md`). Aqui vale qualquer
# texto opaco: o valor de verdade e um id de produto do `catalogo`, e quem prova
# a exigencia e `tests/test_inv_alu_c1_a_matricula_diz_o_curso.py`.
CURSO = "produto-do-curso-1"


@pytest.fixture
def token_valido(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


@pytest.fixture
def auth(token_valido):
    return {"HTTP_AUTHORIZATION": f"Bearer {token_valido}"}


def post(client, url, corpo, auth):
    return client.post(
        url, data=json.dumps(corpo), content_type="application/json", **auth
    )


def na_fila(client, auth, site_id="site-1", status=None):
    url = f"{PRE_MATRICULAS}?site_id={site_id}"
    if status:
        url += f"&status={status}"
    return client.get(url, **auth).json()


def pedir_entrada(client, auth, **campos):
    corpo = {
        "site_id": "site-1",
        "email": "quem-espera@example.com",
        "nome_completo": "Quem Espera",
        "whatsapp": "(96) 99999-0000",
    }
    corpo.update(campos)
    return post(client, PRE_MATRICULAS, corpo, auth)


# ---------------------------------------------------------------------------
# A ARMADILHA (lei §3): quem está na fila NÃO entra na Caixa
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_matricula_aguardando_nao_abre_a_caixa(client, auth):
    """O teste que sabota: existe linha para este e-mail, e mesmo assim a porta
    que decide acesso responde 404 — que o cliente da Caixa traduz para lista
    vazia, o caminho de quem ainda não é aluno."""
    resposta = pedir_entrada(client, auth)
    assert resposta.status_code == 201

    matricula = Matricula.objects.get(email="quem-espera@example.com")
    assert matricula.status == Matricula.STATUS_AGUARDANDO

    acesso = client.get("/api/alunos/alunos/quem-espera@example.com/matriculas", **auth)
    assert acesso.status_code == 404, (
        "uma matrícula `aguardando` abriu a Caixa de Sugestões — é exatamente o "
        "vazamento de acesso que a lei §3 mandou fechar no MESMO PR"
    )


@pytest.mark.django_db
def test_matricula_recusada_nao_abre_a_caixa(client, auth):
    pedir_entrada(client, auth)
    linha = Matricula.objects.get(email="quem-espera@example.com")
    post(
        client,
        f"{PRE_MATRICULAS}/{linha.pk}/decisao",
        {"decisao": "recusar", "decidido_por": "admin-1", "motivo": "não é aluno"},
        auth,
    )

    acesso = client.get("/api/alunos/alunos/quem-espera@example.com/matriculas", **auth)
    assert acesso.status_code == 404


@pytest.mark.django_db
def test_liberar_abre_a_caixa_sem_mais_nenhuma_mudanca(client, auth):
    """A consequência que torna a decisão barata (lei §2): liberar é mudar o
    status, e a resposta da porta de acesso muda sozinha."""
    pedir_entrada(client, auth)
    linha = Matricula.objects.get(email="quem-espera@example.com")
    assert (
        client.get(
            "/api/alunos/alunos/quem-espera@example.com/matriculas", **auth
        ).status_code
        == 404
    )

    decisao = post(
        client,
        f"{PRE_MATRICULAS}/{linha.pk}/decisao",
        {"decisao": "liberar", "decidido_por": "admin-1", "product_id": CURSO},
        auth,
    )
    assert decisao.status_code == 200

    acesso = client.get("/api/alunos/alunos/quem-espera@example.com/matriculas", **auth)
    assert acesso.status_code == 200
    assert acesso.json()[0]["status"] == Matricula.STATUS_ATIVA


@pytest.mark.django_db
def test_status_novo_nasce_sem_acesso(client, auth):
    """O MECANISMO, não a promessa: todo status declarado precisa dizer se DÁ
    ACESSO ou não. Quem inventar um status novo e não decidir de que lado ele
    fica reprova aqui — em vez de descobrir em produção que uma lista de
    exclusão o deixou passar.

    **Os baldes mudaram de nome em 28/08/2026, e o guarda ficou mais forte, não
    mais fraco.** Até então eram `STATUS_QUE_VALEM` e `STATUS_DA_FILA`, e os
    dois cobriam o vocabulário inteiro por coincidência: tudo que não dava
    acesso estava na fila. Com `suspensa` deixando de dar acesso sem entrar na
    fila (`DECISAO-gestao-de-alunos` §2), apareceu um terceiro caso — e a
    pergunta que importa nunca foi "está na fila?", e sim "dá acesso?".
    `STATUS_SEM_ACESSO` responde exatamente essa.
    """
    declarados = {valor for valor, _ in Matricula.STATUS_CHOICES}
    valem = set(Matricula.STATUS_QUE_VALEM)
    sem_acesso = set(Matricula.STATUS_SEM_ACESSO)

    assert valem | sem_acesso == declarados, (
        "status declarado sem resposta para 'dá acesso?': ponha-o em "
        "STATUS_QUE_VALEM ou em STATUS_SEM_ACESSO — sobrando: "
        f"{declarados - valem - sem_acesso}"
    )
    assert not (
        valem & sem_acesso
    ), "um status não pode dar e negar acesso ao mesmo tempo"
    # E a fila continua sendo um subconjunto de quem não tem acesso — nunca o
    # contrário. Se alguém puser um status da fila em QUE_VALEM, o de cima já
    # reprova; este nomeia o erro.
    assert set(Matricula.STATUS_DA_FILA) <= sem_acesso


@pytest.mark.django_db
def test_whatsapp_nunca_sai_por_get_matriculas(client, auth):
    """Lei §5: o número mora ao lado da matrícula e SÓ a porta do admin o
    devolve. A asserção é sobre o conjunto EXATO de chaves — um campo novo que
    vaze para esta resposta reprova mesmo que ninguém lembre de procurá-lo."""
    pedir_entrada(client, auth, whatsapp="(96) 98888-1111")
    linha = Matricula.objects.get(email="quem-espera@example.com")
    post(
        client,
        f"{PRE_MATRICULAS}/{linha.pk}/decisao",
        {"decisao": "liberar", "decidido_por": "admin-1", "product_id": CURSO},
        auth,
    )

    corpo = client.get(
        "/api/alunos/alunos/quem-espera@example.com/matriculas", **auth
    ).json()
    assert set(corpo[0]) == {
        "site_id",
        "order_id",
        "product_id",
        "status",
        "enrolled_at",
    }
    assert "98888" not in json.dumps(corpo)


# ---------------------------------------------------------------------------
# POST /pre-matriculas — entrar na fila
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_entrar_na_fila_cria_linha_aguardando_com_order_id_sintetico(client, auth):
    resposta = pedir_entrada(
        client, auth, comprou_em="2026-08-01", turma="Turma de agosto"
    )
    assert resposta.status_code == 201

    linha = Matricula.objects.get(email="quem-espera@example.com")
    assert linha.status == Matricula.STATUS_AGUARDANDO
    assert linha.order_id.startswith(Matricula.PREFIXO_DA_FILA)
    assert linha.name == "Quem Espera"
    assert linha.whatsapp == "(96) 99999-0000"
    assert linha.comprou_em == date(2026, 8, 1)
    assert linha.turma == "Turma de agosto"


@pytest.mark.django_db
def test_reenviar_atualiza_e_nao_duplica(client, auth):
    assert pedir_entrada(client, auth).status_code == 201
    segunda = pedir_entrada(client, auth, whatsapp="(96) 97777-2222")
    assert segunda.status_code == 200

    assert Matricula.objects.filter(email="quem-espera@example.com").count() == 1
    assert Matricula.objects.get().whatsapp == "(96) 97777-2222"


@pytest.mark.django_db
def test_recusado_que_reenvia_volta_para_a_fila_sem_o_motivo_antigo(client, auth):
    """Lei §7: V1 não edita dados — correção é o admin recusar e a pessoa
    reenviar. O motivo da recusa anterior não pode ficar pendurado na linha."""
    pedir_entrada(client, auth)
    linha = Matricula.objects.get()
    post(
        client,
        f"{PRE_MATRICULAS}/{linha.pk}/decisao",
        {"decisao": "recusar", "decidido_por": "admin-1", "motivo": "faltou o DDD"},
        auth,
    )

    assert pedir_entrada(client, auth, whatsapp="(96) 96666-3333").status_code == 200

    linha.refresh_from_db()
    assert linha.status == Matricula.STATUS_AGUARDANDO
    assert linha.motivo_recusa == ""
    assert linha.decidido_em is None
    assert linha.decidido_por == ""
    assert Matricula.objects.count() == 1


@pytest.mark.django_db
def test_quem_ja_tem_matricula_que_vale_recebe_409(client, auth):
    matricular(
        site_id="site-1",
        order_id="pedido-real-1",
        product_id="curso",
        email="ja-e-aluno@example.com",
        name="Já É Aluno",
    )
    resposta = pedir_entrada(client, auth, email="ja-e-aluno@example.com")
    assert resposta.status_code == 409
    assert Matricula.objects.filter(status=Matricula.STATUS_AGUARDANDO).count() == 0


@pytest.mark.django_db
def test_o_reembolsado_nao_entra_e_tambem_nao_pede_para_voltar(client, auth):
    """[REEMBOLSO] O 409 da fila passou a ter DUAS razões, e esta é a nova.

    Até 31/08/2026 este teste media outra coisa: `reembolsada` VALIA como
    acesso, e a fila a barrava por "você já tem". As duas consultas eram a
    mesma, e o teste existia para provar isso — se divergissem, existiria
    gente recusada na fila por "você já tem acesso" que a Caixa não deixa
    entrar.

    Agora elas divergem DE PROPÓSITO, e a divergência é a decisão do
    mantenedor: o reembolsado não entra E não pede para voltar. Isso não
    recria o beco que o teste antigo temia, porque o beco é EXPLICADO: a tela
    dele nomeia o reembolso e diz o caminho de volta (comprar de novo, ou
    falar com a escola). Beco mudo é defeito; beco explicado é decisão.

    A recusa é medida AQUI, na porta, e não na tela que esconde o formulário:
    um POST direto furaria uma regra que só existisse em template.
    """
    matricula = matricular(
        site_id="site-1",
        order_id="pedido-reembolsado",
        product_id="curso",
        email="reembolsado@example.com",
        name="Reembolsado",
    )[0]
    matricula.status = Matricula.STATUS_REEMBOLSADA
    matricula.save(update_fields=["status"])

    assert (
        pedir_entrada(client, auth, email="reembolsado@example.com").status_code == 409
    )
    # E nenhuma linha da fila nasceu com a tentativa: recusar e criar mesmo
    # assim deixaria a pessoa aparecendo no painel dele como se esperasse.
    assert Matricula.objects.filter(status=Matricula.STATUS_AGUARDANDO).count() == 0
    # A porta de acesso, do outro lado, já não devolve a matrícula: 404.
    assert (
        client.get(
            "/api/alunos/alunos/reembolsado@example.com/matriculas", **auth
        ).status_code
        == 404
    )


@pytest.mark.django_db
def test_o_ex_aluno_continua_podendo_pedir_para_voltar(client, auth):
    """O outro lado da regra acima, e o que a torna uma decisão e não um corte.

    `encerrada` fica FORA de `STATUS_QUE_BARRAM_A_FILA` de propósito
    (`DECISAO-a-ficha-nao-se-apaga.md` §3). Sem este teste, alguém poderia
    "simplificar" a lista para "todo mundo que já teve ficha" e o ex-aluno
    perderia o botão de voltar sem que nada ficasse vermelho.
    """
    matricula = matricular(
        site_id="site-1",
        order_id="pedido-ex-aluno",
        product_id="curso",
        email="ex-aluno@example.com",
        name="Ex-aluno",
    )[0]
    matricula.status = Matricula.STATUS_ENCERRADA
    matricula.save(update_fields=["status"])

    assert pedir_entrada(client, auth, email="ex-aluno@example.com").status_code in (
        200,
        201,
    )


@pytest.mark.django_db
def test_e_mail_e_normalizado_para_a_caixa_encontrar_depois(client, auth):
    """A Caixa pergunta por `email.strip().lower()`. Uma linha gravada com
    maiúsculas seria liberada e continuaria invisível para ela."""
    assert (
        pedir_entrada(client, auth, email="  Quem.Espera@Example.COM ").status_code
        == 201
    )
    assert Matricula.objects.get().email == "quem.espera@example.com"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "corpo_ruim",
    [
        pytest.param({"whatsapp": ""}, id="whatsapp-vazio"),
        pytest.param({"nome_completo": "   "}, id="nome-em-branco"),
        pytest.param({"comprou_em": "01/08/2026"}, id="data-fora-do-formato"),
        pytest.param({"telefone": "(96) 99999-0000"}, id="chave-desconhecida"),
    ],
)
def test_payload_invalido_e_422(client, auth, corpo_ruim):
    assert pedir_entrada(client, auth, **corpo_ruim).status_code == 422
    assert Matricula.objects.count() == 0


@pytest.mark.django_db
def test_campo_obrigatorio_ausente_e_422(client, auth):
    resposta = post(
        client, PRE_MATRICULAS, {"site_id": "site-1", "email": "x@example.com"}, auth
    )
    assert resposta.status_code == 422


@pytest.mark.django_db
def test_duas_linhas_na_fila_para_o_mesmo_par_sao_impossiveis(client, auth):
    """A idempotência de (site_id, email) tem MECANISMO — constraint parcial —
    e não só o 'já existe?' do serviço, que duas requisições simultâneas
    atravessariam juntas."""
    pedir_entrada(client, auth)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Matricula.objects.create(
                site_id="site-1",
                order_id="pre:outro-uuid",
                email="quem-espera@example.com",
                name="Quem Espera De Novo",
                status=Matricula.STATUS_AGUARDANDO,
            )


# ---------------------------------------------------------------------------
# GET /pre-matriculas — a porta do painel
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_fila_devolve_whatsapp_e_dias_de_espera(client, auth):
    pedir_entrada(client, auth, comprou_em="2026-08-01", turma="Turma de agosto")
    linha = Matricula.objects.get()
    Matricula.objects.filter(pk=linha.pk).update(
        enrolled_at=timezone.now() - timedelta(days=7)
    )

    corpo = na_fila(client, auth)
    assert len(corpo) == 1
    assert corpo[0]["whatsapp"] == "(96) 99999-0000"
    assert corpo[0]["nome_completo"] == "Quem Espera"
    assert corpo[0]["esperando_ha_dias"] == 7
    assert corpo[0]["comprou_em"] == "2026-08-01"
    assert corpo[0]["turma"] == "Turma de agosto"
    assert corpo[0]["motivo_recusa"] is None
    assert set(corpo[0]) == {
        "id",
        "site_id",
        "email",
        "nome_completo",
        "whatsapp",
        "comprou_em",
        "turma",
        "status",
        "criada_em",
        "esperando_ha_dias",
        "motivo_recusa",
        # [VOLTAR] Os tres de 29/08/2026 (`DECISAO-a-ficha-nao-se-apaga.md`):
        # o passado da pessoa nesta plataforma, para o painel nao decidir sobre
        # um ex-aluno achando que e gente nova. O conjunto e EXATO de proposito
        # — campo novo nesta porta e PII a mais viajando, e precisa passar por
        # alguem que decida isso.
        "ja_foi_aluno",
        "passagens_anteriores",
        "saiu_em",
    }


@pytest.mark.django_db
def test_os_opcionais_em_branco_saem_como_nulo(client, auth):
    """O contrato diz `type: [string, null]`. No banco eles são "" (evitar
    NULL em CharField é convenção do Django), e a tradução acontece na borda."""
    pedir_entrada(client, auth)
    linha = na_fila(client, auth)[0]
    assert linha["turma"] is None
    assert linha["comprou_em"] is None


@pytest.mark.django_db
def test_quem_espera_ha_mais_tempo_vem_primeiro(client, auth):
    pedir_entrada(client, auth, email="recente@example.com")
    pedir_entrada(client, auth, email="antigo@example.com")
    Matricula.objects.filter(email="antigo@example.com").update(
        enrolled_at=timezone.now() - timedelta(days=30)
    )

    emails = [linha["email"] for linha in na_fila(client, auth)]
    assert emails == ["antigo@example.com", "recente@example.com"], (
        "a fila precisa mostrar quem espera há mais tempo primeiro — é o que "
        "impede uma enxurrada de spam de esconder o aluno de verdade"
    )


@pytest.mark.django_db
def test_a_fila_e_escopada_por_site(client, auth):
    pedir_entrada(client, auth, site_id="site-1", email="a@example.com")
    pedir_entrada(client, auth, site_id="site-2", email="b@example.com")

    assert [l["email"] for l in na_fila(client, auth, site_id="site-1")] == [
        "a@example.com"
    ]
    assert [l["email"] for l in na_fila(client, auth, site_id="site-2")] == [
        "b@example.com"
    ]


@pytest.mark.django_db
def test_a_fila_mostra_recusadas_so_quando_pedido(client, auth):
    pedir_entrada(client, auth)
    linha = Matricula.objects.get()
    post(
        client,
        f"{PRE_MATRICULAS}/{linha.pk}/decisao",
        {"decisao": "recusar", "decidido_por": "admin-1", "motivo": "não é aluno"},
        auth,
    )

    assert na_fila(client, auth) == []
    recusadas = na_fila(client, auth, status="recusada")
    assert len(recusadas) == 1
    assert recusadas[0]["motivo_recusa"] == "não é aluno"


@pytest.mark.django_db
def test_status_fora_do_enum_cai_no_padrao_em_vez_de_esconder_a_fila(client, auth):
    pedir_entrada(client, auth)
    assert len(na_fila(client, auth, status="ativa")) == 1


@pytest.mark.django_db
def test_a_fila_nao_mostra_matricula_paga(client, auth):
    matricular(
        site_id="site-1",
        order_id="pedido-real-2",
        product_id="curso",
        email="pagou@example.com",
        name="Pagou",
    )
    assert na_fila(client, auth) == []


@pytest.mark.django_db
def test_a_fila_SEM_site_id_deixou_de_ser_erro_por_decisao(client, auth):
    """Este teste afirmava 422 até 28/08/2026, e a mudança é DELIBERADA.

    A `DECISAO-categorias-de-usuario` (Rito de Contrato, mantenedor presente)
    tornou `site_id` opcional: o painel do dono é plataforma-inteira (Lei 9), e
    exigir dele o código interno de uma escola para ver quem espera seria pedir
    que ele guardasse um identificador opaco.

    O teste não foi apagado — foi reapontado para a regra nova, e continua
    tendo dentes: se alguém devolver 422 de novo, ou devolver 200 com lista
    vazia (o que `.filter(site_id=None)` faria), ele fica vermelho. Vazio e
    "todas" são as duas respostas possíveis aqui, e só uma está certa.
    """
    pedir_entrada(client, auth, site_id="escola-a", email="a@example.com")
    resposta = client.get(PRE_MATRICULAS, **auth)
    assert resposta.status_code == 200, resposta.content
    assert len(resposta.json()) == 1, "sem site_id a fila voltou vazia"


# ---------------------------------------------------------------------------
# POST /pre-matriculas/{id}/decisao — liberar ou recusar
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_liberar_grava_a_auditoria(client, auth):
    pedir_entrada(client, auth)
    linha = Matricula.objects.get()
    antes = timezone.now()

    resposta = post(
        client,
        f"{PRE_MATRICULAS}/{linha.pk}/decisao",
        {
            "decisao": "liberar",
            "decidido_por": "id-de-plataforma-do-admin",
            "product_id": CURSO,
        },
        auth,
    )
    assert resposta.status_code == 200

    linha.refresh_from_db()
    assert linha.status == Matricula.STATUS_ATIVA
    assert linha.decidido_por == "id-de-plataforma-do-admin"
    assert linha.decidido_em >= antes
    assert linha.motivo_recusa == ""


@pytest.mark.django_db
def test_recusar_sem_motivo_e_422(client, auth):
    """Sem motivo, a pessoa espera para sempre e o mantenedor não distingue
    'ninguém olhou' de 'foi negado' (contrato)."""
    pedir_entrada(client, auth)
    linha = Matricula.objects.get()

    resposta = post(
        client,
        f"{PRE_MATRICULAS}/{linha.pk}/decisao",
        {"decisao": "recusar", "decidido_por": "admin-1"},
        auth,
    )
    assert resposta.status_code == 422
    linha.refresh_from_db()
    assert linha.status == Matricula.STATUS_AGUARDANDO


@pytest.mark.django_db
def test_decisao_nao_se_refaz(client, auth):
    pedir_entrada(client, auth)
    linha = Matricula.objects.get()
    corpo = {"decisao": "liberar", "decidido_por": "admin-1", "product_id": CURSO}

    assert (
        post(client, f"{PRE_MATRICULAS}/{linha.pk}/decisao", corpo, auth).status_code
        == 200
    )
    assert (
        post(client, f"{PRE_MATRICULAS}/{linha.pk}/decisao", corpo, auth).status_code
        == 409
    )


@pytest.mark.django_db
def test_decisao_sobre_matricula_paga_e_404(client, auth):
    """Esta porta NÃO é caminho para mexer no status de quem comprou: ela só
    enxerga linhas nascidas na fila (prefixo `pre:`)."""
    paga = matricular(
        site_id="site-1",
        order_id="pedido-real-3",
        product_id="curso",
        email="pagou@example.com",
        name="Pagou",
    )[0]

    resposta = post(
        client,
        f"{PRE_MATRICULAS}/{paga.pk}/decisao",
        {"decisao": "recusar", "decidido_por": "admin-1", "motivo": "qualquer"},
        auth,
    )
    assert resposta.status_code == 404
    paga.refresh_from_db()
    assert paga.status == Matricula.STATUS_ATIVA


@pytest.mark.django_db
@pytest.mark.parametrize("id_ruim", ["99999", "nao-e-numero"])
def test_decisao_em_id_inexistente_e_404(client, auth, id_ruim):
    """O payload vai COMPLETO de propósito, curso incluído.

    Pedido incompleto responde 422 antes de a linha ser procurada ([INV-ALU-C1],
    e é a mesma ordem que a conferência de `motivo` já seguia). Sem o curso
    aqui, este teste passaria a medir "payload incompleto é recusado" em vez de
    "id inexistente é 404", e o guarda da porta que não alcança quem não está na
    fila morreria em silêncio.
    """
    resposta = post(
        client,
        f"{PRE_MATRICULAS}/{id_ruim}/decisao",
        {"decisao": "liberar", "decidido_por": "admin-1", "product_id": CURSO},
        auth,
    )
    assert resposta.status_code == 404


@pytest.mark.django_db
def test_decisao_desconhecida_e_422(client, auth):
    pedir_entrada(client, auth)
    linha = Matricula.objects.get()
    resposta = post(
        client,
        f"{PRE_MATRICULAS}/{linha.pk}/decisao",
        {"decisao": "apagar", "decidido_por": "admin-1"},
        auth,
    )
    assert resposta.status_code == 422


# ---------------------------------------------------------------------------
# `pre:` é prefixo reservado — fail-closed na borda
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_pedido_real_nao_pode_comecar_com_o_prefixo_da_fila(client, auth):
    resposta = post(
        client,
        "/api/alunos/matriculas",
        {
            "site_id": "site-1",
            "order_id": "pre:tentativa-de-disfarce",
            "product_id": "curso",
            "customer": {"email": "atacante@example.com", "name": "Atacante"},
        },
        auth,
    )
    assert resposta.status_code == 422
    assert Matricula.objects.count() == 0


@pytest.mark.django_db
def test_evento_de_pagamento_com_prefixo_reservado_estoura(client, auth):
    """No caminho do evento a recusa PRECISA subir: envelope assim é mensagem
    envenenada, e a PEL/fila morta existe exatamente para ela."""
    with pytest.raises(OrderIdReservado):
        ao_pagamento_aprovado(
            {
                "site_id": "site-1",
                "order_id": "pre:vindo-do-provedor",
                "customer": {"email": "atacante@example.com", "name": "Atacante"},
            }
        )
    assert Matricula.objects.count() == 0


@pytest.mark.django_db
def test_entrar_na_fila_gera_order_id_unico_por_linha(client, auth):
    entrar_na_fila(
        site_id="site-1",
        email="um@example.com",
        nome_completo="Um",
        whatsapp="(96) 90000-0001",
    )
    entrar_na_fila(
        site_id="site-1",
        email="dois@example.com",
        nome_completo="Dois",
        whatsapp="(96) 90000-0002",
    )
    order_ids = set(Matricula.objects.values_list("order_id", flat=True))
    assert len(order_ids) == 2
    assert all(o.startswith(Matricula.PREFIXO_DA_FILA) for o in order_ids)


# ---------------------------------------------------------------------------
# As portas novas são internas: sem token, ninguém entra
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "metodo,url",
    [
        ("post", PRE_MATRICULAS),
        ("get", f"{PRE_MATRICULAS}?site_id=site-1"),
        ("post", f"{PRE_MATRICULAS}/1/decisao"),
    ],
)
def test_as_portas_da_fila_exigem_token(client, metodo, url):
    if metodo == "get":
        resposta = client.get(url)
    else:
        resposta = client.post(url, data="{}", content_type="application/json")
    assert resposta.status_code == 401


# ------------------------------------------------- a fila de TODAS as escolas
#
# `DECISAO-categorias-de-usuario` (28/08/2026): o painel do dono é
# plataforma-inteira (Lei 9), então `site_id` na query virou OPCIONAL — ausente
# = todas — e passou a vir em toda linha da resposta.


@pytest.mark.django_db
def test_sem_site_id_a_fila_e_de_todas_as_escolas(client, auth):
    """O caso que a mudança existe para atender.

    A direção do erro importa e é a mesma do comentário do handler: uma busca
    sem filtro que devolvesse vazio faria o painel dizer "ninguém esperando"
    para um mantenedor que tem gente esperando. É exatamente o que
    `.filter(site_id=None)` faria — ele casa com `site_id IS NULL`.
    """
    pedir_entrada(client, auth, site_id="escola-a", email="a@example.com")
    pedir_entrada(client, auth, site_id="escola-b", email="b@example.com")

    todas = client.get(PRE_MATRICULAS, **auth).json()
    assert {linha["email"] for linha in todas} == {"a@example.com", "b@example.com"}
    assert {linha["site_id"] for linha in todas} == {"escola-a", "escola-b"}


@pytest.mark.django_db
def test_com_site_id_continua_filtrando_como_antes(client, auth):
    """Retrocompatibilidade medida: quem já passava o parâmetro não muda."""
    pedir_entrada(client, auth, site_id="escola-a", email="a@example.com")
    pedir_entrada(client, auth, site_id="escola-b", email="b@example.com")

    so_a = client.get(f"{PRE_MATRICULAS}?site_id=escola-a", **auth).json()
    assert [linha["email"] for linha in so_a] == ["a@example.com"]
    assert [linha["site_id"] for linha in so_a] == ["escola-a"]


@pytest.mark.django_db
def test_o_site_id_vem_em_toda_linha_nas_duas_formas_de_busca(client, auth):
    """Forma da resposta é UMA, com filtro ou sem.

    Resposta que muda de forma conforme o parâmetro obriga cada consumidor a
    tratar dois casos — e o que esquecer trata o campo como ausente em
    silêncio, mostrando linhas sem dono na tela.
    """
    pedir_entrada(client, auth, site_id="escola-a", email="a@example.com")
    for url in (PRE_MATRICULAS, f"{PRE_MATRICULAS}?site_id=escola-a"):
        for linha in client.get(url, **auth).json():
            assert linha["site_id"] == "escola-a", url


@pytest.mark.django_db
def test_sem_site_id_o_filtro_de_status_continua_valendo(client, auth):
    """Os dois filtros são independentes — e o padrão continua `aguardando`."""
    pedir_entrada(client, auth, site_id="escola-a", email="a@example.com")
    pedir_entrada(client, auth, site_id="escola-b", email="b@example.com")
    fila = client.get(PRE_MATRICULAS, **auth).json()
    alvo = [linha for linha in fila if linha["email"] == "b@example.com"][0]
    post(
        client,
        f"{PRE_MATRICULAS}/{alvo['id']}/decisao",
        {"decisao": "recusar", "decidido_por": "eu", "motivo": "não achei"},
        auth,
    )

    aguardando = client.get(PRE_MATRICULAS, **auth).json()
    assert [linha["email"] for linha in aguardando] == ["a@example.com"]

    recusadas = client.get(f"{PRE_MATRICULAS}?status=recusada", **auth).json()
    assert [linha["email"] for linha in recusadas] == ["b@example.com"]
    assert recusadas[0]["site_id"] == "escola-b"
