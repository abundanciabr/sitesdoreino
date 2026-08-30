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


def _timeout(**kwargs) -> vacina.Fatos:
    """Um deploy de PUSH que morreu no timeout da porta 22, história completa.

    Desde a TAR-041 este ramo atravessa o MESMO portão de ancestralidade que o
    cancelado (`_a_republicacao_avanca`), porque o gatilho automático passou a
    acordar nele: sem esse portão uma vacina disparada sozinha republicaria o
    SHA de um run velho e faria voltar o que já estava no ar — a frase literal
    da `armadilhas/188`. Enquanto quem rodava a vacina era um robô minutos
    depois do próprio merge, a pergunta tinha resposta óbvia e o portão não
    fazia falta.

    O caso-base é o que aconteceu nos PRs #610/#622/#635 em 30/08/2026: o
    publicado é ancestral estrito do SHA deste run, a porta 22 responde do PC e
    o site está de pé. Ou seja: repetir só AVANÇA, e é o certo.
    """
    base = dict(
        conclusion="failure",
        event="push",
        workflow="deploy-celula",
        tem_timeout_ssh=True,
        porta22_viva=True,
        site_http=200,
        head_sha="a" * 40,
        sha_publicado="b" * 40,
        publicado_e_ancestral=True,
        head_ja_publicado=False,
        commits_de_fora=0,
        commits_de_fora_tocam_o_deploy=False,
    )
    base.update(kwargs)
    return _fatos(**base)


def test_porta_viva_com_timeout_e_blip_entao_repete():
    decisao = vacina.decidir(_timeout())
    assert decisao.acao == "repetir"
    assert decisao.codigo == 0
    assert decisao.rerun_apenas_falhados is True, (
        "run FALHADO tem job falhado: `--failed` repete só o que morreu. É o "
        "contrário do cancelado, que precisa do rerun inteiro (armadilhas/188)"
    )


def test_porta_morta_e_a_017_e_para_com_pendencia():
    decisao = vacina.decidir(_timeout(porta22_viva=False))
    assert decisao.acao == "parar"
    assert "017" in decisao.motivo
    assert decisao.pendencia, "a 017 precisa chegar ao mantenedor, não morrer no log"
    assert "NÃO está em produção" in decisao.pendencia
    assert decisao.precisa_de_alarme, (
        "a 017 é configuração e o conserto passa pelo mantenedor — este é "
        "exatamente o desfecho que TEM de acordar alguém"
    )


def test_porta_nao_medida_e_ERROR_e_nao_uma_tentativa_otimista():
    decisao = vacina.decidir(_timeout(porta22_viva=None))
    assert decisao.acao == "nada"
    assert decisao.codigo == 2, "não medir não pode virar 'pode repetir'"


def test_quando_o_medidor_esta_cego_a_mensagem_DIZ_isso(monkeypatch):
    """A testemunha da `armadilhas/209`, agora também na vacina do PC.

    Se a porta 22 fica muda E o site público — que serve 200 para o mundo —
    também não responde de onde a vacina mediu, quem está cego é o MEDIDOR. Foi
    o que o log do run 33330434813 gravou do runner do deploy, com todas as
    letras. Sem essa frase a issue diz só "não consegui medir a porta 22", e o
    mantenedor lê "a minha VPS quebrou" — a leitura errada, e a cara do
    falso-vermelho categórico que a TAR-026 já pagou uma vez.
    """
    cego = vacina.decidir(_timeout(porta22_viva=None, site_http=None))
    assert cego.codigo == 2
    assert "cego" in cego.motivo
    assert "209" in cego.motivo

    enxergando = vacina.decidir(_timeout(porta22_viva=None, site_http=200))
    assert enxergando.codigo == 2, "a decisão NÃO muda — só o que o humano lê"
    assert "cego" not in enxergando.motivo
    assert "enxerga a internet" in enxergando.motivo


# ------------------------------------------------------ regra de parada ----


@pytest.mark.parametrize("tentativas, acao", [(0, "repetir"), (1, "repetir"),
                                              (2, "repetir"), (3, "parar")])
def test_a_regra_de_parada_e_de_tres(tentativas: int, acao: str):
    decisao = vacina.decidir(_timeout(tentativas_feitas=tentativas))
    assert decisao.acao == acao


def test_ao_parar_a_pendencia_diz_que_o_site_esta_no_ar():
    """O que o mantenedor precisa saber: ninguém caiu, mas o merge não subiu."""
    decisao = vacina.decidir(_timeout(tentativas_feitas=3))
    assert "continua no ar" in decisao.pendencia
    assert "ANTIGA" in decisao.pendencia


