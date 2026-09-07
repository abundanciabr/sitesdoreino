"""As seis conferencias do Revisor de coerencia, uma a uma, e a AULA LIMPA.

Lei: `docs/decisoes/PLANO-CELULA-CURSOS.md` §7 (a linha "Revisor de coerencia").
Degrau 3.1 da escada (TAR-245).

A AULA LIMPA VALE TANTO QUANTO AS SEIS
---------------------------------------
O §7 mede este agente por "zero falso positivo em amostra da professora", e o
modo de falhar deste degrau nao e deixar defeito passar: e acusar texto certo.
Por isso cada conferencia tem aqui DUAS medidas, o defeito e o texto legitimo
que se parece com ele, e o arquivo abre e fecha na aula escrita direito, que
tem de devolver zero.

O cenario e o esqueleto semeado (`conftest.esqueleto`): as 34 encomendas e os
13 instrumentos com os nomes canonicos que a instalacao grava. Nenhum texto de
aula viaja neste arquivo alem do minimo que cada medida exige, e nenhum dele e
do mantenedor: sao frases inventadas para o teste ([INV-CUR-C2]).
"""

from __future__ import annotations

import pytest

from apps.cursos import coerencia
from apps.cursos.models import Aula, Peca

pytestmark = pytest.mark.django_db


@pytest.fixture
def e00(esqueleto) -> Aula:
    return esqueleto.aulas.get(numero="E00")


def escrever(aula: Aula, tipo: str, texto: str) -> Aula:
    Peca.objects.update_or_create(aula=aula, tipo=tipo, defaults={"texto": texto})
    return aula


def codigos(aula: Aula) -> list[str]:
    return [defeito.codigo for defeito in coerencia.conferir(aula)]


# ---------------------------------------------------------------------------
# A AULA LIMPA: zero defeito
# ---------------------------------------------------------------------------
def test_a_aula_escrita_direito_nao_tem_defeito_nenhum(e00):
    """Uma aula com tudo o que costuma disparar um revisor mal feito: remissao
    valida, o nome canonico de dois instrumentos, o mesmo arquivo citado tres
    vezes, numeros diferentes de coisas diferentes, a lista do checkpoint igual
    a da peca, e numeros que nao sao de plataforma."""
    e00.aceito_quando = ["o cubo tem bevel", "a base esta apoiada"]
    e00.save(update_fields=["aceito_quando"])
    escrever(e00, Peca.Tipo.PEDIDO, "Uma cadeira para a vitrine, como na E01.")
    escrever(
        e00,
        Peca.Tipo.EU_FACO,
        "Salve como cadeira-final.blend. Sao 4 passos, e o Recall dura 2 minutos.",
    )
    escrever(
        e00,
        Peca.Tipo.NOS_FAZEMOS,
        "Abra cadeira-final.blend de novo. Os mesmos 4 passos, agora comigo.",
    )
    escrever(
        e00,
        Peca.Tipo.VOCE_FAZ,
        "Agora e com voce.\n\nAceito quando\n\n- o cubo tem bevel\n"
        "- a base esta apoiada\n",
    )
    escrever(
        e00,
        Peca.Tipo.DRILLS,
        "Tres drills de 5 minutos cada, sempre sobre cadeira-final.blend.",
    )
    escrever(
        e00,
        Peca.Tipo.REGRA_DO_PADRAO,
        "O Teste STUDS entra aqui, e a Rubrica de Encomenda fecha a entrega.",
    )
    escrever(
        e00,
        Peca.Tipo.ERROS_CLASSICOS,
        "- **Face invertida**: a normal aponta para dentro.\n"
        "- **Bevel exagerado**: o vinco some.",
    )
    escrever(
        e00,
        Peca.Tipo.CHECKPOINT,
        "Envie o arquivo e o print. O prazo esta na tela, e nao aqui.",
    )
    escrever(
        e00,
        Peca.Tipo.GUIA_DO_MENTOR,
        "Anotacao da professora: hoje o limite e de 20000 triangulos.",
    )

    assert coerencia.conferir(e00) == []


