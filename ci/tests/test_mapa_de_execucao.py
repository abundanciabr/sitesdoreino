"""O pacote orienta pela fila local sem reivindicar trabalho nem abrir sessão."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

import economia_da_fabrica as economia
import fila
import mapa_de_execucao as mapa
import sessao
from _nucleo import ErroDeInstrumentacao

AGORA = datetime(2026, 9, 10, tzinfo=timezone.utc)


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    for pasta in ("fila/tarefas", "fila/eventos", "services/admin", "armadilhas"):
        (tmp_path / pasta).mkdir(parents=True)
    (tmp_path / "celulas.yml").write_text(
        "celulas:\n  admin:\n    caminhos: [services/admin, painel]\n    consome: []\n",
        encoding="utf-8",
    )
    dados = {
        "arquivo": "324-exemplo", "id": "TAR-324", "titulo": "Preparar orientação",
        "toca": ["admin", "ci/mapa_de_execucao.py"], "cria": [],
        "evidencia_exigida": "Uma orientação reproduzível com fonte e revisão",
        "despacho": "Criar comportamento de orientação pela tarefa declarada.",
        "origem": "pedido do mantenedor", "criada_em": "2026-09-10",
    }
    (tmp_path / "fila/tarefas/324-exemplo.json").write_text(
        json.dumps(dados), encoding="utf-8"
    )
    monkeypatch.setattr(mapa, "_ler_revisao", lambda raiz: "a" * 40)
    monkeypatch.setattr(mapa, "_ler_estado_git", lambda raiz: "")
    monkeypatch.setattr(economia, "harness_ativo", lambda raiz=None: "codex")
    return tmp_path


def test_tarefa_nova_transporta_fonte_aceite_perfil_e_brief_existente(checkout, monkeypatch):
    compilar = Mock(wraps=economia.compilar_brief)
    monkeypatch.setattr(economia, "compilar_brief", compilar)

    pacote = mapa.materializar_pacote(checkout, "TAR-324", agora=AGORA)

    assert pacote["tipo"] == "tarefa_nova"
    assert pacote["resultado"] == "PASS"
    assert pacote["tar"] == "TAR-324"
    assert pacote["objetivo"] == "Preparar orientação"
    assert pacote["despacho"] == "Criar comportamento de orientação pela tarefa declarada."
    assert pacote["aceite"] == "Uma orientação reproduzível com fonte e revisão"
    assert pacote["origem"] == "pedido do mantenedor"
    assert pacote["fonte"] == "fila/tarefas/324-exemplo.json"
    assert pacote["caminhos_declarados"] == ["services/admin/", "ci/mapa_de_execucao.py"]
    assert pacote["celulas_observadas"] == [
        {"caminho": "services/admin/", "celula": "admin"},
        {"caminho": "ci/mapa_de_execucao.py", "celula": None},
    ]
    assert pacote["estado_fila"]["estado"] == fila.NA_FILA
    assert pacote["perfil_economico"]["modelo"] == "gpt-6-astra"
    assert pacote["perfil_economico"]["esforco"] == "high"
    assert pacote["perfil_economico"]["teto_contexto"] == 180000
    compilar.assert_called_once()
    assert compilar.call_args.kwargs["objetivo"] == pacote["despacho"]
    assert "modelo_recomendado: gpt-6-astra" in pacote["brief"]
    assert pacote["revisao"] == "a" * 40
    assert datetime.fromisoformat(pacote["instante_utc"]).utcoffset() == timezone.utc.utcoffset(None)
    assert "fila/eventos/" in pacote["contexto"]["fontes"]
    assert pacote["contexto"]["limites"]
    assert "Limitação:" in pacote["contexto"]["texto"]
    json.dumps(pacote)


def test_tarefa_inexistente_nao_inventa_orientacao(checkout):
    pacote = mapa.materializar_pacote(checkout, "TAR-999", agora=AGORA)
    assert pacote["tipo"] == "não_medido"
    assert pacote["resultado"] == "ERROR"
    assert pacote["fonte"] == "fila/tarefas/"
    assert "TAR-999" in pacote["causa"]
    assert "fila.py listar" in pacote["proximo_passo"]
    assert "brief" not in pacote


@pytest.mark.parametrize("tar", ["", "324", "TAR-324\n", "../../TAR-324", "TAR-x"])
def test_tar_malformada_recusa_antes_de_ler(checkout, monkeypatch, tar):
    ler = Mock(side_effect=AssertionError("não deveria coletar"))
    monkeypatch.setattr(mapa, "_ler_revisao", ler)
    with pytest.raises(ErroDeInstrumentacao, match="Use TAR-324"):
        mapa.materializar_pacote(checkout, tar, agora=AGORA)
    ler.assert_not_called()


@pytest.mark.parametrize("caminho", ["../fora", "admin/../../fora", r"..\fora", "/tmp/fora", r"C:\fora", r"C:fora", r"\\servidor\fora"])
def test_caminho_inseguro_recusa_sem_compilar(checkout, monkeypatch, caminho):
    arquivo = checkout / "fila/tarefas/324-exemplo.json"
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    dados["toca"] = [caminho]
    arquivo.write_text(json.dumps(dados), encoding="utf-8")
    compilar = Mock(side_effect=AssertionError("não deveria compilar"))
    monkeypatch.setattr(economia, "compilar_brief", compilar)
    with pytest.raises(ErroDeInstrumentacao, match="caminho relativo dentro da raiz"):
        mapa.materializar_pacote(checkout, "TAR-324", agora=AGORA)
    compilar.assert_not_called()


def test_revisao_alterada_na_coleta_invalida_o_pacote(checkout, monkeypatch):
    monkeypatch.setattr(mapa, "_ler_revisao", Mock(side_effect=["a" * 40, "b" * 40]))
    pacote = mapa.materializar_pacote(checkout, "TAR-324", agora=AGORA)
    assert pacote["tipo"] == "não_medido"
    assert pacote["resultado"] == "ERROR"
    assert pacote["fonte"] == "git HEAD"
    assert "mudou" in pacote["causa"]
    assert "brief" not in pacote


def test_estado_reivindicado_nao_e_rotulado_tarefa_nova(checkout):
    evento = {
        "arquivo": "20260910-100000-TAR-324-reivindicada", "tarefa": "TAR-324",
        "evento": "reivindicada", "quando": "2026-09-10T10:00:00+00:00", "quem": "sessao-a",
    }
    (checkout / f"fila/eventos/{evento['arquivo']}.json").write_text(
        json.dumps(evento), encoding="utf-8"
    )
    pacote = mapa.materializar_pacote(checkout, "TAR-324", agora=AGORA)
    assert pacote["tipo"] == "não_medido"
    assert pacote["estado_fila"]["estado"] == fila.REIVINDICADA
    assert "brief" not in pacote


@pytest.mark.parametrize("interface", ["api", "cli"])
def test_coleta_nao_chama_efeitos_nem_rede_e_nao_grava(checkout, monkeypatch, capsys, interface):
    proibidas = []
    for modulo, nomes in (
        (fila, ["cmd_pegar", "_escrever_evento", "reservas_no_servidor", "prs_citando_tarefas"]),
        (sessao, ["main", "Sessao", "correr_de_verdade", "escrever_de_verdade"]),
    ):
        for nome in nomes:
            funcao = Mock(side_effect=AssertionError(f"efeito proibido: {nome}"))
            monkeypatch.setattr(modulo, nome, funcao)
            proibidas.append(funcao)
    antes = {p.relative_to(checkout): p.read_bytes() for p in checkout.rglob("*") if p.is_file()}

    if interface == "api":
        assert mapa.materializar_pacote(checkout, "TAR-324", agora=AGORA)["resultado"] == "PASS"
    else:
        assert mapa.main(["--tar", "TAR-324", "--raiz", str(checkout)]) == 0
        assert json.loads(capsys.readouterr().out)["resultado"] == "PASS"

    depois = {p.relative_to(checkout): p.read_bytes() for p in checkout.rglob("*") if p.is_file()}
    assert depois == antes
    for funcao in proibidas:
        funcao.assert_not_called()


def test_fila_ilegivel_nao_vira_tarefa_inexistente(checkout):
    (checkout / "fila/tarefas/324-exemplo.json").write_text("{", encoding="utf-8")
    pacote = mapa.materializar_pacote(checkout, "TAR-324", agora=AGORA)
    assert pacote["tipo"] == "não_medido"
    assert "JSON" in pacote["causa"]
    assert "Corrija" in pacote["proximo_passo"]


def test_eventos_ausentes_nao_significam_fila_disponivel(checkout):
    (checkout / "fila/eventos").rmdir()
    pacote = mapa.materializar_pacote(checkout, "TAR-324", agora=AGORA)
    assert pacote["tipo"] == "não_medido"
    assert "pastas da fila" in pacote["causa"]


def test_head_indisponivel_nao_emite_brief(checkout, monkeypatch):
    monkeypatch.setattr(mapa, "_ler_revisao", Mock(side_effect=ErroDeInstrumentacao("git indisponível")))
    pacote = mapa.materializar_pacote(checkout, "TAR-324", agora=AGORA)
    assert pacote["tipo"] == "não_medido"
    assert pacote["revisao"] is None
    assert pacote["fonte"] == "git HEAD"
    assert "brief" not in pacote


@pytest.mark.parametrize("saida,codigo", [("a" * 40, 0), ("a" * 64, 0), ("a" * 42, 0), ("", 128)])
def test_leitura_de_head_so_executa_rev_parse(tmp_path, monkeypatch, saida, codigo):
    executar = Mock(return_value=subprocess.CompletedProcess([], codigo, saida, "erro de git"))
    monkeypatch.setattr(mapa.subprocess, "run", executar)
    if codigo or len(saida) not in (40, 64):
        with pytest.raises(ErroDeInstrumentacao):
            mapa._ler_revisao(tmp_path)
    else:
        assert mapa._ler_revisao(tmp_path) == saida
    assert executar.call_args.args[0] == ["git", "rev-parse", "--verify", "HEAD"]
    assert executar.call_args.kwargs["cwd"] == tmp_path


def test_cli_imprime_exatamente_o_pacote_da_api(checkout, monkeypatch, capsys):
    materializar = Mock(wraps=mapa.materializar_pacote)
    monkeypatch.setattr(mapa, "materializar_pacote", materializar)

    assert mapa.main(["--tar", "TAR-324", "--raiz", str(checkout), "--instante-utc", AGORA.isoformat()]) == 0

    captura = capsys.readouterr()
    materializar.assert_called_once()
    assert materializar.call_args.args == (checkout, "TAR-324")
    instante = materializar.call_args.kwargs["agora"]
    assert instante == AGORA
    esperado = materializar._mock_wraps(checkout, "TAR-324", agora=instante)
    assert json.loads(captura.out) == esperado
    assert captura.err == ""


@pytest.mark.parametrize("argumentos", [
    ["--tar", "../../fora"], [], ["--tar"], ["--outra", "TAR-324"],
    ["--tar", "TAR-324", "--instante-utc", "ontem"],
    ["--tar", "TAR-324", "--instante-utc", "2026-09-10T00:00:00"],
])
def test_cli_entrada_invalida_emite_json_sem_traceback(argumentos):
    resultado = subprocess.run(
        [sys.executable, "-B", mapa.__file__, *argumentos],
        capture_output=True, text=True, encoding="utf-8", check=False,
    )
    assert resultado.returncode == 2
    pacote = json.loads(resultado.stdout)
    assert pacote["tipo"] == "não_medido"
    assert pacote["resultado"] == "ERROR"
    assert pacote["fonte"] == "entrada do comando"
    assert "TAR-324" in pacote["proximo_passo"]
    assert resultado.stderr == ""


def test_mesma_entrada_e_instante_produzem_pacote_identico(checkout):
    primeiro = mapa.materializar_pacote(checkout, "TAR-324", agora=AGORA)
    segundo = mapa.materializar_pacote(checkout, "TAR-324", agora=AGORA)
    assert primeiro == segundo
    assert primeiro["instante_utc"] == AGORA.isoformat()


def test_instante_sem_utc_recusa(checkout):
    with pytest.raises(ErroDeInstrumentacao, match="UTC"):
        mapa.materializar_pacote(checkout, "TAR-324", agora=datetime(2026, 9, 10))


@pytest.mark.parametrize("estados", [[" M arquivo.py"], ["", "?? arquivo.py"]])
def test_checkout_sujo_antes_ou_durante_coleta_descarta_pacote(checkout, monkeypatch, estados):
    monkeypatch.setattr(mapa, "_ler_estado_git", Mock(side_effect=estados))
    pacote = mapa.materializar_pacote(checkout, "TAR-324", agora=AGORA)
    assert pacote["tipo"] == "não_medido"
    assert pacote["resultado"] == "ERROR"
    assert pacote["fonte"] == "git status --porcelain"
    assert "alterações" in pacote["causa"]
    assert "Preserve" in pacote["proximo_passo"]
    assert "brief" not in pacote