def test_a_pendencia_alerta_quando_o_site_tambem_caiu():
    decisao = vacina.decidir(_timeout(site_http=502, tentativas_feitas=3))
    assert "ATENÇÃO" in decisao.pendencia


# ------------- o `failure` também atravessa o portão da 188 (TAR-041) ----
#
# ESTE BLOCO É A ENTREGA DA TAR-041, e cada teste aqui reprova uma decisão que
# o código de 30/08/2026 tomava ao contrário. Medido antes do conserto, com os
# MESMOS fatos que estas histórias montam:
#
#     A-divergiu   acao='repetir' codigo=0     <- publicaria um mundo mais VELHO
#     B-ja-no-ar   acao='repetir' codigo=0     <- faria voltar o que já subiu
#     C-nao-medi   acao='repetir' codigo=0     <- repetiria sem ter medido nada
#     D-manual     acao='repetir' codigo=0     <- repetiria disparo de humano
#
# Enquanto a vacina era um COMANDO rodado por um robô minutos depois do próprio
# merge, os quatro eram inofensivos: o SHA era o mais novo do mundo. Com o
# gatilho automático da TAR-041 acordando em todo `failure` da `main`, o
# primeiro deles publica um rollback sozinho, sem ninguém pedir e sem nada
# ficar vermelho.


def test_failure_com_o_publicado_divergente_PARA_em_vez_de_repetir():
    """O desfecho que dói: repetir aqui seria um rollback silencioso."""
    decisao = vacina.decidir(
        _timeout(publicado_e_ancestral=False, head_ja_publicado=False)
    )
    assert decisao.acao == "parar"
    assert decisao.codigo == 1
    assert "rollback silencioso" in decisao.motivo
    assert decisao.pendencia
    assert "RODOU e morreu na conexão" in decisao.pendencia, (
        "a pendência do cancelado dizia 'foi CANCELADO antes de começar' — "
        "sobre um run que RODOU isso manda procurar a doença errada"
    )


def test_failure_cujo_sha_um_verde_mais_novo_ja_publicou_nao_se_repete():
    decisao = vacina.decidir(
        _timeout(publicado_e_ancestral=False, head_ja_publicado=True)
    )
    assert decisao.acao == "nada"
    assert decisao.codigo == 0, "nada a fazer não é falha: o merge chegou ao ar"
    assert "JÁ está no ar" in decisao.motivo
    assert "falhou no timeout da porta 22" in decisao.motivo


@pytest.mark.parametrize(
    "campos",
    [
        {"publicado_e_ancestral": None},
        {"head_ja_publicado": None},
        {"sha_publicado": ""},
        {"head_sha": ""},
        {"workflow": ""},
    ],
)
def test_failure_sem_a_ancestralidade_medida_e_ERROR_e_nao_uma_tentativa(campos):
    """'Não medi' nunca vira 'pode repetir' — também aqui (INV-CI01)."""
    decisao = vacina.decidir(_timeout(**campos))
    assert decisao.acao == "nada"
    assert decisao.codigo == 2


def test_failure_de_disparo_MANUAL_nao_se_repete_sozinho():
    """Um humano apertou o botão e sabe o que queria publicar.

    A vacina automática cura deploy de MERGE. Repetir um `workflow_dispatch`
    sozinho republicaria o SHA daquele disparo sem que ninguém tivesse pedido —
    o mesmo cuidado que a 173 já impunha ao cancelado, agora no `failure`.
    """
    decisao = vacina.decidir(_timeout(event="workflow_dispatch"))
    assert decisao.acao == "nada"
    assert decisao.codigo == 1
    assert "workflow_dispatch" in decisao.motivo
    assert decisao.precisa_de_alarme is False, (
        "há um humano no caso; abrir issue para ele seria contar-lhe o que ele "
        "acabou de fazer"
    )


def test_o_repetir_do_failure_DIZ_que_a_republicacao_avanca():
    """Sem a frase, ninguém confere que o portão da 188 foi mesmo atravessado."""
    decisao = vacina.decidir(_timeout())
    assert "ancestral" in decisao.motivo
    assert "só AVANÇA" in decisao.motivo


