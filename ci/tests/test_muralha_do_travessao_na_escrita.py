"""Guardas da muralha do travessão na escrita (ci/muralha_do_travessao_na_escrita.py).

A muralha recusa, no PreToolUse de Write/Edit, a gravação que AUMENTARIA os
travessões de um arquivo de texto público — o mesmo veredito do portão do PR
(ci/travessao.py), antecipado para o momento da escrita.

Contrato do hook: exit 0 = permite; exit 2 = recusa com o motivo (e as quatro
trocas) no stderr. Arquivo candidato a público cuja medição falhou TAMBÉM é
exit 2 — fail-closed, INV-CI01.

O teste mais importante daqui é o de equivalência: `pertence_a_superficie` é o
espelho por-arquivo de `superficie`, e as duas réguas são comparadas sobre TODO
arquivo do repositório real. Quem mudar uma sem a outra reprova ali, com o
caminho divergente na tela.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ_DO_REPO = Path(__file__).resolve().parents[2]
MURALHA = RAIZ_DO_REPO / "ci" / "muralha_do_travessao_na_escrita.py"
FIACAO = RAIZ_DO_REPO / ".claude" / "settings.json"


def decidir(tool_name: str, tool_input: dict, cwd: Path):
    dados = {
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": tool_input,
        "cwd": str(cwd),
    }
    return subprocess.run(
        [sys.executable, str(MURALHA)],
        input=json.dumps(dados), capture_output=True, text=True,
        encoding="utf-8", timeout=60,
    )


@pytest.fixture()
def reino(tmp_path: Path):
    """Um checkout mínimo com superfície pública de verdade: templates de uma
    célula, a lista do bastidor e um .git para a muralha achar a raiz."""
    raiz = tmp_path / "repo"
    (raiz / ".git").mkdir(parents=True)
    (raiz / "ci").mkdir()
    (raiz / "ci" / "texto-publico-bastidor.txt").write_text(
        "services/*/templates/admin/* :: telas de administracao que so o mantenedor abre\n",
        encoding="utf-8",
    )
    templates = raiz / "services" / "escola" / "templates" / "escola"
    templates.mkdir(parents=True)
    return raiz, templates


# ---------- Write: o arquivo novo ----------

def test_recusa_template_novo_com_travessao(reino):
    raiz, templates = reino
    r = decidir(
        "Write",
        {
            "file_path": str(templates / "aula.html"),
            "content": "<p>Ele só queria uma coisa — paz.</p>",
        },
        raiz,
    )
    assert r.returncode == 2
    assert "MURALHA DO TRAVESSÃO" in r.stderr
    assert "VÍRGULA" in r.stderr  # a lição das quatro trocas viaja na recusa


def test_permite_template_novo_limpo(reino):
    raiz, templates = reino
    r = decidir(
        "Write",
        {
            "file_path": str(templates / "aula.html"),
            "content": "<p>Ele só queria uma coisa: paz.</p>",
        },
        raiz,
    )
    assert r.returncode == 0


def test_permite_travessao_em_comentario_html(reino):
    raiz, templates = reino
    r = decidir(
        "Write",
        {
            "file_path": str(templates / "aula.html"),
            "content": "<!-- nota interna — ninguém lê --><p>Bem-vindo.</p>",
        },
        raiz,
    )
    assert r.returncode == 0


def test_permite_travessao_fora_da_superficie(reino):
    raiz, _ = reino
    r = decidir(
        "Write",
        {
            "file_path": str(raiz / "docs" / "nota.md"),
            "content": "Nota interna — com risca, e pode.",
        },
        raiz,
    )
    assert r.returncode == 0


def test_permite_travessao_no_bastidor(reino):
    raiz, _ = reino
    alvo = raiz / "services" / "escola" / "templates" / "admin" / "painel.html"
    r = decidir(
        "Write",
        {"file_path": str(alvo), "content": "<p>Painel — só o dono vê.</p>"},
        raiz,
    )
    assert r.returncode == 0


# ---------- Edit: o arquivo que já existe ----------

def test_recusa_edit_que_adiciona_travessao(reino):
    raiz, templates = reino
    alvo = templates / "aula.html"
    alvo.write_text("<p>Oi, turma.</p>", encoding="utf-8")
    r = decidir(
        "Edit",
        {
            "file_path": str(alvo),
            "old_string": "Oi, turma.",
            "new_string": "Oi — turma.",
        },
        raiz,
    )
    assert r.returncode == 2


def test_permite_edit_que_remove_travessao(reino):
    raiz, templates = reino
    alvo = templates / "aula.html"
    alvo.write_text("<p>Oi — turma.</p><p>Até — logo.</p>", encoding="utf-8")
    r = decidir(
        "Edit",
        {
            "file_path": str(alvo),
            "old_string": "Oi — turma.",
            "new_string": "Oi, turma.",
        },
        raiz,
    )
    assert r.returncode == 0


def test_permite_edit_neutro_em_arquivo_com_divida(reino):
    raiz, templates = reino
    alvo = templates / "aula.html"
    alvo.write_text("<p>Oi — turma.</p><p>Boa aula.</p>", encoding="utf-8")
    r = decidir(
        "Edit",
        {
            "file_path": str(alvo),
            "old_string": "Boa aula.",
            "new_string": "Excelente aula.",
        },
        raiz,
    )
    assert r.returncode == 0


def test_permite_edit_que_vai_falhar_sozinho(reino):
    raiz, templates = reino
    alvo = templates / "aula.html"
    alvo.write_text("<p>Oi.</p>", encoding="utf-8")
    r = decidir(
        "Edit",
        {
            "file_path": str(alvo),
            "old_string": "isto não está no arquivo",
            "new_string": "tanto — faz",
        },
        raiz,
    )
    assert r.returncode == 0


# ---------- O texto de tela que mora em código ----------

def test_recusa_rotulo_de_choices_com_travessao(reino):
    raiz, _ = reino
    conteudo = (
        "class Status(TextChoices):\n"
        '    EM_ANALISE = "em_analise", "Em análise — aguarde"\n'
    )
    r = decidir(
        "Write",
        {
            "file_path": str(raiz / "services" / "escola" / "models.py"),
            "content": conteudo,
        },
        raiz,
    )
    assert r.returncode == 2


def test_permite_travessao_em_docstring_de_arquivo_com_choices(reino):
    raiz, _ = reino
    conteudo = (
        '"""Modelos da escola — docstring é de programador, não de aluno."""\n'
        "class Status(TextChoices):\n"
        '    EM_ANALISE = "em_analise", "Em análise"\n'
    )
    r = decidir(
        "Write",
        {
            "file_path": str(raiz / "services" / "escola" / "models.py"),
            "content": conteudo,
        },
        raiz,
    )
    assert r.returncode == 0


# ---------- fail-closed e fiação ----------

def test_recusa_candidato_quando_o_instrumento_falta(tmp_path: Path):
    raiz = tmp_path / "repo-sem-bastidor"
    (raiz / ".git").mkdir(parents=True)
    alvo = raiz / "services" / "escola" / "templates" / "escola" / "aula.html"
    r = decidir(
        "Write",
        {"file_path": str(alvo), "content": "<p>Oi — turma.</p>"},
        raiz,
    )
    assert r.returncode == 2
    assert "não consegui medir" in r.stderr.lower() or "medição falhou" in r.stderr


def test_recusa_json_quebrado():
    r = subprocess.run(
        [sys.executable, str(MURALHA)],
        input="isto não é json", capture_output=True, text=True,
        encoding="utf-8", timeout=60,
    )
    assert r.returncode == 2


def test_fiacao_no_settings_json():
    texto = FIACAO.read_text(encoding="utf-8")
    assert "muralha_do_travessao_na_escrita.py" in texto
    assert '"Edit|Write"' in texto


# ---------- a equivalência das duas réguas ----------

def test_pertence_a_superficie_bate_com_superficie_no_repo_real():
    sys.path.insert(0, str(RAIZ_DO_REPO / "ci"))
    import travessao

    oficiais = set(travessao.superficie(RAIZ_DO_REPO))
    sufixos = {".html", ".htm", ".txt", ".md", ".yaml", ".yml", ".py"}
    divergentes = []
    for base in ("documentos", "services"):
        pasta = RAIZ_DO_REPO / base
        if not pasta.is_dir():
            continue
        for arquivo in pasta.rglob("*"):
            if not arquivo.is_file() or arquivo.suffix.lower() not in sufixos:
                continue
            try:
                texto = arquivo.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                texto = ""
            relativo = arquivo.relative_to(RAIZ_DO_REPO)
            if travessao.pertence_a_superficie(
                RAIZ_DO_REPO, relativo, texto
            ) != (arquivo in oficiais):
                divergentes.append(relativo.as_posix())
    assert not divergentes, (
        "as duas réguas divergiram nestes caminhos:\n  " + "\n  ".join(divergentes)
    )
