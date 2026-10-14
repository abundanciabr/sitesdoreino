"""Quem é liberado entra NA HORA, e a tela leva a pessoa para o site.

**O defeito, medido em 28/08/2026 com o mantenedor.** Ele liberou a própria
conta pelo painel; a pessoa saiu da fila na hora; e a Caixa continuou
recusando. Causa: `_tem_matricula` guardava a resposta **"não é aluno" por 10
minutos**, o mesmo TTL do "sim". Aquele número foi escrito quando a única forma
de virar aluno era COMPRAR — um caminho assíncrono, sem ninguém olhando. A fila
de liberação mudou o cenário (agora há alguém esperando na frente da tela,
enquanto outra pessoa aperta o botão) e o TTL não acompanhou.

E a tela **prometia** o que o cache impedia, com todas as letras: *"quando
estiver liberado, esta página abre a Caixa"*.

Três coisas ficam travadas aqui:

1. **A assimetria dos dois TTLs.** É a correção, e ela é assimétrica de
   propósito: um "sim" velho custa acesso a mais por alguns minutos a quem o
   perdeu — raro e sem urgência; um "não" velho custa uma pessoa **barrada
   depois de já ter sido liberada**, olhando para uma tela que lhe promete o
   contrário. Guardar os dois pelo mesmo tempo é tratar como iguais dois erros
   de custo muito diferente.

2. **O recibo se recarrega sozinho — e o formulário NÃO.** Um refresh no
   formulário apagaria o que a pessoa está digitando, e ela ainda não tem nada
   para esperar.

3. **Liberado enquanto esperava vai para o SITE, não para a porta da Caixa.**
   Decisão do mantenedor em 28/08/2026. E só quem chega pelo relógio: sem essa
   distinção, quem acabou de fazer login pela Caixa seria jogado para a home e
   teria de clicar de novo para entrar onde já estava indo.
"""

import time

import pytest
from django.urls import reverse

from apps.core import sessao as ses

from tests.conftest import sessao_do_site

PESSOA = "quem.espera@exemplo.test"


@pytest.fixture(autouse=True)
def cache_limpo():
    ses.limpar_caches()
    yield
    ses.limpar_caches()


def _validade_guardada(email: str) -> float:
    """Quanto tempo, a partir de agora, a resposta guardada ainda vale."""
    expira, _ = ses._CACHE_DE_MATRICULA[email.strip().lower()]
    return expira - time.time()


# --------------------------------------------------- 1. a assimetria dos TTLs


def test_o_nao_e_esquecido_depressa_e_o_sim_nao(rede, db, matricula):
    """A correção, medida nos dois lados na mesma prova.

    Desde 28/08/2026 a porta guarda a CATEGORIA em vez de um sim/não,
    e a assimetria continua a
    mesma: só "aluno" pode envelhecer.

    Sem a assimetria, este teste é impossível de satisfazer: um TTL só teria de
    ser curto (e o "sim" custaria um salto de rede por página) ou longo (e o
    "não" barraria quem acabou de ser liberado).
    """
    rede.alunos_nao_conhece(PESSOA)
    assert ses._situacao(PESSOA) == "cadastrado"
    validade_do_nao = _validade_guardada(PESSOA)

    ses.limpar_caches()
    rede.alunos_diz(PESSOA, [matricula])
    assert ses._situacao(PESSOA) == "aluno"
    validade_do_sim = _validade_guardada(PESSOA)

    assert validade_do_nao <= 15, (
        "o 'não é aluno' voltou a ser guardado por muito tempo — é isso que "
        "barra quem acabou de ser liberado"
    )
    assert validade_do_sim > validade_do_nao * 10, (
        "o 'sim' encurtou junto: cada página de aluno passa a custar um salto "
        "de rede sem necessidade"
    )


def test_liberado_entra_assim_que_o_nao_envelhece(rede, db, matricula):
    """O caminho REAL do defeito, do começo ao fim.

    A pessoa bate na porta (não é aluna), o mantenedor libera, e a pergunta
    seguinte tem de enxergar a mudança. O relógio é adiantado mexendo na
    validade guardada — e não em `time.time()` — para o teste medir a REGRA de
    expiração, não o relógio do sistema.
    """
    rede.alunos_nao_conhece(PESSOA)
    assert ses._situacao(PESSOA) == "cadastrado"

    # O mantenedor libera: a `alunos` passa a responder que há matrícula.
    rede.alunos_diz(PESSOA, [matricula])
    # Ainda dentro da janela curta, a resposta guardada continua valendo — e
    # isso É o desenho: a janela existe para segurar rajada.
    assert ses._situacao(PESSOA) == "cadastrado"

    chave = PESSOA.lower()
    expira, valor = ses._CACHE_DE_MATRICULA[chave]
    ses._CACHE_DE_MATRICULA[chave] = (expira - ses.TTL_SEM_MATRICULA - 1, valor)

    assert ses._situacao(PESSOA) == "aluno", (
        "passada a janela curta, a Caixa continuou recusando quem já foi "
        "liberado — é o defeito de 28/08/2026 de volta"
    )



@pytest.mark.parametrize('marca',['','?esperando=1'])
def test_liberado_e_encaminhado_pelo_login_sem_marca_de_caixa(entrar_como,marca):
    pessoa=entrar_como(PESSOA)
    resposta=pessoa.client.get(reverse('entrar')+marca)
    assert resposta.status_code == 302
    assert resposta['Location'] == '/login?next=%2F'
    assert pessoa.esta_dentro

@pytest.mark.parametrize('marca',['','?esperando=1'])
def test_marca_antiga_nao_concede_acesso(rede,db,quadro,marca):
    rede.alunos_nao_conhece(PESSOA)
    pessoa=sessao_do_site(rede,email=PESSOA)
    assert pessoa.client.get(reverse('entrar')+marca)['Location'] == '/login?next=%2F'
    assert not pessoa.esta_dentro