# ---------------------------------------------------------------------------
# 1. A REMISSAO QUEBRADA
# ---------------------------------------------------------------------------
def test_a_remissao_para_aula_inexistente_e_defeito(e00):
    escrever(e00, Peca.Tipo.DRILLS, "Volte na E99 antes de comecar.")

    (defeito,) = coerencia.conferir(e00)

    assert defeito.codigo == coerencia.REMISSAO_QUEBRADA
    assert defeito.peca == Peca.Tipo.DRILLS
    assert "E99" in defeito.frase
    assert defeito.impede_publicar is True


def test_a_remissao_de_tres_digitos_tambem_e_apontada(e00):
    escrever(e00, Peca.Tipo.DRILLS, "Isto continua na E100.")

    assert codigos(e00) == [coerencia.REMISSAO_QUEBRADA]


def test_a_remissao_para_aula_existente_nao_e_defeito(e00):
    escrever(e00, Peca.Tipo.DRILLS, "Isto veio da E01 e volta na E32 e na E00.")

    assert coerencia.conferir(e00) == []


def test_a_mesma_remissao_quebrada_repetida_aponta_uma_vez_por_peca(e00):
    escrever(e00, Peca.Tipo.DRILLS, "Na E99. De novo na E99. E outra vez na E99.")

    assert codigos(e00) == [coerencia.REMISSAO_QUEBRADA]


# ---------------------------------------------------------------------------
# 2. O NOME FORA DO CANONICO
# ---------------------------------------------------------------------------
def test_o_instrumento_com_a_caixa_trocada_e_defeito(e00):
    escrever(e00, Peca.Tipo.DRILLS, "Aplique a Rubrica de encomenda no fim.")

    (defeito,) = coerencia.conferir(e00)

    assert defeito.codigo == coerencia.NOME_FORA_DO_CANONICO
    assert "Rubrica de encomenda" in defeito.frase
    assert "Rubrica de Encomenda" in defeito.o_que_fazer
    assert defeito.impede_publicar is False


def test_o_instrumento_sem_o_acento_e_defeito(e00):
    escrever(e00, Peca.Tipo.DRILLS, "Faca a Validacao no motor antes de enviar.")

    assert codigos(e00) == [coerencia.NOME_FORA_DO_CANONICO]


def test_o_nome_canonico_exato_nao_e_defeito(e00):
    escrever(
        e00,
        Peca.Tipo.DRILLS,
        "Teste STUDS, Rubrica de Encomenda e Validação no motor.",
    )

    assert coerencia.conferir(e00) == []


def test_a_primeira_letra_em_caixa_diferente_nao_e_defeito(e00):
    """Comeco de frase e maiuscula em portugues: cobrar isso seria o falso
    positivo mais barato de produzir."""
    escrever(e00, Peca.Tipo.DRILLS, "pronto para sair e o instrumento desta aula.")

    assert coerencia.conferir(e00) == []


def test_o_defeito_batizado_na_peca_de_erros_classicos_vira_nome_canonico(e00):
    escrever(e00, Peca.Tipo.ERROS_CLASSICOS, "- **N-gon**: face com mais de 4 lados.")
    escrever(e00, Peca.Tipo.CRITICA_DE_ATELIER, "Procure algum N-Gon sobrando.")

    (defeito,) = coerencia.conferir(e00)

    assert defeito.codigo == coerencia.NOME_FORA_DO_CANONICO
    assert "N-gon" in defeito.o_que_fazer


def test_sem_negrito_na_peca_de_erros_classicos_o_revisor_fica_calado(e00):
    """Adivinhar nome de defeito em prosa corrida seria falso positivo."""
    escrever(e00, Peca.Tipo.ERROS_CLASSICOS, "O erro mais comum e a face invertida.")
    escrever(e00, Peca.Tipo.CRITICA_DE_ATELIER, "Procure Face Invertida sobrando.")

    assert coerencia.conferir(e00) == []


# ---------------------------------------------------------------------------
# 3. O NOME DE ARQUIVO QUE MUDA ENTRE AS PECAS
# ---------------------------------------------------------------------------
def test_o_mesmo_arquivo_com_duas_grafias_e_defeito(e00):
    escrever(e00, Peca.Tipo.EU_FACO, "Salve como cadeira_final.blend.")
    escrever(e00, Peca.Tipo.VOCE_FAZ, "Abra o Cadeira-Final.blend e continue.")

    (defeito,) = coerencia.conferir(e00)

    assert defeito.codigo == coerencia.NOME_DE_ARQUIVO_DIVERGENTE
    assert "cadeira_final.blend" in defeito.frase
    assert "Cadeira-Final.blend" in defeito.frase
    assert defeito.peca == ""


