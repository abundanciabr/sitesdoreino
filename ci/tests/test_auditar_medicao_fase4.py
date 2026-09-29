"""Provas do recálculo independente da amostra real da Fase 4."""

import ast
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import auditar_medicao_fase4 as auditor  # noqa: E402


RAIZ = Path(__file__).resolve().parents[2]
METRICAS = (
    "chamadas_modelo",
    "chamadas_ferramenta",
    "runner_minutos",
    "retentativas",
    "correcoes_revisao",
    "reaberturas",
    "minutos_adocao",
    "minutos_manutencao",
    "defeitos_escapados",
    "violacoes_seguranca",
    "contexto_bytes",
)


def evento_legado(numero, *, tarefa=None, nulos=11):
    metricas = {
        campo: (None if indice < nulos else indice)
        for indice, campo in enumerate(METRICAS)
    }
    evento = {
        "evento": "tarefa_medida",
        "tarefa": tarefa or f"TAR-{numero}",
        "tentativa": f"tentativa-{numero}",
        "branch": f"agent/ci/tarefa-{numero}",
        "commit": f"{numero:x}".rjust(40, "a")[-40:],
        "pr": numero,
        "piloto": "fase1",
        "condicao": "antes",
        "par_id": None,
        "tipo": "correcao",
        "complexidade": "media",
        "natureza": "codigo",
        "componentes": "ci",
        "fronteiras_integracao": "uma",
        "migracao": "nao",
        "risco": "medio",
        "escopo_publicacao": "publicacao-verificada",
        "revisao_instrumento": "b" * 40,
        "inicio": "2026-09-01T10:00:00+00:00",
        "fim": "2026-09-01T10:30:00+00:00",
        "estado": "concluida",
        "fonte": "muralha-do-travessao",
        "metricas": metricas,
    }
    evento["id"] = auditor.identidade_estrutural(evento)
    return evento


def test_auditor_nao_importa_funcoes_decisorias():
    caminho = RAIZ / "ci" / "auditar_medicao_fase4.py"
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.update(nome.name for nome in no.names)
        elif isinstance(no, ast.ImportFrom):
            importados.add(no.module)

    assert "analise_fase4" not in importados
    assert "registrar_tarefa_fase4" not in importados
    assert "telemetria" not in importados


def test_recalculo_prova_hash_contagens_nulos_e_unidade_por_tarefa():
    eventos = [evento_legado(numero) for numero in range(1, 5)]
    eventos.append(evento_legado(5, tarefa="TAR-1", nulos=10))
    esperado = hashlib.sha256(
        json.dumps(eventos, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

    resultado = auditor.auditar_eventos(eventos, RAIZ)

    assert resultado["entrada_sha256"] == esperado
    assert resultado["eventos_tarefa_medida"] == 5
    assert resultado["eventos_estruturalmente_validos"] == 5
    assert resultado["candidatos_confirmatorios_schema2_encerrados"] == 0
    assert resultado["tarefas_confirmatorias_completas"] == 0
    assert resultado["tarefas_distintas"] == 4
    assert resultado["pares_declarados_ou_elegiveis"] == 0
    assert resultado["metricas_ausentes_nao_convertidas_em_zero"] == 54


def test_mutacoes_de_remocao_estado_e_nulo_sao_detectadas():
    eventos = [evento_legado(numero) for numero in range(1, 6)]
    original = auditor.auditar_eventos(eventos, RAIZ)

    removido = auditor.auditar_eventos(eventos[:-1], RAIZ)
    assert removido["entrada_sha256"] != original["entrada_sha256"]
    assert removido["eventos_tarefa_medida"] == 4

    estado_invalido = json.loads(json.dumps(eventos))
    estado_invalido[0]["estado"] = "inventado"
    alterado = auditor.auditar_eventos(estado_invalido, RAIZ)
    assert alterado["eventos_estruturalmente_validos"] == 4

    zero_inventado = json.loads(json.dumps(eventos))
    zero_inventado[0]["metricas"]["contexto_bytes"] = 0
    com_zero = auditor.auditar_eventos(zero_inventado, RAIZ)
    assert com_zero["metricas_ausentes_nao_convertidas_em_zero"] == 54
    assert original["metricas_ausentes_nao_convertidas_em_zero"] == 55


def test_revisoes_publicadas_sao_derivadas_dos_textos_versionados(tmp_path):
    arquivos = ("ci/telemetria.py", "ci/registrar_tarefa_fase4.py",
                "ci/analise_fase4.py", "docs/decisoes/PROTOCOLO-FASE4-MEDICAO.md")
    for relativo in arquivos:
        caminho = tmp_path / relativo
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(f"fonte {relativo}\nlição\n".encode("utf-8"))
    resultado = auditor.auditar_eventos([], tmp_path)
    assert resultado["revisao_instrumento"] == "8d26b4980931e4f1b222ce76b0865c6ad3982a92"
    assert resultado["revisao_analise"] == (
        "828d40b8d25c7b822c44fcace286894070806b112ad81c5f929deeb41474d596"
    )
    caminho = tmp_path / "ci/analise_fase4.py"
    caminho.write_bytes(caminho.read_bytes().replace(b"\n", b"\r\n"))
    normalizado = auditor.auditar_eventos([], tmp_path)
    assert normalizado["revisao_instrumento"] == resultado["revisao_instrumento"]
    assert normalizado["revisao_analise"] == resultado["revisao_analise"]
    caminho.write_bytes(caminho.read_bytes() + b"mudanca\n")
    alterado = auditor.auditar_eventos([], tmp_path)
    assert alterado["revisao_instrumento"] != resultado["revisao_instrumento"]
    assert alterado["revisao_analise"] != resultado["revisao_analise"]


def test_fonte_privada_ausente_reprova_com_caminho_e_acao(
    tmp_path, monkeypatch, capsys
):
    git_comum = tmp_path / ".git"
    git_comum.mkdir()
    monkeypatch.setattr(auditor, "_git_comum", lambda raiz: git_comum)

    assert auditor.main(["--local"]) == 2
    saida = capsys.readouterr().out
    assert f"fonte_ausente: {git_comum / 'telemetria-dos-robos'}" in saida
    assert "execute na bancada que contém o caderno privado" in saida
