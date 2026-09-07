"""A espera que substitui a posição, e o `null` que ela devolve sem vergonha.

O guarda que importa aqui não é o do número certo: é o do NUMERO AUSENTE. Uma
estimativa chutada num Mural recém-aberto é pior que nenhuma, porque o aluno
organiza a semana em cima dela e a plataforma não tinha como saber (plano §5.4).
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.encomendas import espera
from apps.encomendas.models import (
    Encomenda,
    Parametro,
    ParametroAusente,
    PerfilProfissional,
    Pessoa,
)
from tests.conftest import SITE_PADRAO


def oferecer(encomenda):
    """Uma encomenda saindo da fila, pela porta de verdade: é a transição que o
    livro de mudanças registra, e é ela que o ritmo conta."""
    encomenda.mudar_status(Encomenda.Status.OFERECIDA, motivo="cenario do guarda")


def test_sem_nenhuma_encomenda_oferecida_a_espera_e_nula(semeado, tres_na_fila):
    """O caso dos primeiros meses, e o mais importante de todos."""
    assert (
        espera.estimar_dias(tres_na_fila[0], timezone.now(), site_id=SITE_PADRAO)
        is None
    )


def test_com_ritmo_medido_a_espera_sai_em_dias(semeado, tres_na_fila, criar_encomenda):
    """Trinta encomendas oferecidas em trinta dias é uma por dia; quem é o
    primeiro da fila espera cerca de um dia, e o terceiro, cerca de três."""
    for _ in range(30):
        oferecer(criar_encomenda())
    agora = timezone.now()
    assert espera.estimar_dias(tres_na_fila[0], agora, site_id=SITE_PADRAO) == 1
    assert espera.estimar_dias(tres_na_fila[2], agora, site_id=SITE_PADRAO) == 3


def test_arredonda_para_cima(semeado, tres_na_fila, criar_encomenda):
    """Prometer menos do que se sabe é a única direção em que o erro machuca:
    o aluno programa a semana em cima deste número."""
    for _ in range(20):
        oferecer(criar_encomenda())
    # Vinte em trinta dias dá dois terços por dia; o primeiro da fila espera 1,5,
    # e o que a porta diz é 2.
    assert (
        espera.estimar_dias(tres_na_fila[0], timezone.now(), site_id=SITE_PADRAO) == 2
    )


def test_encomenda_de_nivel_fora_do_alcance_nao_conta(
    semeado, tres_na_fila, criar_encomenda
):
    """Ritmo de projeto que esta pessoa não pode pegar não anda a fila dela, e
    contá-lo prometeria uma vez rápida que não existe."""
    for _ in range(30):
        oferecer(criar_encomenda(nivel=Encomenda.Nivel.AVANCADO))
    # Os três da fixture são Nível 1, e o avançado exige Nível 3.
    assert (
        espera.estimar_dias(tres_na_fila[0], timezone.now(), site_id=SITE_PADRAO)
        is None
    )


def test_quem_ainda_nao_tem_titulo_nao_alcanca_nivel_nenhum(semeado, criar_perfil):
    """Título vazio é quem ainda não passou pelo plantão (lei §3.6). Ela não tem
    espera porque não tem vez nenhuma a caminho, e dizer um número seria mentir
    sobre a fila dela."""
    agora = timezone.now()
    sem_titulo = criar_perfil(
        "pes-sem-titulo", entrada=agora - timedelta(days=1), titulo=""
    )
    assert espera.niveis_ao_alcance("") == ()
    assert espera.estimar_dias(sem_titulo, agora, site_id=SITE_PADRAO) is None


def test_quem_nunca_ativou_a_fila_nao_tem_lugar(semeado, criar_encomenda):
    """`data_entrada_fila` nulo é AUSENCIA, não atraso. Inventar um lugar para
    quem não entrou seria prometer uma vez a quem não está esperando por
    nenhuma."""
    for _ in range(30):
        oferecer(criar_encomenda())
    fora = PerfilProfissional.objects.create(
        pessoa=Pessoa.objects.create(id_da_plataforma="pes-fora"),
        site_id=SITE_PADRAO,
        titulo_banca=PerfilProfissional.Titulo.NIVEL_1,
        titulo_dado_por="prof-1",
        titulo_dado_em=timezone.now(),
        data_entrada_fila=None,
    )
    assert espera.posicao_na_fila(fora, site_id=SITE_PADRAO) is None
    assert espera.estimar_dias(fora, timezone.now(), site_id=SITE_PADRAO) is None


def test_a_janela_e_parametro_e_nao_numero_em_codigo(
    semeado, tres_na_fila, criar_encomenda
):
    """A lei §3.8 não abre exceção para "é só um número pequeno".

    Com a janela em trinta dias, trinta encomendas dão uma por dia. Encurtando a
    janela para dez, as mesmas trinta viram três por dia, e a espera do primeiro
    cai. Se este teste ficar verde depois de a linha nova entrar, o número
    voltou para o código.
    """
    for _ in range(30):
        oferecer(criar_encomenda())
    agora = timezone.now()
    assert espera.encomendas_por_dia(tres_na_fila[0], agora, site_id=SITE_PADRAO) == 1.0
    Parametro.objects.create(
        site_id=SITE_PADRAO,
        chave=espera.CHAVE_DA_JANELA,
        valor="10",
        desde=agora,
        motivo="o guarda mede que a janela sai do banco",
        quem="prof-1",
    )
    depois = timezone.now()
    assert (
        espera.encomendas_por_dia(tres_na_fila[0], depois, site_id=SITE_PADRAO) == 3.0
    )


def test_sem_a_linha_do_parametro_a_conta_recusa_em_vez_de_chutar(
    db, criar_perfil, criar_encomenda
):
    """Semeadura que não rodou é ERRO, e não um padrão embutido: um padrão em
    código seria a constante mágica que a lei §3.8 proíbe, e ele esconderia
    exatamente esta instalação pela metade."""
    agora = timezone.now()
    perfil = criar_perfil("pes-solo", entrada=agora - timedelta(days=1))
    oferecer(criar_encomenda())
    with pytest.raises(ParametroAusente):
        espera.encomendas_por_dia(perfil, agora, site_id=SITE_PADRAO)