def test_o_mesmo_arquivo_com_a_mesma_grafia_nao_e_defeito(e00):
    escrever(e00, Peca.Tipo.EU_FACO, "Salve como cadeira_final.blend.")
    escrever(e00, Peca.Tipo.VOCE_FAZ, "Abra o cadeira_final.blend e continue.")

    assert coerencia.conferir(e00) == []


def test_dois_arquivos_de_verdade_diferentes_nao_sao_defeito(e00):
    escrever(e00, Peca.Tipo.EU_FACO, "Entregue cadeira.blend e cadeira.png.")

    assert coerencia.conferir(e00) == []


def test_a_prosa_antes_do_nome_do_arquivo_nao_entra_no_nome(e00):
    escrever(e00, Peca.Tipo.EU_FACO, "o arquivo cadeira.blend fica na pasta")
    escrever(e00, Peca.Tipo.VOCE_FAZ, "abra o cadeira.blend agora")

    assert coerencia.conferir(e00) == []


# ---------------------------------------------------------------------------
# 4. O NUMERO QUE MUDA ENTRE AS PECAS
# ---------------------------------------------------------------------------
def test_a_mesma_contagem_com_dois_numeros_e_defeito(e00):
    escrever(e00, Peca.Tipo.EU_FACO, "Sao 4 passos ate a base.")
    escrever(e00, Peca.Tipo.NOS_FAZEMOS, "Agora os 6 passos comigo.")

    (defeito,) = coerencia.conferir(e00)

    assert defeito.codigo == coerencia.NUMERO_DIVERGENTE
    assert "passo" in defeito.frase
    assert "4" in defeito.frase and "6" in defeito.frase


def test_a_mesma_contagem_com_o_mesmo_numero_nao_e_defeito(e00):
    escrever(e00, Peca.Tipo.EU_FACO, "Sao 4 passos ate a base.")
    escrever(e00, Peca.Tipo.NOS_FAZEMOS, "Os mesmos 4 passos, agora comigo.")

    assert coerencia.conferir(e00) == []


def test_contagens_de_coisas_diferentes_nao_se_confundem(e00):
    escrever(e00, Peca.Tipo.EU_FACO, "Sao 4 passos e 3 drills.")

    assert coerencia.conferir(e00) == []


def test_dois_tempos_diferentes_nao_sao_defeito(e00):
    """O recall dura um tempo e o drill outro: tempo nao e contagem da aula."""
    escrever(e00, Peca.Tipo.RECALL, "Voce tem 2 minutos.")
    escrever(e00, Peca.Tipo.DRILLS, "Cada drill leva 5 minutos.")

    assert coerencia.conferir(e00) == []


# ---------------------------------------------------------------------------
# 5. O "ACEITO QUANDO" CONTRA A LISTA DO CHECKPOINT
# ---------------------------------------------------------------------------
def test_a_lista_da_peca_diferente_da_do_formulario_e_defeito(e00):
    e00.aceito_quando = ["o cubo tem bevel"]
    e00.save(update_fields=["aceito_quando"])
    escrever(
        e00,
        Peca.Tipo.VOCE_FAZ,
        "Aceito quando\n\n- o cubo tem bevel\n- a base esta apoiada\n",
    )

    (defeito,) = coerencia.conferir(e00)

    assert defeito.codigo == coerencia.ACEITO_QUANDO_DIVERGENTE
    assert defeito.peca == Peca.Tipo.VOCE_FAZ
    assert "2" in defeito.frase and "1" in defeito.frase


def test_a_lista_igual_nao_e_defeito(e00):
    e00.aceito_quando = ["o cubo tem bevel", "a base esta apoiada"]
    e00.save(update_fields=["aceito_quando"])
    escrever(
        e00,
        Peca.Tipo.VOCE_FAZ,
        "## Aceito quando\n\n1. O cubo tem bevel\n2. A base esta apoiada\n\n"
        "Depois disso, envie.",
    )

    assert coerencia.conferir(e00) == []


