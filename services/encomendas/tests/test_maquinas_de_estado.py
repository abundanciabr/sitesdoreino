"""As três máquinas de estado da §7.2 do plano, e a prova de que o banco as impõe.

O plano desenha três máquinas: a da **encomenda** (15 estados), a da **oferta**
(pendente e quatro desfechos, todos finais) e a da **disponibilidade** do perfil.
Este arquivo mede as três pelo lado que interessa: a **transição PROIBIDA**. Uma
máquina de estado só vale pelo que ela recusa; o que ela permite qualquer `if`
permite também.

**E ela é medida DUAS vezes, de propósito.** Em Python, `mudar_status()` levanta
`TransicaoProibida`, que é a porta educada da tela. No PostgreSQL, o gatilho
`encomendas_transicao_permitida` recusa o mesmo passo, e é ele quem vale contra
`queryset.update()` (que não passa por `save()`, `armadilhas/023`), contra uma
migração de dados e contra um `psql` de madrugada.

Duas expressões da mesma regra divergem no primeiro dia em que alguém mexer numa
delas, e aqui divergir significa uma encomenda presa num estado de onde a tela
não sabe sair. Por isso `test_o_python_e_o_postgres_concordam_em_todos_os_pares`
percorre o produto cartesiano dos 15 estados e exige o mesmo veredito nos dois.
"""

from datetime import datetime, timedelta, timezone as fuso

import pytest
from django.db import IntegrityError, transaction

from apps.encomendas.models import (
    ESTADOS_ATIVOS_DA_ENCOMENDA,
    ESTADOS_DE_ENCOMENDA,
    TRANSICOES_DA_ENCOMENDA,
    Encomenda,
    MudancaDeStatus,
    Oferta,
    PerfilProfissional,
    Pessoa,
    TransicaoProibida,
)

AGORA = datetime(2026, 9, 4, 12, 0, tzinfo=fuso.utc)
SITE = "escola-a"


@pytest.fixture
def perfil(db):
    pessoa = Pessoa.objects.create(id_da_plataforma="pes-1", nome_exibido="Ana")
    return PerfilProfissional.objects.create(pessoa=pessoa, site_id=SITE)


# O padrão é `NA_FILA` desde 04/09/2026, e a troca acompanha o modelo: a
# encomenda nasce numa pista, não no caixa (`PLANO-AREA-DE-NEGOCIACAO.md` §5).
def cria_encomenda(status=Encomenda.Status.NA_FILA):
    return Encomenda.objects.create(
        site_id=SITE,
        origem=Encomenda.Origem.ESCOLA,
        cliente_id="cli-1",
        cartao=Encomenda.Cartao.ITEM_SIMPLES,
        nivel=Encomenda.Nivel.INICIANTE,
        status=status,
    )


# ---------------------------------------------------------------------------
# A tabela de transições é a do plano, e ela não perdeu nem ganhou estado
# ---------------------------------------------------------------------------


def test_os_dezenove_estados_da_secao_7_2_com_a_emenda():
    """A lista da §7.2 do plano MAIS os quatro da emenda, contada.

    Eram 15 até 04/09/2026. O mantenedor liberou a negociação e o mural aberto
    (`docs/decisoes/PLANO-AREA-DE-NEGOCIACAO.md`), e quatro estados entraram:
    `no_mural`, `reservada`, `em_negociacao` e `acordada`. Estado a mais ou a
    menos reprova aqui.
    """
    assert sorted(ESTADOS_DE_ENCOMENDA) == sorted(
        [
            "abandonada",
            "aberta",
            "acordada",
            "aguardando_cliente",
            "aguardando_pagamento",
            "aprovada",
            "cancelada",
            "concluida",
            "em_correcao",
            "em_mediacao",
            "em_negociacao",
            "em_producao",
            "em_revisao",
            "entregue",
            "na_fila",
            "no_mural",
            "oferecida",
            "para_reclassificar",
            "reservada",
        ]
    )
    assert len(ESTADOS_DE_ENCOMENDA) == 19