# ------------------- veredito e alarme são perguntas DIFERENTES (TAR-041) ----
#
# Com o gatilho só no `cancelled`, `codigo != 0` e "acorde alguém" eram a mesma
# coisa: todo cancelado não-curado é um merge invisível fora do ar. Com o
# `failure` no gatilho deixam de ser — 27 dos 41 deploys vermelhos dos últimos
# 30 dias são defeito de código, que já está VERMELHO e já tem dono. Uma issue
# por cada um afogaria as 14 que interessam, que é o alarme que se aprende a
# ignorar (o argumento que o próprio `vacina-do-deploy.yml` escreve).


def test_falha_que_nao_e_o_timeout_NAO_acorda_ninguem():
    decisao = vacina.decidir(_fatos(tem_timeout_ssh=False))
    assert decisao.codigo == 1, "continua sendo FAIL: a vacina não curou nada"
    assert decisao.precisa_de_alarme is False, (
        "o run está vermelho na `main`, quem mergeou já foi avisado pelo "
        "próprio vermelho, e o `alarme-main` cuida da `main` vermelha"
    )


def test_a_regra_de_parada_estourada_ACORDA_alguem():
    decisao = vacina.decidir(_timeout(tentativas_feitas=3))
    assert decisao.codigo == 1
    assert decisao.precisa_de_alarme is True


def test_o_alarme_nasce_LIGADO_e_o_silencio_se_escreve_a_mao():
    """Ramo novo tem de nascer barulhento.

    O contrário — nascer mudo e alguém lembrar de ligar o alarme — é a garantia
    sem mecanismo da RETROSPECTIVA-FASE-D §2, e nunca se descobre no dia certo.
    """
    assert vacina.Decisao("parar", 1, "qualquer").precisa_de_alarme is True


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
        workflow="deploy-celula",
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


# ------------ a esteira do run decide contra o que medir (TAR-029) ----------
#
# Estas provas nasceram da TAR-029, e todas elas falam o vocabulário do código
# ANTIGO de propósito (armadilhas/195): montam `Fatos` só com campos que a
# versão anterior conhecia e põem `workflow` por `setattr`, para que o vermelho
# caia numa ASSERÇÃO — "a vacina perguntou à esteira errada" — e não num
# `TypeError` de construtor, que provaria apenas que o teste é novo.


def _sem_rede(monkeypatch, registrar: list) -> None:
    """Desliga tudo o que sai da máquina, menos a pergunta que está sob teste."""
    monkeypatch.setattr(vacina, "_rodar", lambda *a, **k: (0, ""))
    monkeypatch.setattr(vacina, "http_do_site", lambda *a, **k: 200)
    monkeypatch.setattr(vacina, "e_ancestral", lambda *a, **k: True)
    monkeypatch.setattr(vacina, "commits_que_ficam_de_fora", lambda *a, **k: (0, False))

    def _espiao(workflow=vacina.WORKFLOW_DO_DEPLOY, limite=vacina.RUNS_OLHADOS_ATRAS):
        registrar.append(workflow)
        return "b" * 40

    monkeypatch.setattr(vacina, "sha_do_ultimo_deploy_verde", _espiao)


def test_o_cancelado_do_deploy_infra_pergunta_ao_deploy_INFRA(monkeypatch):
    """O buraco que a TAR-029 achou: a vacina media a esteira errada.

    `deploy-celula` e `deploy-infra` publicam COISAS DIFERENTES — uma imagem de
    célula e o `docker-compose.yml`/`traefik` da VPS. Até 30/08/2026
    `_colher_a_ancestralidade` chamava `sha_do_ultimo_deploy_verde()` sem argumento,
    ou seja, perguntava SEMPRE ao `deploy-celula`.

    Não é hipótese. Medido em 30/08/2026 nos dois últimos verdes do dia: o do
    `deploy-celula` (00952d43) continha o do `deploy-infra` (8848f1f7) e mais 47
    commits, nenhum tocando `infra/`. Um `deploy-infra` cancelado em qualquer
    ponto dessa faixa recebia `head_ja_publicado = True` — "já está no ar" —
    sobre uma infraestrutura que nunca foi sincronizada.
    """
    perguntou: list[str] = []
    _sem_rede(monkeypatch, perguntou)
    fatos = vacina.Fatos(run="1", status="completed", conclusion="cancelled",
                         event="push", head_sha="a" * 40)
    fatos.workflow = "deploy-infra"

    vacina._colher_a_ancestralidade(fatos)

    assert perguntou == ["deploy-infra.yml"], (
        "a vacina precisa perguntar o que ESTA esteira publicou; perguntar ao "
        f"deploy-celula devolve a resposta de outra pergunta (perguntou: {perguntou})"
    )


