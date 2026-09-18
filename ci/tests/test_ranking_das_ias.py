"""O ranking mede o que está em `main`, e não o que alguém diz ter feito.

Cada teste monta um repositório FALSO em tmp_path, com commits assinados de
propósito, e confere o número que sai. Medir o repositório real aqui daria um
teste que muda de resultado a cada merge — verde por acaso hoje, vermelho
amanhã, e sem dizer o que quebrou.

As quatro coisas que este arquivo existe para impedir:

1. **Trabalho sem assinatura ser repartido por palpite.** Um ranking que
   adivinhasse dono premiaria a IA errada, e ninguém teria como conferir.
2. **Editar template virar "página publicada".** Se mexer num rodapé valesse o
   mesmo que publicar uma tela, a métrica inteira vira ruído em uma semana.
3. **Base ausente virar "então mede a pasta local".** Medir o clone local em
   vez de `origin/main` já reprovou duas fichas do conselho da Fase 4.
4. **Uma IA sem entrega sumir do ranking.** Zero é resposta; ausência é omissão.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

from ranking_das_ias import SemBase, escrever, medir  # noqa: E402
import ranking_das_ias as gerador  # noqa: E402

ASSINATURAS = {
    "claude": "Claude Opus 5 <noreply@anthropic.com>",
    "codex": "Codex <noreply@openai.com>",
    "antigravity": "Antigravity <noreply@google.com>",
}


def _git(pasta: Path, *argumentos: str) -> str:
    return subprocess.run(
        ("git", *argumentos),
        cwd=pasta,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    pasta = tmp_path / "repo"
    (pasta / "painel").mkdir(parents=True)
    _git(pasta, "init", "--initial-branch=principal")
    _git(pasta, "config", "user.email", "mantenedor@exemplo.com")
    _git(pasta, "config", "user.name", "Mantenedor")
    return pasta


def _commit(
    repo: Path, assunto: str, arquivos: dict[str, str], assina: str | None = None
) -> None:
    for caminho, conteudo in arquivos.items():
        alvo = repo / caminho
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(conteudo, encoding="utf-8")
    _git(repo, "add", "-A")
    mensagem = assunto
    if assina:
        mensagem += f"\n\nCo-authored-by: {ASSINATURAS[assina]}"
    _git(repo, "commit", "-m", mensagem)


PAGINA = "services/funil/templates/funil/nova.html"
OUTRA = "services/admin/apps/core/templates/admin/outra.html"


def test_pagina_publicada_e_template_que_passou_a_existir(repo: Path):
    # guarda: ci/ranking_das_ias.py:236
    _commit(repo, "feat: a página", {PAGINA: "<p>um</p>"}, assina="codex")
    _commit(repo, "feat: mexer na página", {PAGINA: "<p>dois</p>"}, assina="codex")

    retrato = medir(repo, "principal")
    codex = next(i for i in retrato["ias"] if i["chave"] == "codex")

    assert codex["paginas"] == 1, "editar template não publica página de novo"
    assert codex["entregas"] == 2, "os dois commits continuam sendo entregas"


def test_arquivo_que_nao_e_template_nao_conta_como_pagina(repo: Path):
    _commit(
        repo,
        "feat: código e documento",
        {"services/funil/views.py": "x = 1", "docs/leia.md": "texto"},
        assina="codex",
    )

    codex = next(i for i in medir(repo, "principal")["ias"] if i["chave"] == "codex")
    assert codex["paginas"] == 0
    assert codex["entregas"] == 1


def test_commit_sem_assinatura_nao_e_repartido(repo: Path):
    _commit(repo, "feat: sem dono", {PAGINA: "<p>um</p>"})

    retrato = medir(repo, "principal")

    assert all(
        ia["entregas"] == 0 for ia in retrato["ias"]
    ), "nenhuma das três pode receber trabalho que não assinou"
    assert retrato["sem_assinatura"]["entregas"] == 1
    assert retrato["sem_assinatura"]["paginas"] == 1


def test_as_tres_aparecem_mesmo_zeradas(repo: Path):
    _commit(repo, "feat: só a Claude", {PAGINA: "<p>um</p>"}, assina="claude")

    retrato = medir(repo, "principal")
    nomes = [ia["nome"] for ia in retrato["ias"]]

    assert nomes == ["Claude Code", "Codex", "Antigravity"]
    parada = next(i for i in retrato["ias"] if i["chave"] == "antigravity")
    assert parada["entregas"] == 0
    assert parada["ultima_entrega"] is None, "sem entrega não há data para inventar"


def test_modelo_diferente_da_mesma_ia_soma_na_mesma_linha(repo: Path):
    """`main` já tem Opus 5, Fable 5.1, Sonnet 5 e Opus 4.8 assinando o mesmo
    trabalho. Uma linha por modelo partiria a Claude Code em quatro rankings."""
    _commit(repo, "feat: um", {PAGINA: "<p>um</p>"}, assina="claude")
    _git(
        repo,
        "commit",
        "--allow-empty",
        "-m",
        "feat: dois\n\nCo-authored-by: Claude Fable 5.1 <noreply@anthropic.com>",
    )

    claude = next(
        i for i in medir(repo, "principal")["ias"] if i["chave"] == "claude-code"
    )
    assert claude["entregas"] == 2


def test_retrabalho_conta_conserto_e_nao_conta_novidade(repo: Path):
    _commit(repo, "feat: a página", {PAGINA: "<p>um</p>"}, assina="codex")
    _commit(repo, "fix: a página quebrada", {PAGINA: "<p>dois</p>"}, assina="codex")
    _commit(repo, "revert: melhor não", {OUTRA: "<p>três</p>"}, assina="codex")

    codex = next(i for i in medir(repo, "principal")["ias"] if i["chave"] == "codex")
    assert codex["retrabalho"] == 2
    assert codex["entregas"] == 3


def test_linhas_somam_o_que_entrou_e_o_que_saiu(repo: Path):
    _commit(repo, "feat: três linhas", {PAGINA: "a\nb\nc\n"}, assina="codex")
    _commit(repo, "feat: sobrou uma", {PAGINA: "a\n"}, assina="codex")

    codex = next(i for i in medir(repo, "principal")["ias"] if i["chave"] == "codex")
    assert codex["linhas"] == 5, "3 somadas no primeiro; 2 apagadas no segundo"


def test_base_ausente_nao_vira_a_pasta_local(repo: Path):
    _commit(repo, "feat: a página", {PAGINA: "<p>um</p>"}, assina="codex")

    with pytest.raises(SemBase) as erro:
        medir(repo, "origin/inexistente")

    assert "git fetch origin" in str(erro.value), "o erro precisa dizer o que fazer"


def test_o_arquivo_publicado_e_o_que_a_tela_espera(repo: Path):
    _commit(repo, "feat: a página", {PAGINA: "<p>um</p>"}, assina="codex")

    caminho = escrever(repo, medir(repo, "principal"))
    dados = json.loads(caminho.read_text(encoding="utf-8"))

    assert caminho == repo / "painel" / "ranking-ias.json"
    assert dados["versao"] == 1, "a tela recusa retrato de versão que não conhece"
    assert dados["base"] == "principal"
    assert len(dados["commit_da_base"]) == 40
    for ia in dados["ias"]:
        assert set(ia) == {
            "chave",
            "nome",
            "papel",
            "entregas",
            "paginas",
            "linhas",
            "retrabalho",
            "dias_ativos",
            "ultima_entrega",
        }


def test_as_duas_leituras_usam_a_revisao_conferida(repo: Path, monkeypatch):
    _commit(repo, "feat: a página", {PAGINA: "<p>um</p>"}, assina="codex")
    revisao = _git(repo, "rev-parse", "principal").strip()
    leituras = []
    ler_git = gerador._git

    def consultar(raiz, *argumentos):
        if argumentos[0] == "log":
            leituras.append(argumentos[1])
        return ler_git(raiz, *argumentos)

    monkeypatch.setattr(gerador, "_git", consultar)
    assert medir(repo, "principal")["commit_da_base"] == revisao
    assert leituras == [revisao, revisao]


@pytest.mark.parametrize("assinaturas", [("claude", "codex"), ("codex", "claude")])
def test_assinatura_multipla_nao_credita_a_primeira_ia(repo: Path, assinaturas):
    _commit(repo, "feat: autoria compartilhada", {PAGINA: "<p>um</p>"})
    trailers = "\n".join(f"Co-authored-by: {ASSINATURAS[ia]}" for ia in assinaturas)
    _git(repo, "commit", "--amend", "-m", f"feat: autoria compartilhada\n\n{trailers}")

    retrato = medir(repo, "principal")
    assert all(ia["entregas"] == 0 for ia in retrato["ias"])
    assert retrato["sem_assinatura"]["entregas"] == 1
    assert retrato["sem_assinatura"]["paginas"] == 1
