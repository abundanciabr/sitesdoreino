"""Os parâmetros são DADO, com histórico por linha nova. E a prova é de fora.

Lei §3.8: *"A tabela `Parametro` mora nesta célula: `chave`, `valor`, `desde`,
`motivo`, `quem`; mudar é acrescentar uma linha, nunca `UPDATE`; o motor lê o
valor vigente em `agora` (...)."*

Os testes distinguem os valores persistidos no banco de constantes no motor.
"""

from datetime import datetime, timezone as fuso
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import IntegrityError

from apps.encomendas.models import CHAVES_DE_PARAMETRO, Parametro

SITE = "escola-a"
AGORA = datetime(2026, 9, 4, 12, 0, tzinfo=fuso.utc)

# A tabela da lei §6, transcrita AQUI, de propósito, e não importada do
# semeador: um teste que importa a resposta do arquivo que ele mede não mede
# nada. As 19 linhas da lei viram 27 chaves porque várias juntam duas ou três
# chaves numa célula só ("janela_inicio / janela_fim"); a 28ª vem do §9 do
# `PLANO-AREA-DE-NEGOCIACAO.md`.
A_LEI_SECAO_6 = {
    "relogio_da_oferta": "3",
    "janela_inicio": "08:00",
    "janela_fim": "22:00",
    "silencios_para_pausa": "3",
    "horas_para_virar_aberta": "24",
    "encomendas_simultaneas_por_aluno": "1",
    "prazo_producao.simples": "3",
    "prazo_producao.vestivel_veiculo": "7",
    "prazo_producao.personagem": "14",
    "dias_de_revisao_no_prazo_prometido": "1",
    "extensoes_por_encomenda": "1",
    "extensao_horas": "48",
    "extensao_pedida_ate_horas_antes": "24",
    "sla_do_revisor": "24",
    "amostragem_de_revisao": "5",
    "aprovacao_tacita": "48",
    "correcoes_incluidas": "1",
    "prazo_da_correcao": "48",
    "passes_nao_pronto_para_reclassificar": "2",
    "passes_nao_pronto_para_aviso": "3",
    "janela_dos_passes": "30",
    "repasse_apos_aprovacao": "proximo_dia_util",
    "meta_aprovacao_cliente_novo": "4",
    "entregas_para_nivel_intermediario": "1",
    "entregas_para_nivel_avancado": "5",
    "janela_sem_abandono": "90",
    "pausa_por_segundo_abandono": "30",
    # A chave do Mural, que vem do §9 do
    # `PLANO-AREA-DE-NEGOCIACAO.md`, a emenda que o mantenedor aprovou em
    # 04/09/2026 e que trouxe o Mural. Transcrita aqui pela mesma razão que as
    # outras 27: um teste que importa a resposta do arquivo que ele mede não
    # mede nada.
    "relogio_da_reserva_no_mural": "3",
    # As tres da NEGOCIACAO, do mesmo §9, que chegaram com o degrau 2.12
    # (TAR-134): tres rodadas para cada lado, vinte e quatro horas uteis de
    # validade por proposta, e quinhentos caracteres de justificativa.
    "rodadas_de_negociacao": "3",
    "validade_da_proposta": "24",
    "limite_da_justificativa": "500",
    # A 32a, do degrau 2.7: quantos dias de historico a estimativa de espera
    # olha para medir o ritmo de encomendas de um nivel
    # (`apps/encomendas/espera.py`). Ela e parametro, e nao numero em codigo,
    # porque o guarda de constante magica deste arquivo reprova numero solto na
    # celula, e reprovou este quando ele nasceu assim.
    "janela_do_ritmo_da_espera": "30",
    # O prazo da chamada aberta é uma decisão histórica própria, e não pode
    # desaparecer porque a chave não está na tabela original da §6.
    "horas_para_escalar_chamada_aberta": "24",
}