def test_o_caixa_nao_e_mais_a_porta_de_entrada():
    """`aguardando_pagamento` deixou de ser o começo, e virou o penúltimo passo.

    É a mudança mais fácil de desfazer sem querer, e a mais cara: se alguém
    devolver o caixa para o início, a plataforma volta a pedir dinheiro por um
    valor que ninguém combinou ainda, que é exatamente o que a negociação
    existe para não fazer (`PLANO-AREA-DE-NEGOCIACAO.md` §5).
    """
    from apps.encomendas.models import Encomenda

    assert Encomenda._meta.get_field("status").default == "na_fila"
    # Ninguém CHEGA ao caixa senão pelo acordo.
    quem_leva_ao_caixa = {
        estado
        for estado, destinos in TRANSICOES_DA_ENCOMENDA.items()
        if "aguardando_pagamento" in destinos
    }
    assert quem_leva_ao_caixa == {"acordada"}
    # E do caixa só se sai para a produção (ou para trás, pelas saídas de sempre).
    assert TRANSICOES_DA_ENCOMENDA["aguardando_pagamento"] == frozenset(
        {"em_producao", "cancelada", "em_mediacao"}
    )


def test_aceitar_uma_oferta_leva_a_negociar_e_nao_a_produzir():
    """A seta que mais mudou de significado com a emenda.

    Antes, aceitar uma oferta era começar a produzir, porque o preço já estava
    dado. Agora é começar a NEGOCIAR. Se esta seta voltar a apontar para
    `em_producao`, a negociação inteira vira código morto que nenhum caminho
    alcança — e nada quebraria para avisar.
    """
    assert "em_negociacao" in TRANSICOES_DA_ENCOMENDA["oferecida"]
    assert "em_producao" not in TRANSICOES_DA_ENCOMENDA["oferecida"]
    # A chamada aberta segue o mesmo caminho: o primeiro que aceita, negocia.
    assert "em_negociacao" in TRANSICOES_DA_ENCOMENDA["aberta"]
    assert "em_producao" not in TRANSICOES_DA_ENCOMENDA["aberta"]
    # E quem pegou no Mural também.
    assert "em_negociacao" in TRANSICOES_DA_ENCOMENDA["reservada"]


def test_quem_calou_decide_para_onde_a_negociacao_volta():
    """[INV-ENC-N7]: cliente calado vai ao plantão, nunca ao próximo aluno.

    O aluno que desiste devolve o projeto à pista dele, e o próximo aluno o
    recebe — isso é justo, porque o projeto continua bom. Mas um cliente que
    sumiu não é um projeto bom: mandá-lo ao próximo faria cada aluno da fila
    gastar a própria vez num fantasma, um depois do outro, e nenhum saberia
    por quê. Por isso as três saídas existem, e são diferentes.
    """
    saidas = TRANSICOES_DA_ENCOMENDA["em_negociacao"]
    assert "acordada" in saidas
    assert "na_fila" in saidas and "no_mural" in saidas
    assert "para_reclassificar" in saidas


def test_os_estados_do_textchoices_sao_os_da_maquina():
    """O `TextChoices` dá o RÓTULO da tela; a máquina dá as transições.

    São duas listas com os mesmos valores, e é este teste que impede a segunda
    de ganhar um estado que a primeira não conhece (ou o contrário): um estado
    sem rótulo apareceria cru na tela do plantão, e um rótulo sem transição
    seria um beco sem saída.
    """
    assert sorted(Encomenda.Status.values) == sorted(ESTADOS_DE_ENCOMENDA)
    assert sorted(TRANSICOES_DA_ENCOMENDA) == sorted(ESTADOS_DE_ENCOMENDA)


def test_todo_estado_ativo_vai_para_mediacao():
    """ "Qualquer estado ativo -> em_mediacao" (plano §7.2)."""
    for estado in ESTADOS_ATIVOS_DA_ENCOMENDA:
        assert "em_mediacao" in TRANSICOES_DA_ENCOMENDA[estado], estado


def test_os_tres_estados_finais_nao_saem_de_lugar_nenhum():
    """`concluida` e `cancelada` terminam; de `aprovada` só se conclui.

    Reabrir uma aprovação é decisão de produto que ninguém tomou, e a mediação
    depois da aprovação seria a porta por onde o dinheiro já repassado voltaria.
    """
    assert TRANSICOES_DA_ENCOMENDA["concluida"] == frozenset()
    assert TRANSICOES_DA_ENCOMENDA["cancelada"] == frozenset()
    assert TRANSICOES_DA_ENCOMENDA["aprovada"] == frozenset({"concluida"})


