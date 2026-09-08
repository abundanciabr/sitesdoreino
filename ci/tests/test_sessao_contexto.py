from pathlib import Path

import pytest
import sessao
from indice_de_armadilhas import coletar, montar_gatilhos, montar_sinais


@pytest.fixture
def memoria(tmp_path):
    raiz = Path(__file__).resolve().parents[2]
    entradas = coletar(raiz)
    (tmp_path / "armadilhas").mkdir()
    (tmp_path / "armadilhas/GATILHOS.json").write_text(
        montar_gatilhos(entradas), encoding="utf-8"
    )
    (tmp_path / "armadilhas/SINAIS.json").write_text(
        montar_sinais(entradas), encoding="utf-8"
    )
    return tmp_path


def test_contexto_real_por_caminho_sintoma_e_multiplos_alvos(memoria):
    texto = sessao.contexto_direcionado(
        memoria,
        objetivo="Retomar bancada",
        caminhos=["painel/registros/20260908-001-teste.js", "ci/sessao.py"],
        sintoma="git status limpo sem ninguem ter medido",
        aceite=["Reexecucao segura"],
    )
    assert "179" in texto
    assert "373" in texto
    assert "Reexecucao segura" in texto
    assert "AGENTS.md" in texto and "CONSTITUICAO.md" in texto
    assert "RETROSPECTIVA-FASE-D.md" in texto
    assert "Não dispensa" in texto
    assert "painel/registros/20260908-001-teste.js" in texto


def test_contexto_vazio_e_truncado_sao_explicitos(memoria):
    vazio = sessao.contexto_direcionado(
        memoria, objetivo="Teste", caminhos=["inexistente.xyz"]
    )
    assert "Nenhuma lição" in vazio
    cheio = sessao.contexto_direcionado(
        memoria, objetivo="Teste", caminhos=["painel/registros/teste.js"], limite=1
    )
    assert "Truncado" in cheio
    assert "--limite-contexto" in cheio
    assert "INDICE.md" in cheio


def test_contexto_ausente_nao_finge_busca_vazia(tmp_path):
    texto = sessao.contexto_direcionado(
        tmp_path, objetivo="Teste", caminhos=["ci/sessao.py"]
    )
    assert "Limitação" in texto
    assert "indice_de_armadilhas.py" in texto


def test_contexto_preserva_licao_transversal(memoria):
    import json

    arquivo = memoria / "armadilhas/GATILHOS.json"
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    real = next(item for item in dados["gatilhos"] if item["armadilha"] == "179")
    dados["gatilhos"].append({**real, "caminho": "*", "armadilha": "transversal-real"})
    arquivo.write_text(json.dumps(dados), encoding="utf-8")
    texto = sessao.contexto_direcionado(
        memoria, objetivo="Teste", caminhos=["painel/registros/teste.js"], limite=100
    )
    assert "transversal-real" in texto and "179" in texto


def test_regra_transversal_real_para_template_de_qualquer_celula(memoria):
    texto = sessao.contexto_direcionado(
        memoria,
        objetivo="Corrigir mensagem",
        caminhos=["services/identidade/apps/contas/templates/contas/entrar.html"],
    )
    assert "394" in texto
    assert "constituicoes/AGENTS.identidade.md" in texto
    assert "services/identidade/LICOES.md" in texto


def test_contexto_cli_nao_prepara_nem_consulta_boletim(monkeypatch, capsys):
    import boletim

    raiz = Path(__file__).resolve().parents[2]
    monkeypatch.setattr(boletim, "coletar", lambda *a: pytest.fail("consultou boletim"))
    monkeypatch.setattr(
        sessao.Sessao, "rodar", lambda *a: pytest.fail("preparou bancada")
    )
    monkeypatch.setattr(sessao, "medir_fase", lambda *a, **k: None)
    assert (
        sessao.main(
            [
                "--raiz",
                str(raiz),
                "--celula",
                "ci",
                "--tarefa",
                "contexto",
                "--sem-container",
                "--contexto",
                "--caminho",
                "ci/sessao.py",
                "--frase",
                "Revisar abertura",
                "--aceite",
                "Retomar sem duplicar",
            ]
        )
        == 0
    )
    saida = capsys.readouterr().out
    assert "Revisar abertura" in saida and "Retomar sem duplicar" in saida
    assert "BANCADA PRONTA" not in saida