def test_o_cancelado_do_deploy_celula_continua_perguntando_ao_deploy_CELULA(monkeypatch):
    """A correção é ESTREITA: o caso que já funcionava não pode mudar de mira.

    Sozinha, a prova de cima passaria também se alguém tivesse feito a vacina
    perguntar sempre ao `deploy-infra` — trocar um erro pelo simétrico.
    """
    perguntou: list[str] = []
    _sem_rede(monkeypatch, perguntou)
    fatos = vacina.Fatos(run="1", status="completed", conclusion="cancelled",
                         event="push", head_sha="a" * 40)
    fatos.workflow = "deploy-celula"

    vacina._colher_a_ancestralidade(fatos)

    assert perguntou == ["deploy-celula.yml"]


def test_sem_saber_a_esteira_o_cancelado_e_ERROR_e_nao_um_palpite():
    """Fail-closed na borda: 'não sei contra o que comparar' não vira 'repetir'.

    Antes da TAR-029 esta mesma história devolvia `repetir`/0 — a vacina
    republicava um SHA sem ter medido a publicação da esteira certa. A história
    é montada aqui SEM a palavra `workflow` (e não com ela vazia) porque é
    assim que o código antigo a enxergava: o vermelho tem de cair nesta
    asserção, não no construtor (armadilhas/195).
    """
    decisao = vacina.decidir(_fatos(
        conclusion="cancelled", event="push",
        head_sha="a" * 40, sha_publicado="b" * 40,
        publicado_e_ancestral=True, head_ja_publicado=False,
        commits_de_fora=0, commits_de_fora_tocam_o_deploy=False, site_http=200,
    ))
    assert decisao.codigo == 2, (
        "esteira desconhecida é ERROR; 'não medi' nunca vira 'pode repetir'"
    )
    assert decisao.acao != "repetir"


def test_o_attempt_do_run_e_a_conta_que_sobrevive_ao_processo(monkeypatch):
    """A regra de parada precisa valer ENTRE execuções (TAR-029).

    Com um gatilho automático, cada rerun cancelado acorda um processo NOVO com
    o contador de memória em zero — vacina → rerun → cancelado → vacina, sem
    fim. `attempt` é a única conta que o GitHub guarda; medido no dia, o run
    33325108776 estava em `attempt: 4`.
    """
    monkeypatch.setattr(vacina, "_colher_a_ancestralidade", lambda fatos: None)
    monkeypatch.setattr(
        vacina, "dados_do_run",
        lambda run: {"status": "completed", "conclusion": "cancelled",
                     "event": "push", "headSha": "a" * 40,
                     "workflowName": "deploy-celula", "attempt": 4},
    )

    fatos = vacina.colher("1", "host.invalido", tentativas=0)

    assert fatos.tentativas_feitas == 3, (
        "quatro tentativas de run são três repetições já feitas; ler zero aqui "
        "é o que faria a vacina repetir para sempre"
    )
    assert vacina.decidir(fatos).acao != "repetir", (
        "estourada a regra de parada, a vacina PARA — a quarta tentativa não é "
        "diagnóstico, é teimosia (armadilhas/127)"
    )


def test_o_laco_de_memoria_ainda_conta_quando_o_attempt_nao_ajuda():
    """Piso, não substituição: o maior dos dois é o que a regra enxerga."""
    assert vacina.tentativas_ja_feitas({"attempt": 1}, 2) == 2
    assert vacina.tentativas_ja_feitas({"attempt": 4}, 0) == 3
    assert vacina.tentativas_ja_feitas({}, 1) == 1, "sem attempt, vale a memória"
    assert vacina.tentativas_ja_feitas({"attempt": "nao-numero"}, 1) == 1


def test_os_paths_do_deploy_infra_sao_LIDOS_apesar_da_forma_em_bloco():
    """As duas formas de `paths:` são YAML válido, e as duas existem aqui.

    O `deploy-celula` escreve em linha (`paths: [a, b]`) e o `deploy-infra` em
    bloco (`- 'infra/...'`). Um leitor que só soubesse a primeira devolveria
    ERROR sobre o `deploy-infra` — e o recado da 188 ("nenhum deploy novo vai
    nascer") viraria "não consegui contar" justamente no caso novo.
    """
    from _nucleo import raiz_do_repo

    raiz = raiz_do_repo()
    prefixos = vacina.paths_do_deploy(
        raiz, raiz / ".github" / "workflows" / "deploy-infra.yml"
    )
    assert "infra/traefik/" in prefixos, f"veio: {prefixos}"
    assert "infra/docker-compose.yml" in prefixos, (
        "o gatilho do deploy-infra tem ARQUIVOS, não só pastas — cortá-los "
        f"deixaria a conta cega (veio: {prefixos})"
    )
    for prefixo in prefixos:
        assert (raiz / prefixo).exists(), (
            f"'{prefixo}' saiu do gatilho mas não existe neste repositório — a "
            "leitura está pegando outra coisa"
        )


