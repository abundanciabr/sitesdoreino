import importlib
import subprocess
import sys


def test_subprocesso_legado_importa_settings_da_propria_celula(monkeypatch, tmp_path):
    servicos = tmp_path / "services"
    legado = servicos / "alunos"
    (legado / "config").mkdir(parents=True)
    (legado / "config" / "settings.py").write_text("ORIGEM = 'legado'\n")
    central = tmp_path / "app"
    (central / "config").mkdir(parents=True)
    (central / "config" / "__init__.py").write_text("")
    (central / "config" / "settings.py").write_text("ORIGEM = 'unificado'\n")

    monkeypatch.setenv("PROVA_POSTGRES_URL", "postgresql://ci:ci@localhost/ci_db")
    monkeypatch.setenv("PROVA_ORIGEM_SERVICES", str(servicos))
    monkeypatch.setenv("PYTHONPATH", str(central))
    prova = importlib.import_module("prova")
    monkeypatch.setattr(prova, "RAIZ_SERVICOS", servicos)

    env = prova.ambiente_legado("alunos", {"alunos": "postgresql://ci:ci@localhost/ci_db"})
    assert env["PYTHONPATH"] == str(legado.resolve())
    assert env["CELULA"] == "alunos"
    assert env["DJANGO_SETTINGS_MODULE"] == "config.settings"
    assert env["DATABASE_URL"] == "postgresql://ci:ci@localhost/ci_db"
    resultado = subprocess.run(
        [sys.executable, "-c", "from config.settings import ORIGEM; print(ORIGEM)"],
        cwd=legado, env=env, capture_output=True, text=True, check=True,
    )
    assert resultado.stdout.strip() == "legado"