def test_metrica_conta_apenas_resposta_emitida(monkeypatch, capsys):
    raiz = Path(__file__).resolve().parents[2]
    medidas = []
    monkeypatch.setattr(sessao, "medir_fase", lambda *a, **k: medidas.append(k))
    assert (
        sessao.main(
            [
                "--raiz",
                str(raiz),
                "--celula",
                "ci",
                "--tarefa",
                "contexto",
                "--sem-container",
                "--contexto",
            ]
        )
        == 0
    )
    assert medidas[0]["contexto_bytes"] == len(capsys.readouterr().out.encode("utf-8"))


@pytest.mark.parametrize("alvo", ["ci/", "ci", "ci/tests/", "ci/tests/novo.py"])
def test_instrucoes_do_diretorio_alvo_e_dos_ancestrais(memoria, alvo):
    (memoria / "ci/tests").mkdir(parents=True)
    (memoria / "ci/AGENTS.md").write_text("Lei da CI", encoding="utf-8")
    (memoria / "ci/tests/AGENTS.md").write_text("Lei dos testes", encoding="utf-8")
    texto = sessao.contexto_direcionado(
        memoria, objetivo="Conferir leis", caminhos=[alvo]
    )
    leituras = next(
        linha
        for linha in texto.splitlines()
        if linha.startswith("Leituras obrigatórias:")
    )
    assert "ci/AGENTS.md" in leituras
    if alvo.startswith("ci/tests"):
        assert "ci/tests/AGENTS.md" in leituras
    assert leituras.count("ci/AGENTS.md") == 1


@pytest.mark.parametrize("explicito", [False, True])
def test_contexto_da_fila_recupera_toca_cria_e_respeita_override(
    memoria, monkeypatch, capsys, explicito
):
    import fila

    tarefa = {
        "arquivo": "277-contexto",
        "titulo": "Retomar abertura",
        "evidencia_exigida": "Reexecução segura",
        "toca": ["ci/sessao.py"],
        "cria": ["painel/registros/*"],
        "move": ["cartao-de-fabrica"],
    }
    monkeypatch.setattr(sessao, "raiz_declarada", lambda p: memoria)
    monkeypatch.setattr(sessao, "celulas_declaradas", lambda p: ["identidade"])
    monkeypatch.setattr(sessao, "medir_fase", lambda *a, **k: None)
    monkeypatch.setattr(fila, "carregar_tarefas", lambda *a: {"TAR-277": tarefa})
    argumentos = [
        "--raiz",
        str(memoria),
        "--celula",
        "ci",
        "--tarefa",
        "contexto",
        "--sem-container",
        "--contexto",
        "--tar",
        "277",
        "--sintoma",
        "git status limpo sem ninguem ter medido",
    ]
    if explicito:
        argumentos += ["--caminho", "ci/override.py"]
    assert sessao.main(argumentos) == 0
    saida = capsys.readouterr().out
    assert "Lição 373:" in saida
    if explicito:
        assert "Caminhos: ci/override.py" in saida
        assert "Lição 179:" not in saida
    else:
        assert "Caminhos: ci/sessao.py, painel/registros/*" in saida
        assert "Lição 179:" in saida
    assert "cartao-de-fabrica" not in saida


def test_areas_e_celulas_da_fila_viram_caminhos_sem_alterar_glob():
    tarefa = {
        "toca": ["ci", "identidade", "AGENTS.md"],
        "cria": ["painel/registros/*", "ci"],
        "move": ["cartao-de-fabrica"],
    }
    assert sessao.caminhos_da_tarefa(tarefa, ["identidade"]) == [
        "ci/",
        "services/identidade/",
        "AGENTS.md",
        "painel/registros/*",
    ]
