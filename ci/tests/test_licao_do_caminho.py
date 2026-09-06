"""Guardas da lição do caminho (ci/licao_do_caminho.py) e do campo `gatilho`.

A lição é o terceiro canal do catálogo, e o único que fala ANTES: o índice
depende de alguém dar Ctrl+F, o sino casa a mensagem de erro (que só existe
depois da queda), e este gancho entrega a lição no momento em que o agente vai
gravar no caminho que morde.

Contrato do hook: exit 2 = a lição foi entregue (o stderr é o texto que o
agente lê); exit 0 = siga. FAIL-OPEN, ao contrário das muralhas: catálogo
ausente, JSON corrompido ou erro interno viram exit 0 e SILÊNCIO — ensinar é
conselho, e conselho que trava a sessão é pior que conselho nenhum.

Os testes do `gatilho` no gerador estão aqui de propósito, junto de quem os
consome: um gatilho guloso é um gancho que interrompe trabalho legítimo, e
essas duas metades precisam ser lidas na mesma tela.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ_DO_REPO = Path(__file__).resolve().parents[2]
GANCHO = RAIZ_DO_REPO / "ci" / "licao_do_caminho.py"
FIACAO = RAIZ_DO_REPO / ".claude" / "settings.json"

sys.path.insert(0, str(RAIZ_DO_REPO / "ci"))

import indice_de_armadilhas as indice  # noqa: E402


GATILHOS_DE_TESTE = {
    "versao": 1,
    "gerado_por": "teste",
    "gatilhos": [
        {
            "armadilha": "179",
            "arquivo": "armadilhas/179-numero.md",
            "titulo": "O número do registro",
            "caminho": "painel/registros/*",
            "licao": "o número se PEDE ao almoxarife, nunca se escolhe.",
        },
        {
            "armadilha": "185",
            "arquivo": "armadilhas/185-evidencia.md",
            "titulo": "A evidência sem o número do PR",
            "caminho": "painel/registros/*",
            "licao": "a evidência precisa citar o número do próprio PR.",
        },
        {
            "armadilha": "356",
            "arquivo": "armadilhas/356-fila.md",
            "titulo": "Corrente errada na fila",
            "caminho": "fila/tarefas/*",
            "licao": "arquivo de tarefa não muda depois de criado.",
        },
    ],
}


@pytest.fixture()
def casa(tmp_path: Path):
    """Um checkout mínimo com o catálogo compilado no lugar."""
    raiz = tmp_path / "repo"
    (raiz / ".git").mkdir(parents=True)
    (raiz / "armadilhas").mkdir()
    (raiz / "armadilhas" / "GATILHOS.json").write_text(
        json.dumps(GATILHOS_DE_TESTE, ensure_ascii=False), encoding="utf-8"
    )
    (raiz / "painel" / "registros").mkdir(parents=True)
    (raiz / "fila" / "tarefas").mkdir(parents=True)
    (raiz / "ci").mkdir()
    return raiz


def gravar(raiz: Path, caminho: str, sessao: str = "sessao-A", ferramenta="Write"):
    dados = {
        "hook_event_name": "PreToolUse",
        "tool_name": ferramenta,
        "tool_input": {"file_path": str(raiz / caminho), "content": "x"},
        "cwd": str(raiz),
        "session_id": sessao,
    }
    return subprocess.run(
        [sys.executable, str(GANCHO)],
        input=json.dumps(dados), capture_output=True, text=True,
        encoding="utf-8", timeout=60,
    )


# ---------- o que a lição faz ----------

def test_ensina_na_primeira_escrita_do_caminho(casa):
    r = gravar(casa, "painel/registros/20260906-001-x.js")
    assert r.returncode == 2
    assert "LIÇÃO DO CAMINHO" in r.stderr
    assert "o número se PEDE" in r.stderr


def test_entrega_as_duas_licoes_do_mesmo_caminho_de_uma_vez(casa):
    r = gravar(casa, "painel/registros/20260906-001-x.js")
    assert "o número se PEDE" in r.stderr
    assert "citar o número do próprio PR" in r.stderr


def test_cala_na_segunda_escrita_da_mesma_sessao(casa):
    assert gravar(casa, "painel/registros/a.js").returncode == 2
    segunda = gravar(casa, "painel/registros/b.js")
    assert segunda.returncode == 0 and not segunda.stderr.strip()


def test_ensina_de_novo_em_outra_sessao(casa):
    gravar(casa, "painel/registros/a.js", sessao="sessao-A")
    assert gravar(casa, "painel/registros/b.js", sessao="sessao-B").returncode == 2


def test_caminhos_diferentes_ensinam_separado(casa):
    assert gravar(casa, "painel/registros/a.js").returncode == 2
    assert gravar(casa, "fila/tarefas/TAR-999.json").returncode == 2


def test_cala_em_caminho_sem_gatilho(casa):
    r = gravar(casa, "ci/travessao.py")
    assert r.returncode == 0 and not r.stderr.strip()


def test_vale_para_edit_tambem(casa):
    alvo = casa / "painel" / "registros" / "existente.js"
    alvo.write_text("oi", encoding="utf-8")
    assert gravar(casa, "painel/registros/existente.js", ferramenta="Edit").returncode == 2


def test_ignora_ferramenta_que_nao_escreve_arquivo(casa):
    r = gravar(casa, "painel/registros/a.js", ferramenta="Bash")
    assert r.returncode == 0


# ---------- fail-open: na dúvida, cala ----------

def test_cala_quando_o_catalogo_nao_existe(tmp_path: Path):
    raiz = tmp_path / "sem-catalogo"
    (raiz / ".git").mkdir(parents=True)
    (raiz / "painel" / "registros").mkdir(parents=True)
    r = gravar(raiz, "painel/registros/a.js")
    assert r.returncode == 0 and not r.stderr.strip()


def test_cala_quando_o_catalogo_esta_corrompido(casa):
    (casa / "armadilhas" / "GATILHOS.json").write_text("{ isto não é json", encoding="utf-8")
    r = gravar(casa, "painel/registros/a.js")
    assert r.returncode == 0 and not r.stderr.strip()


def test_cala_com_json_quebrado_na_entrada():
    r = subprocess.run(
        [sys.executable, str(GANCHO)],
        input="nada disso é json", capture_output=True, text=True,
        encoding="utf-8", timeout=60,
    )
    assert r.returncode == 0


def test_cala_fora_de_qualquer_repo(casa, tmp_path: Path):
    dados = {
        "hook_event_name": "PreToolUse", "tool_name": "Write",
        "tool_input": {"file_path": str(tmp_path / "solto.txt"), "content": "x"},
        "cwd": str(tmp_path), "session_id": "s",
    }
    r = subprocess.run(
        [sys.executable, str(GANCHO)],
        input=json.dumps(dados), capture_output=True, text=True,
        encoding="utf-8", timeout=60,
    )
    assert r.returncode == 0


# ---------- o campo `gatilho` no gerador ----------

def test_gatilho_sem_licao_reprova():
    with pytest.raises(indice.ErroDeFrontmatter, match="gatilho sem licao"):
        indice.validar_gatilhos(["painel/registros/*"], "", "999-x.md")


def test_licao_sem_gatilho_reprova():
    with pytest.raises(indice.ErroDeFrontmatter, match="licao sem gatilho"):
        indice.validar_gatilhos([], "uma lição bem escrita e comprida o bastante", "999-x.md")


@pytest.mark.parametrize("guloso", ["*", "*.py", "**/*", "*/*"])
def test_gatilho_guloso_reprova(guloso):
    with pytest.raises(indice.ErroDeFrontmatter):
        indice.validar_gatilhos([guloso], "uma lição bem escrita e comprida o bastante", "999-x.md")


def test_gatilho_que_casa_caminho_inocente_reprova():
    """A prova por sabotagem: um gatilho largo tem de ficar vermelho."""
    with pytest.raises(indice.ErroDeFrontmatter, match="INOCENTE"):
        indice.validar_gatilhos(["ci/*.py"], "uma lição bem escrita e comprida o bastante", "999-x.md")


def test_gatilho_com_barra_invertida_reprova():
    with pytest.raises(indice.ErroDeFrontmatter, match="barra invertida"):
        indice.validar_gatilhos([r"painel\registros\*"], "uma lição bem escrita e comprida", "999-x.md")


def test_licao_curta_demais_reprova():
    with pytest.raises(indice.ErroDeFrontmatter, match="licao com"):
        indice.validar_gatilhos(["painel/registros/*"], "peça o número", "999-x.md")


def test_gatilho_bom_passa():
    indice.validar_gatilhos(
        ["painel/registros/*"],
        "o número se PEDE ao almoxarife, nunca se escolhe olhando a pasta.",
        "179-x.md",
    )


# ---------- o catálogo real e a fiação ----------

def test_o_catalogo_real_tem_gatilhos_e_eles_compilam():
    entradas = indice.coletar(RAIZ_DO_REPO)
    com_gatilho = [e for e in entradas if e.gatilhos]
    assert com_gatilho, "nenhuma armadilha declara gatilho: o gancho nasceria mudo"
    for entrada in com_gatilho:
        assert entrada.licao, f"{entrada.nome}: gatilho sem lição passou pela validação"


def test_fiacao_no_settings_json():
    texto = FIACAO.read_text(encoding="utf-8")
    assert "licao_do_caminho.py" in texto