# AS CHAVES QUE EXISTEM NO CATALOGO E NAO TEM VALOR, DE PROPOSITO. O piso por
# nivel sai do piloto de papel, que e onde os primeiros precos reais vao
# aparecer; chutar um numero agora
# seria inventa-lo para depois defende-lo. A chave existe porque o vocabulario e
# fechado no banco, e sem ela o mantenedor nao conseguiria gravar o piso nem
# quando o tivesse.
#
# ELAS SAO MEDIDAS AQUI, e nao esquecidas: um guarda que so contasse as chaves
# semeadas nao distinguiria a ausencia proposital de um valor esquecido, que e
# exatamente o que este arquivo existe para pegar.
O_PISO_NASCE_SEM_NUMERO = {
    "piso_por_nivel.iniciante",
    "piso_por_nivel.intermediario",
    "piso_por_nivel.avancado",
}


def semear(site=SITE):
    saida = StringIO()
    call_command("semear_parametros", site=site, stdout=saida)
    return saida.getvalue()


# ---------------------------------------------------------------------------
# 1. O catálogo e a semente
# ---------------------------------------------------------------------------


def test_o_catalogo_tem_as_36_chaves():
    """Chave a mais ou a menos reprova aqui, antes de o motor ler `None`."""
    assert sorted(CHAVES_DE_PARAMETRO) == sorted(
        set(A_LEI_SECAO_6) | O_PISO_NASCE_SEM_NUMERO
    )
    assert len(CHAVES_DE_PARAMETRO) == 36


def test_a_semente_grava_os_33_valores(db):
    """A prova de fora: cada chave é LIDA DO BANCO e comparada com a lei."""
    semear()
    do_banco = dict(
        Parametro.objects.filter(site_id=SITE).values_list("chave", "valor")
    )
    assert do_banco == A_LEI_SECAO_6


def test_o_piso_por_nivel_nasce_sem_linha_nenhuma(db):
    """O §9 em um guarda: a chave existe, e o número não.

    Sem esta asserção, semear um piso inventado passaria despercebido, e o
    número que ninguém decidiu viraria o número que todo mundo defende. Quem
    lê o piso (`negociacao.aviso_de_piso`) devolve `None` enquanto não houver
    linha, e nenhum caminho da célula bloqueia proposta por causa dele.
    """
    semear()
    assert not Parametro.objects.filter(
        site_id=SITE, chave__in=sorted(O_PISO_NASCE_SEM_NUMERO)
    ).exists()
    assert O_PISO_NASCE_SEM_NUMERO <= set(CHAVES_DE_PARAMETRO)


def test_toda_linha_semeada_diz_desde_quando_e_por_que(db):
    """`desde`, `motivo` e `quem` não são enfeite: são o histórico da lei §3.8."""
    semear()
    for linha in Parametro.objects.filter(site_id=SITE):
        assert linha.desde is not None
        assert len(linha.motivo) >= 15, linha.chave
        # A semente não tem pessoa atrás: quem semeia é a instalação da célula.
        assert linha.quem == ""


def test_a_semente_nao_pisa_em_cima_da_mudanca_do_dono(db):
    """Idempotente por CHAVE, não pela linha.

    Um `get_or_create` pela linha inteira reinstalaria o valor de fábrica ao
    lado da mudança do mantenedor, e a mais nova venceria. Como a tabela é
    append-only, não haveria como desfazer.
    """
    semear()
    Parametro.objects.create(
        site_id=SITE,
        chave="relogio_da_oferta",
        valor="5",
        desde=AGORA,
        motivo="O piloto de papel mostrou que tres horas nao dao tempo.",
        quem="dono-1",
    )
    semear()
    assert (
        Parametro.objects.filter(site_id=SITE, chave="relogio_da_oferta").count() == 2
    )
    assert Parametro.vigente_em("relogio_da_oferta", AGORA, site_id=SITE).valor == "5"


def test_a_semente_e_por_site(db):
    """Multissítio: uma fábrica, N lojas. Semear a escola A não semeia a escola B."""
    semear(site="escola-a")
    assert Parametro.objects.filter(site_id="escola-b").count() == 0


# ---------------------------------------------------------------------------
# 2. Mudar é acrescentar uma linha, nunca UPDATE
# ---------------------------------------------------------------------------