def test_paths_em_bloco_nao_engole_a_chave_seguinte(tmp_path: Path):
    """Ler lixo é pior que não achar: lixo decide sem levantar suspeita."""
    pasta = tmp_path / ".github" / "workflows"
    pasta.mkdir(parents=True)
    (pasta / "deploy-celula.yml").write_text(
        "on:\n  push:\n    paths:\n      - 'infra/traefik/**'\n"
        "permissions:\n  contents: read\n",
        encoding="utf-8",
    )
    assert vacina.paths_do_deploy(tmp_path) == ("infra/traefik/",)


def test_o_arquivo_do_workflow_e_descoberto_pelo_nome_de_dentro():
    """Casar por convenção de nome de arquivo quebraria calado num rename."""
    from _nucleo import raiz_do_repo

    raiz = raiz_do_repo()
    assert vacina.arquivo_do_workflow("deploy-infra", raiz).name == "deploy-infra.yml"
    assert vacina.arquivo_do_workflow("deploy-celula", raiz).name == "deploy-celula.yml"
    with pytest.raises(vacina.ErroDeMedicao):
        vacina.arquivo_do_workflow("workflow-que-nao-existe", raiz)


# ------------- o FIO entre a tabela e o workflow (TAR-041) ------------------
#
# O controle de ruído inteiro pende desta função: se ela escrever `alarmar`
# errado, a tabela decide uma coisa e a issue nasce por outra — e ninguém
# descobre, porque os dois lados continuam parecendo certos separadamente.


def _saida_escrita(decisao, tmp_path, monkeypatch) -> dict:
    arquivo = tmp_path / "saida.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(arquivo))
    vacina.escrever_saida_do_passo(decisao)
    linhas = arquivo.read_text(encoding="utf-8").splitlines()
    return dict(linha.split("=", 1) for linha in linhas if "=" in linha)


def test_o_defeito_de_codigo_sai_FAIL_mas_alarmar_FALSE(tmp_path, monkeypatch):
    """As duas perguntas na mesma saída, e elas discordam de propósito."""
    decisao = vacina.decidir(_fatos(tem_timeout_ssh=False))
    saida = _saida_escrita(decisao, tmp_path, monkeypatch)
    assert saida["codigo"] == "1", "o veredito continua sendo FAIL: nada foi curado"
    assert saida["alarmar"] == "false", (
        "27 dos 41 vermelhos de 30 dias caem aqui; uma issue por cada um "
        "afogaria as 14 que interessam"
    )
    assert saida["acao"] == "parar"


def test_a_017_sai_FAIL_e_alarmar_TRUE(tmp_path, monkeypatch):
    decisao = vacina.decidir(_timeout(porta22_viva=False))
    saida = _saida_escrita(decisao, tmp_path, monkeypatch)
    assert saida["codigo"] == "1"
    assert saida["alarmar"] == "true", "configuração da VPS é território do dono"


def test_o_sucesso_nunca_alarma(tmp_path, monkeypatch):
    saida = _saida_escrita(
        vacina.decidir(_fatos(conclusion="success")), tmp_path, monkeypatch
    )
    assert saida["codigo"] == "0" and saida["alarmar"] == "false"


def test_o_ERROR_sempre_alarma_mesmo_com_precisa_de_alarme_no_padrao(
    tmp_path, monkeypatch
):
    """'Não medi' é o desfecho em que ninguém mais vai olhar (INV-CI01)."""
    saida = _saida_escrita(
        vacina.decidir(_timeout(porta22_viva=None)), tmp_path, monkeypatch
    )
    assert saida["codigo"] == "2" and saida["alarmar"] == "true"


def test_fora_do_actions_a_funcao_nao_estoura(monkeypatch):
    """A vacina precisa continuar rodando na mão, do PC, sem GITHUB_OUTPUT."""
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    vacina.escrever_saida_do_passo(vacina.Decisao("nada", 0, "x"))
