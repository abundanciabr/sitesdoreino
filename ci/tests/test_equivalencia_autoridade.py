"""A autoridade da base classifica guardas declarados, mesmo fora de CODEOWNERS."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import autoridade_das_fontes as autoridade
from _nucleo import ErroDeInstrumentacao, Estado


def test_guarda_da_base_exige_revisao_mesmo_com_grant_de_arquivos(monkeypatch, tmp_path):
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github/CODEOWNERS").write_text("/ci/ @dono\n", encoding="utf-8")
    (tmp_path / "INVARIANTES.md").write_text(
        "### [INV-X] Identificadores únicos\n"
        "- **O quê:** não duplicar.\n"
        "- **Teste-Guarda:** `services/alunos/tests/test_inv_x.py` — dois IDs distintos.\n"
        "- **Célula dona:** alunos\n",
        encoding="utf-8",
    )
    (tmp_path / "candidate").mkdir()
    (tmp_path / "candidate/INVARIANTES.md").write_text("", encoding="utf-8")
    monkeypatch.setattr(autoridade, "BASE", tmp_path)
    monkeypatch.setattr(autoridade, "candidato_inerte", lambda *args: None)
    monkeypatch.setattr(autoridade, "base_na_main", lambda consulta, numero, sha: consulta("pulls/1"))
    monkeypatch.setattr(autoridade, "prova_da_base", lambda *args: (True, "PASS", "TAR-991", "painel/registros/prova.js"))
    monkeypatch.setattr(autoridade, "mandato_reutilizavel", lambda *args: True)
    monkeypatch.setattr(autoridade, "checar_mandato", lambda *args: SimpleNamespace(estado=Estado.PASS))
    caminho = "services/alunos/tests/test_inv_x.py"
    def consulta(rota):
        if rota == "pulls/1":
            return {"state": "open", "head": {"sha": "a" * 40}, "base": {"ref": "main"},
                    "html_url": "https://github.com/abundanciabr/sitesdoreino/pull/1", "body": "", "user": {"login": "autor"}}
        if rota.startswith("pulls/1/files?"):
            return [{"filename": caminho}] if "page=1" in rota else []
        raise AssertionError(rota)
    assert autoridade.analisar(1, "a" * 40, tmp_path / "candidate", consulta)[:2] == ("PASS", True)
    assert autoridade.conclusao("PASS", True, "skipped") == "failure"
    assert autoridade.conclusao("PASS", True, "success") == "success"
    caminho = "INVARIANTES.md"
    assert autoridade.analisar(1, "a" * 40, tmp_path / "candidate", consulta)[:2] == ("PASS", True)
    caminho = "services/catalogo/models.py"
    assert autoridade.analisar(1, "a" * 40, tmp_path / "candidate", consulta)[:2] == ("PASS", False)
def test_documento_sem_guardas_emite_error(monkeypatch, tmp_path, capsys):
    saida = tmp_path / "saida.txt"
    monkeypatch.setenv("GITHUB_REPOSITORY", "abundanciabr/sitesdoreino")
    monkeypatch.setenv("GH_TOKEN", "teste")
    monkeypatch.setenv("GITHUB_OUTPUT", str(saida))
    monkeypatch.setattr(sys, "argv", ["autoridade_das_fontes.py", "analisar", "--pr", "1", "--head", "a" * 40, "--candidato", str(tmp_path)])
    def documento_invalido(*args):
        raise ErroDeInstrumentacao("nenhuma linha Teste-Guarda")
    monkeypatch.setattr(autoridade, "analisar", documento_invalido)
    assert autoridade.main() == 2
    assert "estado=ERROR" in saida.read_text(encoding="utf-8")
    assert "Confira API, checkout e base; repita o check" in capsys.readouterr().out