def test_o_valor_vigente_e_o_de_agora_e_nao_o_mais_recente(db):
    """A regra inteira da lei §3.8 cabe nesta asserção.

    Um parâmetro mudado às 15h NÃO reescreve uma oferta feita às 14h. Sem isto,
    a mudança do mantenedor seria retroativa, e uma oferta já feita passaria a
    ser julgada por uma regra que não existia quando ela nasceu.
    """
    semear()
    Parametro.objects.create(
        site_id=SITE,
        chave="relogio_da_oferta",
        valor="5",
        desde=AGORA.replace(hour=15),
        motivo="O piloto de papel mostrou que tres horas nao dao tempo.",
        quem="dono-1",
    )
    as_14h = Parametro.vigente_em(
        "relogio_da_oferta", AGORA.replace(hour=14), site_id=SITE
    )
    as_16h = Parametro.vigente_em(
        "relogio_da_oferta", AGORA.replace(hour=16), site_id=SITE
    )
    assert (as_14h.valor, as_16h.valor) == ("3", "5")


def test_antes_da_semente_nao_ha_valor_inventado(db):
    """`vigente_em` devolve `None`, e não um padrão embutido.

    Um padrão em código seria exatamente a constante mágica que a lei proíbe, e
    ele esconderia uma semeadura que não rodou: a célula trabalharia com números
    que ninguém escolheu.
    """
    assert Parametro.vigente_em("relogio_da_oferta", AGORA, site_id=SITE) is None


def test_mudar_um_parametro_e_acrescentar_uma_linha(db):
    """O PostgreSQL recusa o `UPDATE`. Sem gatilho, isto seria só uma frase."""
    semear()
    linha = Parametro.objects.get(site_id=SITE, chave="relogio_da_oferta")
    with pytest.raises(IntegrityError, match="append-only"):
        Parametro.objects.filter(pk=linha.pk).update(valor="5")


def test_uma_linha_de_parametro_nao_se_apaga(db):
    semear()
    with pytest.raises(IntegrityError, match="append-only"):
        Parametro.objects.filter(site_id=SITE, chave="janela_fim").delete()


def test_a_chave_fora_do_vocabulario_e_recusada(db):
    """A tabela não é um saco de configuração: chave nova é diff visível."""
    with pytest.raises(
        IntegrityError, match="chave_de_parametro_no_vocabulario_fechado"
    ):
        Parametro.objects.create(
            site_id=SITE,
            chave="preco_do_item_simples",
            valor="1000",
            desde=AGORA,
            motivo="Dinheiro nao mora nesta celula, e esta chave prova isso.",
            quem="dono-1",
        )


@pytest.mark.parametrize("motivo", ["", "ajuste"])
def test_mudanca_com_motivo_opcional_preserva_valor_autor_e_historico(db, motivo):
    semear()
    Parametro.objects.create(
        site_id=SITE,
        chave="relogio_da_oferta",
        valor="5",
        desde=AGORA,
        motivo=motivo,
        quem="dono-1",
    )
    historico = list(
        Parametro.objects.filter(site_id=SITE, chave="relogio_da_oferta")
        .order_by("desde")
        .values_list("valor", "motivo", "quem")
    )
    assert len(historico) == 2
    assert historico[0][0] == "3"
    assert historico[1] == ("5", motivo, "dono-1")


def test_duas_linhas_da_mesma_chave_no_mesmo_instante_sao_recusadas(db):
    """Duas respostas para "quanto vale agora" é a pergunta ambígua."""
    semear()
    vigente = Parametro.objects.get(site_id=SITE, chave="relogio_da_oferta")
    with pytest.raises(IntegrityError, match="uma_linha_por_chave_por_momento"):
        Parametro.objects.create(
            site_id=SITE,
            chave="relogio_da_oferta",
            valor="9",
            desde=vigente.desde,
            motivo="Duas linhas valendo do mesmo instante nao podem existir.",
            quem="dono-1",
        )


def test_o_tipo_de_cada_chave_vem_do_catalogo(db):
    """O `valor` é sempre texto; a chave é quem diz o tipo (contrato em papel)."""
    semear()
    assert (
        Parametro.objects.get(chave="janela_inicio", site_id=SITE).tipo == "hora_do_dia"
    )
    assert (
        Parametro.objects.get(chave="relogio_da_oferta", site_id=SITE).tipo == "horas"
    )
    assert (
        Parametro.objects.get(chave="repasse_apos_aprovacao", site_id=SITE).tipo
        == "enum"
    )
