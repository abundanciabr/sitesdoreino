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
from apps.core.views import DEPOIS_DE_LIBERADO, MARCA_DE_ESPERA
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

    Desde 28/08/2026 a porta guarda a CATEGORIA em vez de um sim/não
    (`DECISAO-ex-aluno-e-a-porta-que-explica`), e a assimetria continua a
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


# ------------------------------------------- 2. o recibo se recarrega sozinho


def test_o_recibo_se_recarrega_sozinho_e_aponta_para_a_marca(rede, db, quadro):
    rede.alunos_nao_conhece(PESSOA)
    pessoa = sessao_do_site(rede, email=PESSOA)
    rede.alunos_aceita_o_pedido()
    resposta = pessoa.client.post(
        reverse("pedir_entrada"),
        {"nome_completo": "Quem Espera", "whatsapp": "(96) 99999-0000"},
    )
    conteudo = resposta.content.decode()

    assert 'http-equiv="refresh"' in conteudo
    assert f"{MARCA_DE_ESPERA}=1" in conteudo


def test_o_formulario_nao_se_recarrega(rede, db, quadro):
    """Um refresh aqui apagaria o que a pessoa está digitando.

    E ela ainda não tem nada para esperar: o pedido não foi feito.
    """
    rede.alunos_nao_conhece(PESSOA)
    pessoa = sessao_do_site(rede, email=PESSOA)
    conteudo = pessoa.abrir().content.decode()

    assert "Pedir liberação" in conteudo, "não é a tela do formulário"
    assert 'http-equiv="refresh"' not in conteudo


def test_a_tela_nao_promete_mais_o_que_nao_acontece(rede, db, quadro):
    """A frase antiga dizia "esta página abre a Caixa" — e não abria.

    Trocar o texto sem trocar o comportamento seria maquiagem; trocar o
    comportamento sem trocar o texto deixaria a tela mentindo para o outro
    lado. Este guarda cobra os dois.
    """
    rede.alunos_nao_conhece(PESSOA)
    pessoa = sessao_do_site(rede, email=PESSOA)
    rede.alunos_aceita_o_pedido()
    conteudo = pessoa.client.post(
        reverse("pedir_entrada"),
        {"nome_completo": "Quem Espera", "whatsapp": "(96) 99999-0000"},
    ).content.decode()

    assert "esta página abre a Caixa" not in conteudo
    assert "se atualiza sozinha" in conteudo


# --------------------------------------- 3. liberado vai para o SITE


def test_quem_esperava_e_foi_liberado_vai_para_o_site(entrar_como):
    pessoa = entrar_como(PESSOA)
    resposta = pessoa.client.get(f"{reverse('entrar')}?{MARCA_DE_ESPERA}=1")

    assert resposta.status_code == 302
    assert resposta["Location"] == DEPOIS_DE_LIBERADO


def test_sem_a_marca_quem_entra_continua_caindo_na_porta(entrar_como):
    """Quem acabou de fazer login pela Caixa NÃO pode ser jogado para a home.

    O `_abrir` do login volta para esta porta de propósito. Sem a distinção
    pela marca, a pessoa teria de clicar de novo para entrar onde já estava
    indo — e o defeito seria invisível, porque "foi para a home" parece certo.
    """
    pessoa = entrar_como(PESSOA)
    resposta = pessoa.client.get(reverse("entrar"))

    assert resposta.status_code == 200
    assert "Ver o quadro de sugestões" in resposta.content.decode()


def test_a_marca_sozinha_nao_abre_porta_nenhuma(rede, db, quadro):
    """A marca é um SINAL de origem, nunca uma credencial.

    Quem ainda não foi liberado continua no recibo, com 403 — mesmo pedindo a
    página com a marca na mão.
    """
    rede.alunos_nao_conhece(PESSOA)
    pessoa = sessao_do_site(rede, email=PESSOA)
    resposta = pessoa.client.get(f"{reverse('entrar')}?{MARCA_DE_ESPERA}=1")

    assert resposta.status_code == 403
    assert "Location" not in resposta


def test_visitante_com_a_marca_nao_vira_ninguem(rede, db, quadro):
    """Sem sessão do site, a marca não muda nada."""
    from django.test import Client

    resposta = Client().get(f"{reverse('entrar')}?{MARCA_DE_ESPERA}=1")

    assert resposta.status_code == 200
    assert "Location" not in resposta