# ---------------------------------------------------------------------------
# A transição proibida, pelos dois lados
# ---------------------------------------------------------------------------


def test_a_encomenda_recusa_pular_a_producao(db):
    """O caminho feliz inteiro existe; o atalho, não.

    `na_fila -> aprovada` é o atalho que uma tela apressada tentaria: aprovar
    sem ninguém ter produzido, entregue nem revisado. É também o que
    [INV-ENC-S2] (nenhuma primeira entrega chega ao cliente sem humano olhar)
    depende de ser impossível.
    """
    encomenda = cria_encomenda(Encomenda.Status.NA_FILA)
    with pytest.raises(TransicaoProibida, match="na_fila nao vai para aprovada"):
        encomenda.mudar_status(Encomenda.Status.APROVADA)
    encomenda.refresh_from_db()
    assert encomenda.status == "na_fila"


def test_a_transicao_proibida_nao_deixa_rastro(db):
    """Recusar é não acontecer: o histórico não ganha linha de tentativa."""
    encomenda = cria_encomenda(Encomenda.Status.NA_FILA)
    with pytest.raises(TransicaoProibida):
        encomenda.mudar_status(Encomenda.Status.CONCLUIDA)
    assert MudancaDeStatus.objects.filter(encomenda=encomenda).count() == 0


def test_o_queryset_update_tambem_e_recusado(db):
    """A guarda que importa: `update()` não passa por `save()` (`armadilhas/023`).

    Este é o caminho de uma varredura periódica, de uma migração de dados e de
    uma tela de administração futura. Se a máquina vivesse só em Python, ela
    seria uma promessa exatamente aqui.
    """
    encomenda = cria_encomenda(Encomenda.Status.NA_FILA)
    with pytest.raises(IntegrityError, match="transicao proibida"):
        Encomenda.objects.filter(pk=encomenda.pk).update(
            status=Encomenda.Status.CONCLUIDA
        )


def test_a_linha_principal_do_plano_anda_inteira(db):
    """O caminho feliz, da fila à conclusão, sem atalho nenhum.

    Depois da emenda de 04/09/2026 ele passa por `em_negociacao`, `acordada` e
    só então pelo caixa: a encomenda nasce numa pista, um aluno recebe a
    oferta, os dois negociam, o acordo congela o combinado, o pagamento é
    confirmado, e aí a produção começa.
    """
    caminho = [
        "oferecida",
        "em_negociacao",
        "acordada",
        "aguardando_pagamento",
        "em_producao",
        "entregue",
        "em_revisao",
        "aguardando_cliente",
        "aprovada",
        "concluida",
    ]
    encomenda = cria_encomenda()
    for passo in caminho:
        encomenda.mudar_status(passo, ator_id="prof-1")
    encomenda.refresh_from_db()
    assert encomenda.status == "concluida"
    assert (
        list(
            MudancaDeStatus.objects.filter(encomenda=encomenda).values_list(
                "para", flat=True
            )
        )
        == caminho
    )


def test_a_linha_do_mural_anda_inteira(db):
    """A segunda pista, ponta a ponta.

    O projeto nasce no Mural, um aluno o PEGA (`reservada`), propõe, os dois
    fecham, o pagamento é confirmado e a produção começa. É o mesmo destino da
    fila por um caminho diferente — e é isso que prova que o Mural não é um
    produto paralelo, e sim uma segunda porta para a mesma esteira.
    """
    # O projeto NASCE no Mural, e não é movido para lá: quem decide a pista é o
    # nível, no momento em que a encomenda é criada. `na_fila -> no_mural` não
    # é transição legal de propósito — trocar a pista de um projeto vivo é
    # reclassificação, e reclassificação passa pelo plantão.
    caminho = [
        "reservada",
        "em_negociacao",
        "acordada",
        "aguardando_pagamento",
        "em_producao",
    ]
    encomenda = cria_encomenda(Encomenda.Status.NO_MURAL)
    for passo in caminho:
        encomenda.mudar_status(passo, ator_id="prof-1")
    encomenda.refresh_from_db()
    assert encomenda.status == "em_producao"


