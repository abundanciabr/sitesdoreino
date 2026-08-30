"""Guardas da vacina do deploy que não chegou (armadilhas/127 e /188).

A tabela de decisão é o coração deste script, e ela é PURA de propósito: colher
os fatos (gh, socket, http, git) e decidir o que fazer são funções separadas,
então todos os ramos podem ser provados sem rede, sem `gh` e sem VPS. Um script
de automação de deploy que só desse para testar contra a produção nunca seria
testado — e um automatismo não testado que REPETE deploys é pior que o
procedimento manual que ele substitui. As histórias abaixo são montadas à mão,
como as de `ci/tests/test_divida_do_livro.py`, justamente porque os desfechos
que decidem se a vacina é justa não se produzem sob encomenda em produção.

O que estes testes protegem, e por quê cada um existe:

- **Só repete o que é a 127.** Repetir uma falha de código não conserta código;
  trataria defeito real como blip e o esconderia atrás de três tentativas.
- **Porta 22 morta não é blip.** É a armadilhas/017, falha PERMANENTE de
  configuração — repetir só gasta tempo, e o conserto passa pelo mantenedor.
- **Não medir nunca vira permissão** (INV-CI01): sem a medição da porta, o
  script para com ERROR em vez de repetir na esperança.
- **A regra de parada existe.** Três vermelhos com a porta viva e ele para,
  entregando o texto da pendência. A quarta tentativa não é diagnóstico.
- **O cancelado tem DUAS causas opostas** (TAR-017, 30/08/2026). Cancelado de
  disparo manual é a armadilhas/173 e NÃO se cura repetindo; cancelado de PUSH
  é a armadilhas/188, e ali repetir É a cura — desde que republicar aquele SHA
  só avance. Enquanto os dois eram o mesmo ramo, a vacina mandava "não fazer
  nada" sobre um merge que estava fora do ar em silêncio.
"""

from __future__ import annotations

import subprocess
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


def test_run_cancelado_sem_saber_o_disparo_nao_se_repete():
    """Sem `event`, não dá para saber se é a 173 ou a 188: não se repete."""
    decisao = vacina.decidir(_fatos(conclusion="cancelled"))
    assert decisao.acao == "nada"
    assert decisao.codigo == 1


def test_run_pulado_nao_se_repete():
    decisao = vacina.decidir(_fatos(conclusion="skipped"))
    assert decisao.acao == "nada"
    assert decisao.codigo == 1
    assert "skipped" in decisao.motivo


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


# --------------------------- o cancelado: a 173 contra a 188 (TAR-017) ----


def _cancelado(**kwargs) -> vacina.Fatos:
    """Um deploy de PUSH cancelado, com a história já medida.

    Os SHAs são inventados de propósito: a decisão inteira é uma conta sobre
    booleanos que `colher()` já mediu, então ela se prova sem rede, sem `gh` e
    sem Git. O caso-base é o da origem da 188 — o publicado é ancestral do run
    cancelado, e nada volta se ele for republicado.
    """
    base = dict(
        conclusion="cancelled",
        event="push",
        head_sha="a" * 40,
        sha_publicado="b" * 40,
        publicado_e_ancestral=True,
        head_ja_publicado=False,
        commits_de_fora=0,
        commits_de_fora_tocam_o_deploy=False,
        site_http=200,
    )
    base.update(kwargs)
    return _fatos(**base)


def test_cancelado_de_push_com_o_publicado_ancestral_REPETE():
    """O desfecho 1 da 188: repetir só AVANÇA, e é a única cura.

    Este é o caso que a vacina errava até 30/08/2026: ela devolvia "NADA, não
    se cura repetindo", o agente fechava a tarefa, e o merge ficava na `main`
    sem estar em produção — sem log vermelho, sem alarme, sem ninguém olhando.
    """
    decisao = vacina.decidir(_cancelado())
    assert decisao.acao == "repetir"
    assert decisao.codigo == 0
    assert "188" in decisao.motivo
    assert decisao.rerun_apenas_falhados is False, (
        "run cancelado não tem job FALHADO: `gh run rerun --failed` não teria "
        "o que repetir, e a vacina ficaria girando sem publicar nada"
    )


def test_cancelado_de_push_com_o_publicado_divergente_PARA():
    """O desfecho 2 da 188: repetir seria um rollback silencioso."""
    decisao = vacina.decidir(
        _cancelado(publicado_e_ancestral=False, head_ja_publicado=False)
    )
    assert decisao.acao == "parar"
    assert decisao.codigo == 1
    assert "rollback silencioso" in decisao.motivo
    assert decisao.pendencia, (
        "um deploy que não chega ao ar precisa alcançar o mantenedor em texto, "
        "não morrer no log de uma sessão que já terminou"
    )
    assert "NÃO está em produção" in decisao.pendencia


