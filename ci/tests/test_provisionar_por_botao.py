"""A operação VPS provisionar repassa valores públicos sem shell."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("operar_provisionar", RAIZ / "infra" / "operar.py")
operar = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = operar
spec.loader.exec_module(operar)


def _ctx(tmp_path: Path, chamadas: list) -> operar.Contexto:
    return operar.Contexto(
        raiz=RAIZ,
        ambiente={"PLATAFORMA_DIR": str(tmp_path), "OPERAR_ESTADO": str(tmp_path / "estado")},
        processo=lambda *args, **kwargs: chamadas.append((args, kwargs)) or (0, ""),
        espera=0,
    )


def test_a_cli_expoe_alvo_e_argumentos():
    op = operar.OPERACOES["provisionar"]
    assert op.executar is operar.op_provisionar
    assert [p.nome for p in op.params] == ["alvo", "argumento"]
    assert op.params[0].obrigatorio


def test_alvo_invalido_nao_executa_nada(tmp_path):
    chamadas: list = []
    assert operar.main(["provisionar", "--alvo", "../env/admin"], _ctx(tmp_path, chamadas)) != 0
    assert chamadas == []
    assert not (tmp_path / "publicacoes").exists()


def test_host_publico_chega_a_execucao_com_o_arquivo_certo(tmp_path, monkeypatch):
    script = RAIZ / "infra" / "provisionar-cursos.sh"
    chamadas: list = []
    monkeypatch.setattr(operar, "fcntl", None)
    monkeypatch.setattr(operar, "_provisionar_sob_trava",
                        lambda ctx, alvo, arquivo, argumentos: chamadas.append((alvo, arquivo, argumentos)) or 0)
    assert operar.main(["provisionar", "--alvo", "cursos"], _ctx(tmp_path, [])) == 0
    assert chamadas == [("cursos", script, ["meshcraft.top"])]


def test_os_roteiros_de_verdade_dizem_na_linha_de_uso_o_que_recebem():
    host = {"cursos", "encomendas", "gamificacao", "pages", "pares-da-prancheta"}
    obrigatorios = {"email": 1, "sugestoes": 2, "equipe-da-gamificacao": 1}
    roteiros = sorted((RAIZ / "infra").glob("provisionar-*.sh"))
    assert roteiros
    for roteiro in roteiros:
        alvo = roteiro.name[len("provisionar-"):-len(".sh")]
        uso = operar.uso_do_roteiro(roteiro)
        assert uso.host == ("meshcraft.top" if alvo in host else None), alvo
        assert uso.obrigatorios == obrigatorios.get(alvo, 0), alvo


def test_roteiro_de_verdade_com_valor_obrigatorio_recusa_sem_ele(tmp_path, capsys):
    chamadas: list = []
    for alvo, minimo in (("email", 1), ("sugestoes", 2), ("equipe-da-gamificacao", 1)):
        assert operar.main(["provisionar", "--alvo", alvo], _ctx(tmp_path, chamadas)) == 1
        assert f"precisa de {minimo} argumento(s)" in capsys.readouterr().out
    assert chamadas == []
    assert not (tmp_path / "publicacoes").exists()
