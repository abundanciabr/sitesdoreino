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

from apps.encomendas.models import Encomenda, PerfilProfissional, Pessoa

SITE_PADRAO = "escola-a"


@pytest.fixture
def semeado(db):
    """Os 27 parâmetros da lei §6 no banco, pelo caminho da instalação."""
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
    cartoes = {
        Encomenda.Nivel.INICIANTE: Encomenda.Cartao.ITEM_SIMPLES,
        Encomenda.Nivel.INTERMEDIARIO: Encomenda.Cartao.VESTIVEL_OU_VEICULO,
        Encomenda.Nivel.AVANCADO: Encomenda.Cartao.PERSONAGEM,
    }

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
            cartao=cartoes[nivel],
            nivel=nivel,
            status=status,
        )

    return fabrica


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