def test_cancelado_de_disparo_manual_continua_sendo_a_173():
    """O desfecho 3: o cancelamento que de fato não se cura repetindo.

    Aqui a cura é dar grupo de concorrência próprio ao workflow, e um rerun só
    perderia a cadeira outra vez. A mensagem precisa NOMEAR o disparo — foi
    justamente a frase genérica "cancelamento não se cura repetindo" que fez
    um agente fechar a tarefa com o merge fora do ar (armadilhas/188).
    """
    decisao = vacina.decidir(_cancelado(event="workflow_dispatch"))
    assert decisao.acao == "nada"
    assert decisao.codigo == 1
    assert "173" in decisao.motivo
    assert "workflow_dispatch" in decisao.motivo, (
        "sem nomear o disparo, a mensagem serve para os dois casos — e serviu, "
        "com o merge fora do ar como consequência"
    )
    assert "188" not in decisao.motivo


def test_cancelado_de_push_ja_publicado_por_um_verde_mais_novo_nao_se_repete():
    """Repetir aqui republicaria um mundo mais VELHO. O merge já está no ar."""
    decisao = vacina.decidir(
        _cancelado(publicado_e_ancestral=False, head_ja_publicado=True)
    )
    assert decisao.acao == "nada"
    assert decisao.codigo == 0, "nada a fazer não é falha: o merge chegou ao ar"
    assert "JÁ está no ar" in decisao.motivo


def test_cancelado_de_push_cujo_sha_e_o_publicado_nao_se_repete():
    decisao = vacina.decidir(
        _cancelado(publicado_e_ancestral=True, head_ja_publicado=True)
    )
    assert decisao.acao == "nada"
    assert decisao.codigo == 0


@pytest.mark.parametrize(
    "campos",
    [
        {"publicado_e_ancestral": None},
        {"head_ja_publicado": None},
        {"sha_publicado": ""},
        {"head_sha": ""},
    ],
)
def test_sem_a_ancestralidade_medida_e_ERROR_e_nao_uma_tentativa(campos: dict):
    """'Não medi' nunca vira 'pode repetir' (INV-CI01).

    Sem os dois SHAs, ou sem a conta entre eles, repetir é apostar num
    rollback. O clone raso é o caso concreto: o commit pode simplesmente não
    existir neste checkout (armadilhas/159).
    """
    decisao = vacina.decidir(_cancelado(**campos))
    assert decisao.acao == "nada"
    assert decisao.codigo == 2


def test_a_regra_de_parada_tambem_vale_para_o_cancelado():
    """A cadeira musical pode expulsar o rerun também — e três basta."""
    decisao = vacina.decidir(_cancelado(tentativas_feitas=3))
    assert decisao.acao == "parar"
    assert decisao.codigo == 1
    assert decisao.pendencia
    assert "CANCELADO" in decisao.pendencia


# ---------------------------------- o que fica de fora do rerun (188 §d) ----


def test_o_recado_avisa_quando_nenhum_commit_de_fora_dispara_deploy():
    """A informação que decide entre 'espere o próximo deploy' e 'repita'."""
    decisao = vacina.decidir(
        _cancelado(commits_de_fora=4, commits_de_fora_tocam_o_deploy=False)
    )
    assert decisao.acao == "repetir"
    assert "nenhum deploy novo vai nascer" in decisao.recado
    assert "services/" in decisao.recado, (
        "dizer QUAIS pastas disparam deploy é o que permite conferir a conta"
    )


def test_o_recado_acalma_quando_os_commits_de_fora_tem_deploy_proprio():
    decisao = vacina.decidir(
        _cancelado(commits_de_fora=4, commits_de_fora_tocam_o_deploy=True)
    )
    assert "próprio deploy" in decisao.recado
    assert "não há o que perder" in decisao.recado


def test_o_recado_confessa_quando_nao_conseguiu_contar():
    decisao = vacina.decidir(
        _cancelado(commits_de_fora=None, commits_de_fora_tocam_o_deploy=None)
    )
    assert decisao.acao == "repetir", (
        "a contagem informa, não decide: quem decide é a ancestralidade"
    )
    assert "não consegui contar" in decisao.recado


# ------------------------------------------- as medições, contra o real ----


