"""O MAPA DAS CÉLULAS: o leitor de `celulas.yml` e a pergunta "este arquivo é de quem?"."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "ci"))

import mapa_de_celulas  # noqa: E402
from _nucleo import ErroDeInstrumentacao  # noqa: E402


@pytest.mark.parametrize(
    "conteudo",
    [
        "isto: não tem a chave certa\n",
        "celulas: {}\n",
        "celulas:\n  quiz: 'não é bloco'\n",
        "celulas:\n  quiz:\n    consome: []\n",  # sem caminhos
        "celulas:\n  quiz:\n    caminhos: [services/quiz]\n    consome: 'texto'\n",
    ],
)
def test_mapa_malformado_e_ERROR_e_nunca_um_mapa_vazio(tmp_path: Path, conteudo: str):
    """Mapa quebrado não pode virar "nenhuma célula existe": a publicação
    concluiria que o push não toca célula nenhuma e não publicaria nada."""
    raiz = tmp_path / "repo"
    raiz.mkdir()
    (raiz / "celulas.yml").write_text(conteudo, encoding="utf-8")
    with pytest.raises(ErroDeInstrumentacao):
        mapa_de_celulas.carregar(raiz)


def test_mapa_ausente_e_ERROR(tmp_path: Path):
    with pytest.raises(ErroDeInstrumentacao):
        mapa_de_celulas.carregar(tmp_path)


def test_o_arquivo_da_celula_pertence_a_ela_e_um_arquivo_solto_nao_pertence_a_ninguem():
    mapa = mapa_de_celulas.carregar(RAIZ)
    assert list(mapa) == ["aplicacao"]
    assert mapa_de_celulas.celula_do_caminho("services/admin/config/urls.py", mapa) == "aplicacao"
    assert mapa_de_celulas.celula_do_caminho("services/quiz/app.py", mapa) == "aplicacao"
    assert mapa_de_celulas.celula_do_caminho("packages/site_errors/src/x.py", mapa) == "aplicacao"
    assert mapa_de_celulas.celula_do_caminho("documentos/pagina.md", mapa) == "aplicacao"
    assert mapa_de_celulas.celula_do_caminho("README.md", mapa) is None
    assert mapa_de_celulas.celula_do_caminho("ci/_nucleo.py", mapa) is None


def test_prefixo_casa_por_SEGMENTO_e_nao_por_texto():
    """`services` captura módulos novos, mas não um prefixo apenas parecido."""
    mapa = mapa_de_celulas.carregar(RAIZ)
    assert mapa_de_celulas.celula_do_caminho("services/quizzes/app.py", mapa) == "aplicacao"
    assert mapa_de_celulas.celula_do_caminho("services-extra/app.py", mapa) is None


def test_celulas_do_diff_e_ordenado_e_sem_repeticao():
    mapa = mapa_de_celulas.carregar(RAIZ)
    achadas = mapa_de_celulas.celulas_do_diff(
        [
            "services/quiz/a.py",
            "services/quiz/b.py",
            "services/admin/config/urls.py",
            "README.md",
        ],
        mapa,
    )
    assert achadas == ["aplicacao"]


def test_toda_celula_declarada_existe_no_disco():
    mapa = mapa_de_celulas.carregar(RAIZ)
    inexistentes = [
        f"{celula.nome}: {base}"
        for celula in mapa.values()
        for base in celula.caminhos
        if not (RAIZ / base).exists()
    ]
    assert not inexistentes, inexistentes


def test_todo_workflow_que_le_o_mapa_instala_o_leitor():
    """O mapa é YAML: sem PyYAML, quem o lê não conclui e falha alto."""
    import yaml as _yaml

    pasta = RAIZ / ".github" / "workflows"
    for arquivo in sorted(pasta.glob("*.yml")):
        texto = arquivo.read_text(encoding="utf-8")
        if "detectar-celulas" not in texto and "mapa_de_celulas" not in texto:
            continue
        fluxo = _yaml.safe_load(texto)
        instala = [
            passo
            for job in fluxo["jobs"].values()
            for passo in job.get("steps", [])
            if "pyyaml" in str(passo.get("run", "")).lower()
        ]
        assert instala, (
            f"{arquivo.name} lê o mapa das células e não instala o PyYAML: "
            "a detecção vai falhar alto em todo push"
        )


def test_pacote_site_errors_acorda_todas_as_celulas_consumidoras():
    mapa = mapa_de_celulas.carregar(RAIZ)
    consumidores = sorted(
        wheel.parents[1].name
        for wheel in (RAIZ / "services").glob("*/vendor/site_errors-*.whl")
    )

    assert consumidores, "o pacote site_errors não tem consumidor vendorizado"
    assert mapa_de_celulas.celulas_do_diff(
        ["packages/site_errors/src/site_errors/handlers.py"], mapa
    ) == ["aplicacao"]