def test_a_peca_que_nao_declara_aceito_quando_fica_calada(e00):
    e00.aceito_quando = ["o cubo tem bevel"]
    e00.save(update_fields=["aceito_quando"])
    escrever(e00, Peca.Tipo.VOCE_FAZ, "Agora e com voce. Refaca o exercicio.")

    assert coerencia.conferir(e00) == []


def test_a_peca_que_declara_e_nao_lista_nada_e_defeito(e00):
    e00.aceito_quando = ["o cubo tem bevel"]
    e00.save(update_fields=["aceito_quando"])
    escrever(e00, Peca.Tipo.VOCE_FAZ, "Aceito quando\n\nvoce achar que ficou bom.")

    assert codigos(e00) == [coerencia.ACEITO_QUANDO_DIVERGENTE]


# ---------------------------------------------------------------------------
# 6. O NUMERO DE PLATAFORMA NO CORPO
# ---------------------------------------------------------------------------
def test_o_limite_de_triangulos_cravado_e_defeito(e00):
    escrever(e00, Peca.Tipo.PEDIDO, "O limite e de 20000 triangulos por peca.")

    (defeito,) = coerencia.conferir(e00)

    assert defeito.codigo == coerencia.NUMERO_DE_PLATAFORMA
    assert "triangulo" in defeito.frase
    assert "apendice vivo" in defeito.o_que_fazer


def test_a_taxa_cravada_e_defeito(e00):
    escrever(e00, Peca.Tipo.PAGINA_DO_PORTFOLIO, "A taxa e de 30 por cento hoje.")

    assert codigos(e00) == [coerencia.NUMERO_DE_PLATAFORMA]


def test_a_contagem_que_a_tela_calcula_e_defeito(e00):
    escrever(e00, Peca.Tipo.CHECKPOINT, "Responda as 5 perguntas do quiz.")

    (defeito,) = coerencia.conferir(e00)

    assert defeito.codigo == coerencia.NUMERO_DE_PLATAFORMA
    assert "5 perguntas" in defeito.frase


def test_o_numero_de_plataforma_na_peca_interna_da_professora_nao_e_defeito(e00):
    """O `guia_do_mentor` e a mesa de trabalho dela, e nao o capitulo."""
    escrever(e00, Peca.Tipo.GUIA_DO_MENTOR, "Hoje o limite e de 20000 triangulos.")
    escrever(e00, Peca.Tipo.ROTEIRO, "A moderacao leva 48 horas em media.")

    assert coerencia.conferir(e00) == []


def test_numero_que_nao_e_de_plataforma_nao_e_defeito(e00):
    escrever(e00, Peca.Tipo.EU_FACO, "Aumente o bevel para 0,2 e olhe a aresta.")

    assert coerencia.conferir(e00) == []


def test_a_palavra_de_plataforma_sem_numero_nao_e_defeito(e00):
    escrever(e00, Peca.Tipo.PEDIDO, "Fique de olho no limite de triangulos do Roblox.")

    assert coerencia.conferir(e00) == []


# ---------------------------------------------------------------------------
# O CONJUNTO
# ---------------------------------------------------------------------------
def test_as_seis_conferencias_estao_ligadas(e00):
    """Uma sexta conferencia que nascesse desligada de `conferir` passaria em
    todos os testes acima e nao apontaria nada na tela."""
    assert len(coerencia.AS_SEIS) == 6


def test_so_a_remissao_quebrada_impede_publicar(e00):
    escrever(e00, Peca.Tipo.PEDIDO, "O limite e de 20000 triangulos.")
    escrever(e00, Peca.Tipo.DRILLS, "Volte na E99 e na Rubrica de encomenda.")

    impedem = coerencia.impedem_publicar(e00)

    assert [defeito.codigo for defeito in impedem] == [coerencia.REMISSAO_QUEBRADA]
    assert len(coerencia.conferir(e00)) == 3


def test_o_revisor_nao_grava_nada(e00):
    """Ele aponta, e so. Nenhuma versao sobe, nenhum estado muda."""
    escrever(e00, Peca.Tipo.DRILLS, "Volte na E99.")
    antes = (e00.versao, e00.estado, e00.publicada_em)

    coerencia.conferir(e00)

    e00.refresh_from_db()
    assert (e00.versao, e00.estado, e00.publicada_em) == antes