def test_o_cliente_que_some_nao_cai_no_colo_do_proximo_aluno(db):
    """[INV-ENC-N7] medido no banco, e não só na tabela de transições.

    Da negociação se sai para o plantão (cliente calado) ou de volta à pista
    (aluno calado). As duas existem, e a diferença entre elas é a regra.
    """
    encomenda = cria_encomenda()
    for passo in ["oferecida", "em_negociacao", "para_reclassificar"]:
        encomenda.mudar_status(passo, ator_id="prof-1")
    encomenda.refresh_from_db()
    assert encomenda.status == "para_reclassificar"

    outra = cria_encomenda()
    for passo in ["oferecida", "em_negociacao", "na_fila"]:
        outra.mudar_status(passo, ator_id="prof-1")
    outra.refresh_from_db()
    assert outra.status == "na_fila"


def test_o_mesmo_status_nao_e_transicao(db):
    """Reafirmar o estado atual é recusado em Python e ignorado pelo banco.

    O chamador que "reafirma" um estado quase sempre está perdendo uma condição
    de corrida, e devolver sucesso ali é o falso-verde do padrão 1 da
    RETROSPECTIVA. Já o gatilho deixa passar `UPDATE` que não muda o status,
    porque é assim que um `save()` de outro campo qualquer funciona.
    """
    encomenda = cria_encomenda(Encomenda.Status.NA_FILA)
    with pytest.raises(TransicaoProibida):
        encomenda.mudar_status(Encomenda.Status.NA_FILA)
    Encomenda.objects.filter(pk=encomenda.pk).update(cliente_id="cli-2")
    encomenda.refresh_from_db()
    assert encomenda.cliente_id == "cli-2"


def test_o_python_e_o_postgres_concordam_em_todos_os_pares(db):
    """A prova de que a tabela do código e a do gatilho são a MESMA.

    A tabela vive duas vezes: em `TRANSICOES_DA_ENCOMENDA` (que a tela lê para
    saber quais botões mostrar) e dentro da função `encomendas_transicao_permitida`
    da migração `0001` (que o banco impõe). Não há como gerar uma da outra sem
    uma migração importar o modelo, o que a tornaria histórica e frágil. O que
    resta é medir: os 15 x 15 pares, um a um, com o mesmo veredito nos dois.

    Sem este teste, alguém acrescentaria um destino ao dicionário do Python e a
    tela ofereceria um botão que o banco recusa, em produção, e só lá.
    """
    divergencias = []
    for de in ESTADOS_DE_ENCOMENDA:
        # Uma linha NOVA por estado de partida. O gatilho e `BEFORE UPDATE`, e
        # o INSERT nao passa por ele: preparar o estado de partida por `update`
        # seria pedir ao gatilho que permitisse justamente o que ele recusa.
        encomenda = cria_encomenda(de)
        for para in ESTADOS_DE_ENCOMENDA:
            if de == para:
                continue
            python_deixa = para in TRANSICOES_DA_ENCOMENDA[de]
            try:
                with transaction.atomic():
                    Encomenda.objects.filter(pk=encomenda.pk).update(status=para)
                    banco_deixa = True
                    # Desfaz para o estado de partida sem gatilho reclamar: o
                    # `atomic` de fora e quem devolve, no `raise` abaixo.
                    raise _Voltar()
            except _Voltar:
                pass
            except IntegrityError:
                banco_deixa = False
            if python_deixa != banco_deixa:
                divergencias.append((de, para, python_deixa, banco_deixa))

    assert divergencias == [], (
        "o dicionario `TRANSICOES_DA_ENCOMENDA` e o gatilho "
        "`encomendas_transicao_permitida` da migracao 0001 discordam nestes "
        f"pares (de, para, python, banco): {divergencias}"
    )


class _Voltar(Exception):
    """Desfaz o `atomic` do par medido sem confundir com a recusa do gatilho."""


