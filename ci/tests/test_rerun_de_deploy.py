"""Guardas da vacina da armadilhas/127 (ci/rerun_de_deploy.py).

A tabela de decisão é o coração deste script, e ela é PURA de propósito: colher
os fatos (gh, socket, http) e decidir o que fazer são funções separadas, então
todos os ramos podem ser provados sem rede, sem `gh` e sem VPS. Um script de
automação de deploy que só desse para testar contra a produção nunca seria
testado — e um automatismo não testado que REPETE deploys é pior que o
procedimento manual que ele substitui.

O que estes testes protegem, e por quê cada um existe:

- **Só repete o que é a 127.** Repetir uma falha de código não conserta código;
  trataria defeito real como blip e o esconderia atrás de três tentativas.
- **Porta 22 morta não é blip.** É a armadilhas/017, falha PERMANENTE de
  configuração — repetir só gasta tempo, e o conserto passa pelo mantenedor.
- **Não medir nunca vira permissão** (INV-CI01): sem a medição da porta, o
  script para com ERROR em vez de repetir na esperança.
- **A regra de parada existe.** Três vermelhos com a porta viva e ele para,
  entregando o texto da pendência. A quarta tentativa não é diagnóstico.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import rerun_de_deploy as vacina  # noqa: E402


def _fatos(**kwargs) -> vacina.Fatos:
    base = dict(run="123", status="completed", conclusion="failure")
    base.update(kwargs)
    return vacina.Fatos(**base)


# ----------------------------------------------------- o que NÃO se repete ----


def test_run_verde_nao_se_repete():
    decisao = vacina.decidir(_fatos(conclusion="success"))
    assert decisao.acao == "nada"
    assert decisao.codigo == 0


def test_run_em_andamento_e_ERROR_nao_veredito():
    """Medir pela metade não vira veredito."""
    decisao = vacina.decidir(_fatos(status="in_progress", conclusion=""))
    assert decisao.codigo == 2


def test_falha_que_nao_e_de_ssh_para_e_manda_ler_o_log():
    decisao = vacina.decidir(_fatos(tem_timeout_ssh=False))
    assert decisao.acao == "parar"
    assert decisao.codigo == 1
    assert "log-failed" in decisao.motivo, "parar sem ensinar onde olhar não ajuda"


def test_falha_de_autenticacao_nao_se_repete():
    """Chave/usuário é território do mantenedor: repetir não conserta credencial."""
    decisao = vacina.decidir(
        _fatos(tem_timeout_ssh=True, tem_falha_de_autenticacao=True,
               porta22_viva=True)
    )
    assert decisao.acao == "parar"
    assert "AUTENTICAÇÃO" in decisao.motivo


def test_run_cancelado_nao_se_repete():
    decisao = vacina.decidir(_fatos(conclusion="cancelled"))
    assert decisao.acao == "nada"
    assert decisao.codigo == 1


# -------------------------------------------- 127 (blip) contra 017 (fixa) ----


def test_porta_viva_com_timeout_e_blip_entao_repete():
    decisao = vacina.decidir(
        _fatos(tem_timeout_ssh=True, porta22_viva=True, site_http=200)
    )
    assert decisao.acao == "repetir"
    assert decisao.codigo == 0


def test_porta_morta_e_a_017_e_para_com_pendencia():
    decisao = vacina.decidir(
        _fatos(tem_timeout_ssh=True, porta22_viva=False, site_http=200)
    )
    assert decisao.acao == "parar"
    assert "017" in decisao.motivo
    assert decisao.pendencia, "a 017 precisa chegar ao mantenedor, não morrer no log"
    assert "NÃO está em produção" in decisao.pendencia


def test_porta_nao_medida_e_ERROR_e_nao_uma_tentativa_otimista():
    decisao = vacina.decidir(
        _fatos(tem_timeout_ssh=True, porta22_viva=None)
    )
    assert decisao.acao == "nada"
    assert decisao.codigo == 2, "não medir não pode virar 'pode repetir'"


# ------------------------------------------------------ regra de parada ----


@pytest.mark.parametrize("tentativas, acao", [(0, "repetir"), (1, "repetir"),
                                              (2, "repetir"), (3, "parar")])
def test_a_regra_de_parada_e_de_tres(tentativas: int, acao: str):
    decisao = vacina.decidir(
        _fatos(tem_timeout_ssh=True, porta22_viva=True, site_http=200,
               tentativas_feitas=tentativas)
    )
    assert decisao.acao == acao


def test_ao_parar_a_pendencia_diz_que_o_site_esta_no_ar():
    """O que o mantenedor precisa saber: ninguém caiu, mas o merge não subiu."""
    decisao = vacina.decidir(
        _fatos(tem_timeout_ssh=True, porta22_viva=True, site_http=200,
               tentativas_feitas=3)
    )
    assert "continua no ar" in decisao.pendencia
    assert "ANTIGA" in decisao.pendencia


def test_a_pendencia_alerta_quando_o_site_tambem_caiu():
    decisao = vacina.decidir(
        _fatos(tem_timeout_ssh=True, porta22_viva=True, site_http=502,
               tentativas_feitas=3)
    )
    assert "ATENÇÃO" in decisao.pendencia


# ------------------------------------------------- as assinaturas do log ----


def test_reconhece_o_timeout_real_que_aconteceu_em_29_08():
    log = "2026/08/29 19:51:29 dial tcp ***:22: i/o timeout"
    assert vacina.RE_TIMEOUT_SSH.search(log)


def test_nao_confunde_outro_timeout_com_o_da_porta_22():
    assert not vacina.RE_TIMEOUT_SSH.search("dial tcp 10.0.0.1:5432: i/o timeout")


def test_reconhece_falha_de_autenticacao():
    assert vacina.RE_SSH_AUTENTICACAO.search("ssh: handshake failed: ...")


# --------------------------------------------------- a entrada está viva ----


def test_a_entrada_127_declara_esta_vacina_como_sua_guarda():
    """A DECLARAÇÃO estruturada, não uma menção qualquer no texto.

    Procurar o nome do arquivo no corpo passaria só por a entrada citar o
    comando num exemplo — e o índice continuaria podendo mentir sobre quem faz
    a lição valer. O que vale é o campo `guarda.dono` do frontmatter, que é o
    que o gerador lê para montar a coluna.
    """
    import indice_de_armadilhas as indice
    from _nucleo import raiz_do_repo

    raiz = raiz_do_repo()
    entradas = [e for e in indice.coletar(raiz) if e.numero == "127"]
    assert entradas, "a vacina cita a armadilhas/127, que precisa existir"
    guarda = entradas[0].guarda
    assert guarda.get("tipo") == "vacina", f"tipo declarado: {guarda.get('tipo')}"
    assert guarda.get("dono") == "ci/rerun_de_deploy.py", (
        "a entrada precisa declarar ESTA vacina como sua guarda — senão o "
        f"índice segue dizendo que ninguém a faz valer (veio: {guarda.get('dono')})"
    )
