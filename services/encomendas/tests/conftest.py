"""As peças que os sete guardas de justiça montam para medir o motor.

Sete arquivos `test_inv_j*.py` precisam do mesmo cenário mínimo — parâmetros
semeados, perfis com título e lugar na fila, encomendas esperando — e escrever
esse cenário sete vezes garantiria que seis cópias envelhecessem em silêncio.

**O que NÃO mora aqui:** nenhuma regra. As fábricas montam estado; quem julga é
o motor, e quem afirma é cada guarda. Uma fábrica que decidisse quem é elegível
seria o teste medindo a própria resposta.

Duas escolhas com motivo escrito:

- **O `agora` de cada guarda é o relógio REAL** (`datetime.now(tz=utc)`), nunca
  um instante fixo. `Oferta.oferecida_em` é `auto_now_add`, e a restrição
  `oferta_expira_depois_de_oferecida` compara os dois: com um instante fixo, o
  arquivo passa até o relógio da máquina ultrapassá-lo e fica vermelho sozinho
  (`armadilhas/323`, medida nesta célula em 04/09/2026).
- **Os parâmetros vêm do semeador**, não de linhas escritas à mão. É o mesmo
  caminho que a instalação da célula percorre, e um cenário que grava os
  próprios valores provaria o motor contra números que ninguém usa.
"""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command

from apps.encomendas import mural
from apps.encomendas.models import (
    ESTADOS_DO_MURAL_RESERVAVEL,
    Encomenda,
    PerfilProfissional,
    Pessoa,
)

SITE_PADRAO = "escola-a"

# O cartão decide o nível, e o banco recusa o par errado
# (`o_cartao_decide_o_nivel`). A tabela mora aqui, e não dentro de cada fábrica,
# porque duas fábricas a usam e duas cópias divergiriam no primeiro cartão novo.
CARTAO_DO_NIVEL = {
    Encomenda.Nivel.INICIANTE: Encomenda.Cartao.ITEM_SIMPLES,
    Encomenda.Nivel.INTERMEDIARIO: Encomenda.Cartao.VESTIVEL_OU_VEICULO,
    Encomenda.Nivel.AVANCADO: Encomenda.Cartao.PERSONAGEM,
}


@pytest.fixture
def semeado(db):
    """Os 28 parâmetros no banco, pelo caminho da instalação.

    Vinte e sete da lei §6, mais o `relogio_da_reserva_no_mural` do §9 do
    `PLANO-AREA-DE-NEGOCIACAO.md`, que chegou com o Mural.
    """
    call_command("semear_parametros", site=SITE_PADRAO, stdout=StringIO())
    return SITE_PADRAO


@pytest.fixture
def criar_perfil(db):
    """Fábrica de perfil profissional pronto para receber oferta.

    Os padrões são o caso comum da fila: título Nível 1 dado pelo professor,
    disponível, zero entregas, na fila desde ontem. Cada guarda muda SÓ o campo
    que ele mede, e é isso que faz o vermelho apontar para uma linha.
    """

    def fabrica(
        id_da_pessoa,
        *,
        entrada,
        titulo=PerfilProfissional.Titulo.NIVEL_1,
        entregas=0,
        disponibilidade=PerfilProfissional.Disponibilidade.DISPONIVEL,
        abandonos=None,
        site_id=SITE_PADRAO,
    ):
        pessoa = Pessoa.objects.create(id_da_plataforma=id_da_pessoa)
        return PerfilProfissional.objects.create(
            pessoa=pessoa,
            site_id=site_id,
            titulo_banca=titulo,
            # Título tem autor e data, e o banco exige os três juntos
            # (`titulo_de_banca_tem_autor_e_data`). Quem dá o título é o
            # professor, até a Banca existir (lei §3.6).
            titulo_dado_por="prof-1" if titulo else "",
            titulo_dado_em=entrada if titulo else None,
            entregas_aprovadas=entregas,
            disponibilidade=disponibilidade,
            data_entrada_fila=entrada,
            abandonos=abandonos or [],
        )

    return fabrica