# ---------------------------------------------------------------------------
# A máquina da oferta: pendente, e quatro desfechos finais
# ---------------------------------------------------------------------------


def _oferta(encomenda, aluno):
    return Oferta.objects.create(
        site_id=SITE,
        encomenda=encomenda,
        aluno=aluno,
        expira_em=AGORA + timedelta(hours=3),
    )


def test_a_oferta_fechada_e_pedra(perfil):
    """Aceita não vira passada, expirada não vira aceita.

    É o que permite auditar a justiça da fila meses depois sem perguntar a
    ninguém o que aconteceu: a `Oferta` é registro de primeira classe
    (plano §7.1), não linha de trabalho.
    """
    oferta = _oferta(cria_encomenda(), perfil)
    oferta.responder(Oferta.Resultado.ACEITA, em=AGORA)
    with pytest.raises(TransicaoProibida, match="aceita nao vai para passou"):
        oferta.responder(
            Oferta.Resultado.PASSOU,
            motivo_passe=Oferta.MotivoDoPasse.SEM_TEMPO,
            em=AGORA,
        )


def test_a_oferta_pendente_vai_para_os_quatro_desfechos(perfil):
    for resultado in ("aceita", "passou", "expirou", "cancelada"):
        encomenda = cria_encomenda()
        oferta = _oferta(encomenda, perfil)
        motivo = Oferta.MotivoDoPasse.NAO_CURTO if resultado == "passou" else ""
        oferta.responder(resultado, motivo_passe=motivo, em=AGORA)
        assert oferta.respondida_em == AGORA


def test_os_quatro_motivos_de_passe_sao_os_do_plano():
    """Anexo A do plano: quatro botões, um toque. Nem três, nem cinco."""
    assert sorted(Oferta.MotivoDoPasse.values) == [
        "nao_curto",
        "nao_me_sinto_pronto",
        "sem_tempo",
        "valor_baixo",
    ]


# ---------------------------------------------------------------------------
# A máquina da disponibilidade
# ---------------------------------------------------------------------------


def test_o_perfil_pausado_nao_vai_direto_para_trabalhando(perfil):
    """Quem está fora das ofertas não recebe oferta, logo não há aceite.

    Sem esta recusa, [INV-ENC-J7] ("aluno trabalhando não recebe ofertas") não
    teria como ser provado no degrau 2.3: existiria um caminho para entrar em
    trabalho sem passar por uma oferta.
    """
    perfil.mudar_disponibilidade(
        PerfilProfissional.Disponibilidade.PAUSADO,
        modo_da_pausa=PerfilProfissional.ModoDaPausa.MANUAL,
    )
    with pytest.raises(TransicaoProibida, match="pausado nao vai para trabalhando"):
        perfil.mudar_disponibilidade(PerfilProfissional.Disponibilidade.TRABALHANDO)


def test_religar_apaga_a_pausa(perfil):
    """ "O aluno religa e volta ao mesmo lugar" (plano §6.3).

    O lugar é `data_entrada_fila`, e a pausa some junto: um perfil disponível
    com `pausa_ate` no futuro seria lido de dois jeitos por dois pedaços de
    código, e o segundo a ler é o que erra.
    """
    perfil.data_entrada_fila = AGORA
    perfil.save(update_fields=["data_entrada_fila"])
    perfil.mudar_disponibilidade(
        PerfilProfissional.Disponibilidade.PAUSADO,
        modo_da_pausa=PerfilProfissional.ModoDaPausa.POR_SILENCIO,
        pausa_ate=AGORA + timedelta(days=30),
    )
    perfil.mudar_disponibilidade(PerfilProfissional.Disponibilidade.DISPONIVEL)
    perfil.refresh_from_db()
    assert perfil.modo_da_pausa == "" and perfil.pausa_ate is None
    assert perfil.data_entrada_fila == AGORA


def test_os_quatro_modos_de_pausa_sao_os_do_contrato():
    """Os mesmos quatro de `aluno.pausado.v1`, que esta célula promete emitir."""
    assert sorted(PerfilProfissional.ModoDaPausa.values) == [
        "automatica_por_silencio",
        "manual",
        "por_segundo_abandono",
        "suspensao_pelo_plantao",
    ]
