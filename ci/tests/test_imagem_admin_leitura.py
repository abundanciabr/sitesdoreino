"""A imagem de leitura precede a troca de serviços da TAR-427."""

from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[2]


def test_imagem_de_leitura_tem_configuracao_propria_e_nao_executa_migracao():
    dockerfile = (RAIZ / "services/admin/Dockerfile.leitura").read_text(
        encoding="utf-8"
    )
    assert "DJANGO_SETTINGS_MODULE=config.settings_leitura" in dockerfile
    assert 'CMD ["uvicorn", "config.asgi:application"' in dockerfile
    assert "migrate" not in dockerfile
    assert (RAIZ / "services/admin/Dockerfile").is_file()


def test_preparacao_publica_imagem_separada_antes_de_ativar_servicos():
    fluxo = yaml.safe_load(
        (RAIZ / ".github/workflows/deploy-celula.yml").read_text(encoding="utf-8")
    )
    passos = fluxo["jobs"]["deploy"]["steps"]
    publicacao = next(p for p in passos if "Dockerfile.leitura" in p.get("run", ""))
    assert publicacao["if"] == "matrix.celula == 'admin'"
    assert "plataforma-admin-leitura" in publicacao["run"]
    assert "ci/enviar_a_imagem.py" in publicacao["run"]
    assert passos.index(publicacao) < next(
        i for i, p in enumerate(passos) if "script_path" in p.get("with", {})
    )