@pytest.fixture
def criar_encomenda(db):
    """Fábrica de encomenda esperando na fila.

    Nasce `origem=escola` porque até a Fase 3 essa é a única origem que entra na
    fila (lei §3.4: dinheiro por último, e a escola é o primeiro cliente). O
    cartão decide o nível, e o banco recusa o par errado
    (`o_cartao_decide_o_nivel`) — por isso os dois andam juntos aqui.
    """

    def fabrica(
        *,
        nivel=Encomenda.Nivel.INICIANTE,
        cliente="cli-1",
        status=Encomenda.Status.NA_FILA,
        site_id=SITE_PADRAO,
    ):
        return Encomenda.objects.create(
            site_id=site_id,
            origem=Encomenda.Origem.ESCOLA,
            cliente_id=cliente,
            cartao=CARTAO_DO_NIVEL[nivel],
            nivel=nivel,
            status=status,
            # A coluna `pista` não pode mentir sobre onde o projeto está sendo
            # mostrado, e o banco recusa o par incoerente
            # (`no_mural_so_na_pista_do_mural`). A fábrica deriva a pista do
            # status pedido, e não do nível, porque quem chama aqui está
            # montando um cenário no meio da vida da encomenda, não o
            # nascimento dela. O nascimento tem porta própria: `mural.nascer`,
            # e é a fixture `criar_projeto_no_mural` que a usa.
            pista=(
                Encomenda.Pista.MURAL
                if status in ESTADOS_DO_MURAL_RESERVAVEL
                else Encomenda.Pista.FILA
            ),
        )

    return fabrica


@pytest.fixture
def criar_projeto_no_mural(db):
    """Fábrica de projeto do Mural, pela MESMA porta que a Fase 3 vai usar.

    Passa por `mural.nascer`, e não por um `create` próprio, pela mesma razão
    que a fixture `semeado` chama o semeador: um cenário que monta o estado por
    fora prova o código contra um nascimento que ninguém faz. A pista e o
    estado inicial vêm da regra, e o teste não os informa.

    O nível padrão é o INTERMEDIÁRIO porque é o primeiro que nasce no Mural: o
    Iniciante nasce na fila, e um projeto Iniciante criado por aqui iria para a
    outra pista, que é justamente o [INV-ENC-M2].
    """

    def fabrica(
        *,
        nivel=Encomenda.Nivel.INTERMEDIARIO,
        cliente="cli-1",
        site_id=SITE_PADRAO,
    ):
        return mural.nascer(
            site_id=site_id,
            origem=Encomenda.Origem.ESCOLA,
            cliente_id=cliente,
            cartao=CARTAO_DO_NIVEL[nivel],
        )

    return fabrica


@pytest.fixture
def dois_no_mural(semeado, criar_perfil):
    """Dois alunos que já entregaram, que são quem enxerga o Mural.

    A Ana é Nível 2 com uma entrega aprovada (o mínimo do Intermediário) e o Bru
    é Nível 3 com cinco (o mínimo do Avançado). Os dois estão disponíveis e na
    fila há tempos, então a única coisa que os separa de um projeto é a régua de
    elegibilidade, que é exatamente o que os guardas do Mural medem.
    """
    from datetime import datetime, timezone as fuso

    agora = datetime.now(tz=fuso.utc)
    return [
        criar_perfil(
            "pes-ana",
            entrada=agora - timedelta(days=30),
            titulo=PerfilProfissional.Titulo.NIVEL_2,
            entregas=1,
        ),
        criar_perfil(
            "pes-bru",
            entrada=agora - timedelta(days=20),
            titulo=PerfilProfissional.Titulo.NIVEL_3,
            entregas=5,
        ),
    ]


@pytest.fixture
def tres_na_fila(semeado, criar_perfil):
    """Três alunos idênticos, separados só pela data de entrada.

    É o cenário em que a regra da lei §6.2 é visível a olho nu: todos com zero
    entregas, então o desempate é a data, e a ordem esperada é a do alfabeto dos
    nomes. Quem quiser medir a PRIMEIRA metade da regra (menos entregas) muda as
    entregas e a ordem tem de virar.
    """
    from datetime import datetime, timezone as fuso

    agora = datetime.now(tz=fuso.utc)
    return [
        criar_perfil("pes-ana", entrada=agora - timedelta(days=30)),
        criar_perfil("pes-bia", entrada=agora - timedelta(days=20)),
        criar_perfil("pes-caio", entrada=agora - timedelta(days=10)),
    ]
