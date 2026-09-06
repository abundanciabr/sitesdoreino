"""A fila de próxima ação: as regras, o roteador e os dois guardas.

`docs/decisoes/PLANO-PAINEL-DE-GESTAO.md`, degrau 15 do §8 e §11 (*"venda antes
de sucesso do aluno é recusada | teste-guarda na fila de próxima ação"*).

O tempo entra por parâmetro em todo teste, como na régua: cenário de "sumiu há
oito dias" se escreve como ele é, sem relógio congelado e sem teste que passa de
manhã e falha de noite.

Os dois guardas são provados dos DOIS lados. Um guarda que só é testado no caso
em que ele barra é indistinguível de um guarda que barra tudo, e esse guarda
seria pior do que nenhum: ele desligaria a fila inteira em silêncio.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.utils import timezone
from io import StringIO

from apps.jornadas import proxima_acao
from apps.jornadas.models import (
    EnvioDeCheckpoint,
    Entrega,
    EstadoDoAluno,
    Inscricao,
    Jornada,
    JornadaVersao,
    Passo,
)
from apps.jornadas.parametros import (
    PARAMETROS,
    TETO_DE_CONTATO_POR_SEMANA,
    Parametro,
)

SITE = "site-abc"
PESSOA = "pessoa-opaca-1"


def em(dia, hora=10):
    return timezone.make_aware(
        datetime(2026, 9, dia, hora), timezone.get_current_timezone()
    )


AGORA = em(20)


def uma_leitura(**campos):
    """A leitura padrão: pessoa sobre quem a plataforma não sabe nada."""
    base = dict(
        destinatario_id=PESSOA,
        site_id=SITE,
        momento=AGORA,
        entrou_em_aula_em=None,
        ultima_atividade_em=None,
        entregou_checkpoint=False,
        inscricao_andando=False,
        inscricao_vencida_desde=None,
        mensagens_na_janela=0,
    )
    base.update(campos)
    return proxima_acao.Leitura(**base)


def _sempre(leitura):
    return True


def uma_regra_de_venda():
    """Uma regra de venda escrita de propósito para casar com QUALQUER pessoa.

    Ela não existe no código de produção, e não pode existir hoje (diretiva do
    mantenedor de 22/08/2026, e §9 do plano). Ela existe AQUI porque é a única
    forma de provar que o guarda protege contra a regra que alguém escreverá um
    dia: guarda testado só contra código correto não guarda nada.
    """
    return proxima_acao.Regra(
        slug="oferta-do-proximo-passo",
        versao=1,
        situacao="uma situacao qualquer",
        gesto="oferecer o proximo passo pago",
        executor="humano",
        e_de_venda=True,
        e_de_contato=False,
        quando=_sempre,
    )


# ---------------------------------------------------------------------------
# AS TRÊS SAÍDAS, E SÓ ELAS
# ---------------------------------------------------------------------------


def test_o_roteador_tem_tres_saidas_e_a_quarta_e_recusada_no_nascimento():
    with pytest.raises(ValueError) as erro:
        proxima_acao.Regra(
            slug="uma-quarta-saida",
            versao=1,
            situacao="qualquer",
            gesto="qualquer",
            executor="em-analise",
            e_de_venda=False,
            e_de_contato=False,
            quando=_sempre,
        )
    assert "tres saidas" in str(erro.value)


def test_toda_regra_declarada_usa_um_dos_tres_executores():
    for regra in proxima_acao.REGRAS:
        assert regra.executor in proxima_acao.EXECUTORES


# ---------------------------------------------------------------------------
# GUARDA 1: SUCESSO DO ALUNO ANTES DE VENDA
# ---------------------------------------------------------------------------


def test_venda_para_quem_nao_teve_resultado_na_escola_e_recusada():
    leitura = uma_leitura(entregou_checkpoint=False)
    with patch.object(proxima_acao, "REGRAS", (uma_regra_de_venda(),)):
        decisao = proxima_acao.decidir(leitura)

    assert decisao.ha_gesto is False
    assert decisao.executor == ""
    assert "venda recusada" in decisao.porque
    assert "ainda nao teve resultado na escola" in decisao.porque


def test_a_mesma_venda_passa_para_quem_ja_entregou_um_checkpoint():
    """O outro lado do guarda: ele barra a venda cedo, não barra a venda."""
    leitura = uma_leitura(entregou_checkpoint=True)
    with patch.object(proxima_acao, "REGRAS", (uma_regra_de_venda(),)):
        decisao = proxima_acao.decidir(leitura)

    assert decisao.ha_gesto is True
    assert decisao.gesto == "oferecer o proximo passo pago"


def test_abrir_a_aula_nao_conta_como_resultado_e_a_venda_continua_recusada():
    """Quem abriu a aula e não entregou nada não colheu nada."""
    leitura = uma_leitura(entrou_em_aula_em=em(19), entregou_checkpoint=False)
    assert proxima_acao.teve_resultado_na_escola(leitura) is False

    with patch.object(proxima_acao, "REGRAS", (uma_regra_de_venda(),)):
        decisao = proxima_acao.decidir(leitura)
    assert decisao.ha_gesto is False


def test_a_venda_recusada_nao_apaga_o_gesto_legitimo_da_pessoa():
    """Negar a venda não pode virar negar tudo: a fila continua procurando."""
    leitura = uma_leitura(
        entregou_checkpoint=False,
        ultima_atividade_em=AGORA - timedelta(days=9),
    )
    regras = (uma_regra_de_venda(),) + proxima_acao.REGRAS
    with patch.object(proxima_acao, "REGRAS", regras):
        decisao = proxima_acao.decidir(leitura)

    assert decisao.regra_slug == "sumiu-e-a-maquina-ja-falou"
    assert decisao.executor == "humano"


# ---------------------------------------------------------------------------
# GUARDA 2: O TETO DE CONTATO
# ---------------------------------------------------------------------------


def test_o_teto_de_contato_segura_o_gesto_humano():
    leitura = uma_leitura(
        ultima_atividade_em=AGORA - timedelta(days=9),
        mensagens_na_janela=TETO_DE_CONTATO_POR_SEMANA.valor,
    )
    decisao = proxima_acao.decidir(leitura)

    assert decisao.ha_gesto is False
    assert "teto de" in decisao.porque


def test_abaixo_do_teto_o_mesmo_gesto_humano_sai():
    leitura = uma_leitura(
        ultima_atividade_em=AGORA - timedelta(days=9),
        mensagens_na_janela=TETO_DE_CONTATO_POR_SEMANA.valor - 1,
    )
    decisao = proxima_acao.decidir(leitura)

    assert decisao.executor == "humano"
    assert decisao.gesto == "a professora fala com esta pessoa, uma por uma"


def test_o_teto_nao_segura_tarefa_de_robo_porque_ela_nao_gasta_atencao():
    leitura = uma_leitura(
        inscricao_andando=True,
        inscricao_vencida_desde=AGORA - timedelta(days=3),
        mensagens_na_janela=TETO_DE_CONTATO_POR_SEMANA.valor + 10,
    )
    decisao = proxima_acao.decidir(leitura)

    assert decisao.executor == "robo"
    assert decisao.regra_slug == "jornada-parada-sem-explicacao"


# ---------------------------------------------------------------------------
# A ORDEM DAS REGRAS, QUE É PARTE DA REGRA
# ---------------------------------------------------------------------------


def test_jornada_parada_vence_a_regra_da_automacao():
    """Com a automação travada, dizer que a automação cuida disso é mentira."""
    leitura = uma_leitura(
        inscricao_andando=True,
        entrou_em_aula_em=None,
        inscricao_vencida_desde=AGORA - timedelta(days=2),
    )
    assert proxima_acao.decidir(leitura).executor == "robo"


def test_quem_esta_numa_sequencia_no_prazo_fica_com_a_automacao():
    leitura = uma_leitura(inscricao_andando=True, inscricao_vencida_desde=None)
    decisao = proxima_acao.decidir(leitura)

    assert decisao.executor == "automacao"
    assert decisao.regra_slug == "matriculada-e-nunca-entrou-em-aula"


def test_pessoa_sem_situacao_nenhuma_nao_vira_gesto_e_a_fila_diz_por_que():
    decisao = proxima_acao.decidir(uma_leitura())

    assert decisao.ha_gesto is False
    assert decisao.porque == "nenhuma regra casou com a situacao desta pessoa"


def test_quem_sumiu_mas_ainda_tem_a_maquina_falando_nao_vira_gesto_humano():
    leitura = uma_leitura(
        inscricao_andando=True,
        entrou_em_aula_em=em(10),
        ultima_atividade_em=AGORA - timedelta(days=30),
    )
    assert proxima_acao.decidir(leitura).executor != "humano"


# ---------------------------------------------------------------------------
# A REGRA É VERSIONADA, E ISSO É OBSERVÁVEL
# ---------------------------------------------------------------------------

# O par (versão, assinatura) de cada regra, fixado à mão. Mexer numa frase, num
# executor ou no corpo da condição muda a assinatura e derruba este teste; a
# única forma de fazê-lo passar de novo é subir a versão e reescrever a linha
# aqui, o que faz a mudança de regra aparecer no diff. Sem isto, "versionada"
# seria um número que ninguém é obrigado a mexer.
ASSINATURAS = {
    "jornada-parada-sem-explicacao": (1, "f456c9b482ee91de"),
    "matriculada-e-nunca-entrou-em-aula": (1, "5a57f90b053f75f3"),
    "sumiu-e-a-maquina-ja-falou": (1, "cf213a60ca8f1f85"),
}


def test_regra_que_muda_sem_subir_a_versao_reprova_aqui():
    medido = {
        regra.slug: (regra.versao, proxima_acao.impressao_digital(regra))
        for regra in proxima_acao.REGRAS
    }
    assert medido == ASSINATURAS, (
        "alguma regra da fila de proxima acao mudou. Suba a `versao` dela em "
        "apps/jornadas/proxima_acao.py e escreva o par novo em ASSINATURAS."
    )


def test_cada_regra_tem_uma_assinatura_propria():
    assinaturas = [proxima_acao.impressao_digital(r) for r in proxima_acao.REGRAS]
    assert len(set(assinaturas)) == len(assinaturas)


# ---------------------------------------------------------------------------
# OS TETOS SÃO PARÂMETRO COM DONO
# ---------------------------------------------------------------------------


def test_todo_parametro_tem_dono_declarado():
    for parametro in PARAMETROS:
        assert parametro.dono.strip(), parametro.nome


def test_parametro_sem_dono_nao_nasce():
    with pytest.raises(ValueError) as erro:
        Parametro(
            nome="um teto qualquer",
            valor=1,
            unidade="por dia",
            dono="   ",
            porque="porque sim",
        )
    assert "nao tem dono declarado" in str(erro.value)


def test_o_teto_diario_da_regua_le_do_parametro_e_nao_de_um_numero_solto():
    from apps.jornadas import regua
    from apps.jornadas.parametros import TETO_DE_CONTATO_POR_DIA

    assert regua.TETO_POR_DIA == TETO_DE_CONTATO_POR_DIA.valor


# ---------------------------------------------------------------------------
# A LEITURA VEM DO BANCO, E A FILA SE LÊ INTEIRA
# ---------------------------------------------------------------------------


def uma_inscricao(destinatario, slug, proximo_em=None, estado="andando"):
    jornada = Jornada.objects.create(
        site_id=SITE, slug=slug, gatilho="identidade.pessoa-cadastrada.v1"
    )
    versao = JornadaVersao.objects.create(jornada=jornada, numero=1)
    passo = Passo.objects.create(
        jornada_versao=versao, ordem=1, classe="relacional", canais=["sino"]
    )
    inscricao = Inscricao.objects.create(
        jornada_versao=versao,
        destinatario_id=destinatario,
        site_id=SITE,
        proximo_em=proximo_em,
        estado=estado,
    )
    return inscricao, passo


@pytest.mark.django_db
def test_a_leitura_traz_o_que_o_banco_sabe_sobre_a_pessoa():
    inscricao, passo = uma_inscricao(PESSOA, "boas-vindas", proximo_em=em(18))
    EstadoDoAluno.objects.create(
        destinatario_id=PESSOA,
        site_id=SITE,
        ultima_atividade_em=em(12),
        ultima_aula_em=em(11),
    )
    EnvioDeCheckpoint.objects.create(
        site_id=SITE, envio_id="env-1", aula_id="aula-1", aluno_id=PESSOA
    )
    Entrega.objects.create(
        inscricao=inscricao,
        passo=passo,
        canal="sino",
        previsto_para=em(19),
        enviado_em=em(19),
        resultado="enviada",
    )

    leitura = proxima_acao.ler(PESSOA, SITE, AGORA)

    assert leitura.inscricao_andando is True
    assert leitura.inscricao_vencida_desde == em(18)
    assert leitura.entrou_em_aula_em == em(11)
    assert leitura.ultima_atividade_em == em(12)
    assert leitura.entregou_checkpoint is True
    assert leitura.mensagens_na_janela == 1


@pytest.mark.django_db
def test_mensagem_de_oito_dias_atras_ja_saiu_da_janela_do_teto():
    inscricao, passo = uma_inscricao(PESSOA, "boas-vindas")
    Entrega.objects.create(
        inscricao=inscricao,
        passo=passo,
        canal="sino",
        previsto_para=em(12),
        enviado_em=AGORA - timedelta(days=8),
        resultado="enviada",
    )

    assert proxima_acao.ler(PESSOA, SITE, AGORA).mensagens_na_janela == 0


@pytest.mark.django_db
def test_a_pessoa_de_outro_site_nao_entra_nesta_fila():
    uma_inscricao(PESSOA, "boas-vindas")
    EstadoDoAluno.objects.create(destinatario_id="de-outra-casa", site_id="site-xyz")

    assert proxima_acao.pessoas_conhecidas(SITE) == [PESSOA]


@pytest.mark.django_db
def test_a_fila_poe_a_maquina_antes_da_gente_e_o_robo_no_fim():
    uma_inscricao("pessoa-automacao", "boas-vindas")
    uma_inscricao("pessoa-robo", "silencio", proximo_em=em(15))
    EstadoDoAluno.objects.create(
        destinatario_id="pessoa-humano",
        site_id=SITE,
        ultima_atividade_em=AGORA - timedelta(days=10),
    )

    com_gesto = [d for d in proxima_acao.fila(SITE, AGORA) if d.ha_gesto]

    assert [d.executor for d in com_gesto] == ["automacao", "humano", "robo"]


@pytest.mark.django_db
def test_o_comando_mostra_a_fila_e_a_linha_do_balcao_para_o_robo():
    """O comando le o relogio de verdade, entao a inscricao vence no PASSADO.

    O `proximo_em` dos outros testes e um instante do cenario, comparado com o
    `momento` que eles injetam. Este aqui passa pelo `handle()`, que chama
    `timezone.now()` sem parametro nenhum: uma data de cenario no futuro faria a
    inscricao parecer em dia, e o teste do robo mediria a regra da automacao
    achando que media a do robo.
    """
    vencida_ha_dois_dias = timezone.now() - timedelta(days=2)
    uma_inscricao("pessoa-robo", "silencio", proximo_em=vencida_ha_dois_dias)
    saida = StringIO()

    call_command("fila_de_proxima_acao", "--site", SITE, stdout=saida)
    texto = saida.getvalue()

    assert "FILA DE PROXIMA ACAO" in texto
    assert "ROBO (1)" in texto
    assert "python ci/fila.py criar" in texto
    assert "pessoa-robo" in texto


@pytest.mark.django_db
def test_o_comando_diz_quando_nao_conhece_ninguem():
    saida = StringIO()
    call_command("fila_de_proxima_acao", "--site", "site-vazio", stdout=saida)

    assert "Ninguem conhecido no site site-vazio" in saida.getvalue()
