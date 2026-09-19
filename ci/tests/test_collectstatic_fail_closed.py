from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]


DOCKERFILES_DA_FASE_3 = [
    RAIZ / "services" / "admin" / "Dockerfile",
    RAIZ / "services" / "alunos" / "Dockerfile",
    RAIZ / "services" / "cursos" / "Dockerfile",
    RAIZ / "services" / "identidade" / "Dockerfile",
]


def test_dockerfiles_da_fase_3_nao_escondem_collectstatic():
    encontrados = [
        str(dockerfile.relative_to(RAIZ))
        for dockerfile in DOCKERFILES_DA_FASE_3
        if "collectstatic --noinput || true" in dockerfile.read_text(encoding="utf-8")
    ]

    assert encontrados == []