def test_os_paths_do_deploy_saem_do_workflow_de_verdade():
    """Nenhum fato do projeto mora em dois lugares (CLAUDE.md).

    Se esta lista fosse uma constante copiada, bastaria alguém acrescentar uma
    pasta ao gatilho do `deploy-celula` para a vacina passar a afirmar "nenhum
    deploy novo vai nascer" sobre um merge que nasce COM deploy — mentira dita
    exatamente na hora de decidir se repete.
    """
    from _nucleo import raiz_do_repo

    raiz = raiz_do_repo()
    prefixos = vacina.paths_do_deploy(raiz)
    assert prefixos, "sem os paths, o recado da 188 vira palpite"
    for prefixo in prefixos:
        assert (raiz / prefixo).is_dir(), (
            f"'{prefixo}' saiu do gatilho do deploy mas não é pasta deste "
            "repositório — a leitura do workflow está pegando outra coisa"
        )
    assert "services/" in prefixos, (
        "um gatilho de deploy de célula sem `services/` seria outro projeto: "
        "se isto cair, o que foi lido não é a linha `paths:` do deploy-celula"
    )


def test_paths_sem_a_linha_do_gatilho_e_ERROR_e_nao_lista_vazia(tmp_path: Path):
    """Fail-closed na borda: adivinhar a lista é pior que não saber.

    Lista vazia devolvida em silêncio faria `any(...)` responder sempre False
    — ou seja, "nenhum commit dispara deploy" para todo mundo, para sempre.
    """
    pasta = tmp_path / ".github" / "workflows"
    pasta.mkdir(parents=True)
    (pasta / "deploy-celula.yml").write_text(
        "on:\n  push:\n    branches: [main]\n", encoding="utf-8"
    )
    with pytest.raises(vacina.ErroDeMedicao):
        vacina.paths_do_deploy(tmp_path)


def _git(pasta: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=pasta, capture_output=True, text=True, check=True,
        encoding="utf-8", errors="replace",
    ).stdout.strip()


def test_a_ancestralidade_separa_o_nao_provado_do_nao_medido(tmp_path, monkeypatch):
    """Contra o Git de verdade, não contra um dublê: os TRÊS códigos de saída.

    `git merge-base --is-ancestor` responde 0 (é), 1 (provei que não) e 128
    (não consegui medir — commit ausente, clone raso: armadilhas/159). Ler o
    128 como "não" é o que transformaria "não medi" em permissão para repetir,
    e um rerun errado aqui é rollback silencioso em produção.
    """
    _git(tmp_path, "init", "--quiet", "-b", "principal")
    _git(tmp_path, "config", "user.email", "teste@exemplo")
    _git(tmp_path, "config", "user.name", "teste")
    (tmp_path / "a.txt").write_text("um", encoding="utf-8")
    _git(tmp_path, "add", "a.txt")
    _git(tmp_path, "commit", "--quiet", "-m", "primeiro")
    antigo = _git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "a.txt").write_text("dois", encoding="utf-8")
    _git(tmp_path, "commit", "--quiet", "-am", "segundo")
    novo = _git(tmp_path, "rev-parse", "HEAD")

    monkeypatch.chdir(tmp_path)
    assert vacina.e_ancestral(antigo, novo) is True
    assert vacina.e_ancestral(novo, antigo) is False
    assert vacina.e_ancestral(antigo, antigo) is True, "todo commit contém a si"
    assert vacina.e_ancestral("0" * 40, novo) is None, (
        "commit ausente é 'não medi' (None), jamais 'não é ancestral' (False)"
    )


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


def test_a_entrada_188_declara_ESTE_arquivo_como_sua_guarda():
    """A 188 nasceu `guarda: {tipo: nenhum}` porque nada a impunha (TAR-017).

    O motivo declarado era exato: *"repetir ou não depende de ancestralidade
    contra o SHA que a VPS serve, e nada guarda esse SHA hoje"*. A vacina passou
    a medir esse SHA pelo Actions, então o buraco fechou — e a entrada precisa
    dizer QUEM faz a lição valer, senão o índice segue afirmando que ninguém faz.
    """
    import indice_de_armadilhas as indice
    from _nucleo import raiz_do_repo

    raiz = raiz_do_repo()
    entradas = [e for e in indice.coletar(raiz) if e.numero == "188"]
    assert entradas, "a vacina agora cita a armadilhas/188, que precisa existir"
    guarda = entradas[0].guarda
    assert guarda.get("tipo") == "CI", f"tipo declarado: {guarda.get('tipo')}"
    assert guarda.get("dono") == "ci/tests/test_rerun_de_deploy.py", (
        "a 188 precisa declarar ESTE arquivo de teste como sua guarda "
        f"(veio: {guarda.get('dono')})"
    )
