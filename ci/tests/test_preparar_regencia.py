"""O preparo exporta a revisão publicada, preserva briefs e recusa incerteza."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from _nucleo import MARCAS_DA_RAIZ
from economia_da_fabrica import compilar_brief


SCRIPT = Path(__file__).resolve().parents[1] / "preparar_regencia.py"


def git(raiz, *args):
    return subprocess.run(["git", *args], cwd=raiz, capture_output=True,
                          text=True, encoding="utf-8", check=True).stdout.strip()


def gravar(raiz, caminho, dados):
    destino = raiz / caminho
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")


def tarefa(raiz, numero, **campos):
    brief = compilar_brief(raiz, objetivo="Provar exportação integral", tipo="teste",
                          celula="ci", alvos=["ci/exemplo.py"], armadilhas=[])
    dados = dict(arquivo=f"{numero:03}-exemplo", id=f"TAR-{numero:03}",
                 titulo=f"Tarefa {numero}", toca=["ci/exemplo.py"], depende_de=[],
                 evidencia_exigida="pytest verde", despacho=brief + "Aceite completo.\n" * 1000,
                 origem="fixture", criada_em="2026-09-12")
    dados.update(campos)
    gravar(raiz, f"fila/tarefas/{numero:03}-exemplo.json", dados)
    return dados


def evento(raiz, numero, tipo, **campos):
    nome = f"20260912-120000-TAR-{numero:03}-{tipo}"
    dados = dict(arquivo=nome, tarefa=f"TAR-{numero:03}", evento=tipo,
                 quando="2026-09-12T12:00:00+00:00", quem="executor")
    dados.update(campos)
    gravar(raiz, f"fila/eventos/{nome}.json", dados)


def publicar(raiz):
    git(raiz, "add", ".")
    git(raiz, "-c", "core.hooksPath=", "commit", "-qm", "fixture")
    git(raiz, "update-ref", "refs/remotes/origin/main", "HEAD")
    return git(raiz, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    raiz = tmp_path / "repo"
    raiz.mkdir()
    git(raiz, "init", "-q")
    git(raiz, "config", "user.name", "Teste")
    git(raiz, "config", "user.email", "teste@example.org")
    for marca in MARCAS_DA_RAIZ:
        if "." in marca:
            (raiz / marca).write_text("fixture", encoding="utf-8")
        else:
            (raiz / marca).mkdir()
            (raiz / marca / ".gitkeep").write_text("", encoding="utf-8")
    tarefa(raiz, 1)
    publicar(raiz)
    return raiz


def executar(repo, saida, *ids):
    return subprocess.run([sys.executable, str(SCRIPT), *ids, "--saida", str(saida)],
                          cwd=repo, capture_output=True, text=True, encoding="utf-8")


def test_sete_despachos_integrais_com_resumo_abaixo_de_dez_por_cento(repo, tmp_path):
    tarefas = [tarefa(repo, n) for n in range(1, 8)]
    sha = publicar(repo)
    saida = tmp_path / "pacote"
    proc = executar(repo, saida, *[t["id"] for t in tarefas])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    resumo = (saida / "resumo.md").read_bytes()
    integral = sum(len(t["despacho"].encode()) for t in tarefas)
    assert len(resumo) / integral <= .1
    assert sha in proc.stdout
    assert "ao vivo: não consultadas" in proc.stdout
    assert "aptidão não aferida" in proc.stdout
    assert "Aceite completo." not in proc.stdout
    assert "alvo de bytes atingido" in proc.stdout
    fontes = (saida / "fontes.md").read_text(encoding="utf-8")
    assert "Fontes e hashes: fontes.md" in proc.stdout
    for t in tarefas:
        corpo = (saida / f"{t['id']}.md").read_bytes()
        assert corpo == t["despacho"].encode()
        assert hashlib.sha256(corpo).hexdigest() in fontes
        assert f"fila/tarefas/{t['arquivo']}.json" in fontes


def test_pasta_suja_e_head_diferente_nao_substituem_origin_main(repo, tmp_path):
    original = json.loads((repo / "fila/tarefas/001-exemplo.json").read_text(encoding="utf-8"))
    sha = git(repo, "rev-parse", "origin/main")
    tarefa(repo, 1, despacho="conteúdo local não roteado")
    git(repo, "add", ".")
    git(repo, "-c", "core.hooksPath=", "commit", "-qm", "head divergente")
    tarefa(repo, 1, titulo="sujo", despacho="sujo")
    evento(repo, 1, "cancelada", detalhe="apenas local")
    saida = tmp_path / "pacote"
    proc = executar(repo, saida, "TAR-001")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (saida / "TAR-001.md").read_text(encoding="utf-8") == original["despacho"]
    assert sha in proc.stdout and "na fila" in proc.stdout
    assert "sujo" not in proc.stdout


@pytest.mark.parametrize("ids", [[], ["TAR-1"], ["../TAR-001"], ["TAR-999"], ["TAR-001", "TAR-001"]])
def test_recusa_selecao_invalida_sem_escrever(repo, tmp_path, ids):
    saida = tmp_path / "pacote"
    proc = executar(repo, saida, *ids)
    assert proc.returncode != 0
    assert not saida.exists()


@pytest.mark.parametrize("despacho", ["", " ", "Faça tudo", "modelo_recomendado: gpt-6-astra\nesforco_recomendado: high\nteto_de_contexto: 0\n"])
def test_recusa_despacho_vazio_ou_sem_roteamento(repo, tmp_path, despacho):
    tarefa(repo, 1, despacho=despacho)
    publicar(repo)
    saida = tmp_path / "pacote"
    proc = executar(repo, saida, "TAR-001")
    assert proc.returncode == 2
    assert not saida.exists()


@pytest.mark.parametrize("tipo,campos,estado", [
    ("reivindicada", {}, "reivindicada"),
    ("bloqueada", {"detalhe": "falta decisão", "espera": "mantenedor"}, "bloqueada"),
    ("concluida", {"evidencia": "PR #1", "verificado_em": "2026-09-12"}, "concluída"),
    ("cancelada", {"detalhe": "cancelamento"}, "cancelada"),
    ("submetida", {"pr": "https://github.com/abundanciabr/sitesdoreino/pull/1",
                   "revisao": "a" * 40, "arvore": "b" * 40}, "em execução"),
])
def test_estados_vem_dos_eventos_sem_recomendar_aptidao(repo, tmp_path, tipo, campos, estado):
    evento(repo, 1, tipo, **campos)
    publicar(repo)
    proc = executar(repo, tmp_path / "pacote", "TAR-001")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"Estado: {estado}" in proc.stdout
    assert "aptidão não aferida" in proc.stdout
    if tipo == "bloqueada":
        assert "Destrava: mantenedor" in proc.stdout
    if tipo == "submetida":
        assert campos["pr"] in proc.stdout
        assert campos["revisao"] in proc.stdout
        assert campos["arvore"] in proc.stdout


def test_dependencia_fora_da_selecao_e_calculada(repo, tmp_path):
    tarefa(repo, 2, depende_de=["TAR-001"])
    publicar(repo)
    saida = tmp_path / "pacote"
    proc = executar(repo, saida, "TAR-002")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Estado: bloqueada" in proc.stdout
    assert "TAR-001 (na fila)" in proc.stdout
    assert not (saida / "TAR-001.md").exists()


@pytest.mark.parametrize("defeito", ["json", "dependencia", "git", "fila_vazia"])
def test_fonte_impossivel_de_medir_e_error(repo, tmp_path, defeito):
    if defeito == "json":
        (repo / "fila/tarefas/001-exemplo.json").write_text("{", encoding="utf-8")
    elif defeito == "dependencia":
        tarefa(repo, 1, depende_de=["TAR-999"])
    elif defeito == "fila_vazia":
        (repo / "fila/tarefas/001-exemplo.json").unlink()
    if defeito == "git":
        git(repo, "update-ref", "-d", "refs/remotes/origin/main")
    else:
        publicar(repo)
    saida = tmp_path / "pacote"
    proc = executar(repo, saida, "TAR-001")
    assert proc.returncode == 2
    assert "ERROR" in proc.stdout
    if defeito == "json":
        assert git(repo, "rev-parse", "origin/main") in proc.stdout
    assert not saida.exists()


def test_idempotencia_e_recusa_divergencia_antes_de_escrever(repo, tmp_path):
    # guarda: ci/preparar_regencia.py:153
    saida = tmp_path / "pacote"
    primeira = executar(repo, saida, "TAR-001")
    assert primeira.returncode == 0, primeira.stdout + primeira.stderr
    arquivos = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in saida.iterdir()}
    assert executar(repo, saida, "TAR-001").returncode == 0
    assert arquivos == {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in saida.iterdir()}
    (saida / "TAR-001.md").write_text("preservar", encoding="utf-8")
    (saida / "resumo.md").unlink()
    proc = executar(repo, saida, "TAR-001")
    assert proc.returncode == 2
    assert (saida / "TAR-001.md").read_text() == "preservar"
    assert not (saida / "resumo.md").exists()


@pytest.mark.parametrize("relativo", ["", "ci/pacote", "fila/tarefas/pacote", ".git/pacote"])
def test_recusa_saida_dentro_do_repositorio(repo, relativo):
    saida = repo / relativo
    proc = executar(repo, saida, "TAR-001")
    assert proc.returncode == 2
    assert not (saida / "TAR-001.md").exists()


def test_recusa_saida_no_espelho_quando_executado_em_worktree(repo, tmp_path):
    # guarda: ci/preparar_regencia.py:108
    bancada = tmp_path / "bancada"
    git(repo, "worktree", "add", "--detach", str(bancada), "HEAD")
    proc = executar(bancada, repo / "pacote", "TAR-001")
    assert proc.returncode == 2
    assert "Saída alcança um repositório" in proc.stdout
    assert not (repo / "pacote").exists()


def test_brief_curto_informa_medicao_sem_alegar_meta(repo, tmp_path):
    t = tarefa(repo, 1)
    tarefa(repo, 1, despacho=t["despacho"].split("Aceite completo.")[0])
    publicar(repo)
    proc = executar(repo, tmp_path / "pacote", "TAR-001")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "alvo de bytes não atingido" in proc.stdout
    assert "Não mede tokens, preço ou trabalho total" in proc.stdout


@pytest.mark.parametrize("roteamento", [
    "modelo_recomendado: sonnet (no Codex: gpt-5.6-sol) · esforco_recomendado: medium · teto_de_contexto: 100000",
    "Texto. modelo_recomendado: modelo-de-cima(gpt-6-astra); esforco_recomendado: high; teto_de_contexto: 180000. Ficha gerada pela economia.",
])
def test_preserva_roteamento_legado_na_mesma_linha(repo, tmp_path, roteamento):
    despacho = "Execute o mandato completo.\n" + roteamento + "\n"
    tarefa(repo, 1, despacho=despacho)
    publicar(repo)
    saida = tmp_path / "pacote"
    proc = executar(repo, saida, "TAR-001")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (saida / "TAR-001.md").read_bytes() == despacho.encode()


def test_recusa_junction_ou_symlink_nos_componentes_da_saida(repo, tmp_path):
    # guarda: ci/preparar_regencia.py:106
    destino = tmp_path / "destino"
    destino.mkdir()
    link = tmp_path / "link"
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(destino)],
                       capture_output=True, check=True)
    else:
        link.symlink_to(destino, target_is_directory=True)
    proc = executar(repo, link / "pacote", "TAR-001")
    assert proc.returncode == 2
    assert "link" in proc.stdout
    assert not (destino / "pacote").exists()


def test_recusa_despacho_extra_de_outro_lote(repo, tmp_path):
    # guarda: ci/preparar_regencia.py:149
    saida = tmp_path / "pacote"
    saida.mkdir()
    (saida / "TAR-999.md").write_text("preservar", encoding="utf-8")
    proc = executar(repo, saida, "TAR-001")
    assert proc.returncode == 2
    assert list(saida.iterdir()) == [saida / "TAR-999.md"]


def test_selecao_vazia_diz_como_corrigir_em_portugues(repo, tmp_path):
    proc = executar(repo, tmp_path / "pacote")
    assert proc.returncode == 2
    assert "Seleção inválida; informe IDs TAR-NNN" in proc.stdout


def test_stdout_tem_exatamente_os_bytes_medidos_no_resumo(repo, tmp_path):
    saida = tmp_path / "pacote"
    proc = subprocess.run([sys.executable, str(SCRIPT), "TAR-001", "--saida", str(saida)],
                          cwd=repo, capture_output=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout == (saida / "resumo.md").read_bytes()
    assert f"resumo={len(proc.stdout)};".encode() in proc.stdout


@pytest.mark.parametrize("campo,valor", [
    ("modelo_recomendado", "não use gpt-5.6-sol-inexistente"),
    ("modelo_recomendado", "gpt-5.6-sol-inexistente"),
    ("modelo_recomendado", "gpt-5.6-sol ou gpt-6-astra"),
    ("teto_de_contexto", "90000.5"),
    ("esforco_recomendado", "qualquer"),
])
def test_recusa_roteamento_sem_valor_exato(repo, tmp_path, campo, valor):
    # guarda: ci/preparar_regencia.py:132
    campos = dict(modelo_recomendado="gpt-6-astra", esforco_recomendado="high", teto_de_contexto="180000")
    campos[campo] = valor
    tarefa(repo, 1, despacho="\n".join(f"{k}: {v}" for k, v in campos.items()))
    publicar(repo)
    saida = tmp_path / "pacote"
    proc = executar(repo, saida, "TAR-001")
    assert proc.returncode == 2
    assert not saida.exists()
