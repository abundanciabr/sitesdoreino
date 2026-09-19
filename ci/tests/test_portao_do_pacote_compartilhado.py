"""O portão do pacote compartilhado, e a prova de que ele REPROVA.

Dois papéis, no mesmo arquivo e de propósito:

1. `test_as_wheels_vendorizadas_sao_as_wheels_deste_fonte` É o portão. Ele roda
   na árvore de verdade, dentro do `muralhas.yml` (`python ci/ci.py --apenas
   testador` é pytest sobre `ci/tests/`), que é o único workflow sem filtro de
   caminho. Antes dele, um PR que só mexia em `packages/outbox-relay` não
   acordava suíte alguma: `celulas_do_diff` devolvia `[]`, o `ci-celula-gate`
   imprimia SKIP verde e o pouso integrava (`armadilhas/487`).

2. Os demais provam que ele morde. Portão que não reprova nada é pior que
   portão nenhum, porque compra confiança sem pagar por ela — [INV-CI01] e a
   lição 3 do Lote A. Cada um sabota uma coisa DIFERENTE numa árvore de mentira
   e exige o veredito exato: divergência de conteúdo é FAIL, wheel renomeada
   sem reconstruir é FAIL, requirements apontando outra wheel é FAIL, e o que
   impede a MEDIÇÃO (pacote fora do lugar, wheel ilegível, zero consumidores) é
   ERROR, nunca PASS.
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import portao_do_pacote_compartilhado as portao  # noqa: E402
from _nucleo import Estado, raiz_do_repo  # noqa: E402

RAIZ = raiz_do_repo()
PORTAO = CI / "portao_do_pacote_compartilhado.py"

RELAY = "def publicar():\n    return 1\n"
INIT = "from .relay import publicar\n"


def _wheel(destino: Path, versao: str, modulos: dict[str, str]) -> Path:
    """Uma wheel de mentira: só o que este portão lê (módulos e METADATA)."""
    caminho = destino / f"outbox_relay-{versao}-py3-none-any.whl"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(caminho, "w") as zf:
        for nome, corpo in modulos.items():
            zf.writestr(f"outbox_relay/{nome}", corpo)
        zf.writestr(
            f"outbox_relay-{versao}.dist-info/METADATA",
            f"Metadata-Version: 2.4\nName: outbox-relay\nVersion: {versao}\n",
        )
    return caminho


@pytest.fixture
def arvore(repo) -> Path:
    """Repositório de mentira com o pacote, uma célula e a wheel em dia."""
    raiz = repo.raiz
    src = raiz / portao.PACOTE / "src" / "outbox_relay"
    src.mkdir(parents=True)
    (src / "relay.py").write_text(RELAY, encoding="utf-8")
    (src / "__init__.py").write_text(INIT, encoding="utf-8")
    (raiz / portao.PACOTE / "pyproject.toml").write_text(
        '[project]\nname = "outbox-relay"\nversion = "0.3.1"\n', encoding="utf-8"
    )
    _wheel(
        raiz / "services" / "falsa" / "vendor",
        "0.3.1",
        {"relay.py": RELAY, "__init__.py": INIT},
    )
    (raiz / "services" / "falsa" / "requirements.txt").write_text(
        "services/falsa/vendor/outbox_relay-0.3.1-py3-none-any.whl\n", encoding="utf-8"
    )
    return raiz


def test_as_wheels_vendorizadas_sao_as_wheels_deste_fonte():
    """O PORTÃO. Vermelho aqui significa: reconstrua as wheels no MESMO PR."""
    relatorio = portao.rodar(RAIZ)
    assert relatorio.estado is Estado.PASS, relatorio.render()
    celulas = {r.nome.split("/")[0] for r in relatorio.resultados}
    assert celulas >= {"alunos", "identidade"}, (
        "uma célula deixou de vendorizar o pacote e o portão passou a conferir "
        "menos do que conferia.\n" + relatorio.render()
    )


def test_arvore_em_dia_passa(arvore: Path):
    assert portao.rodar(arvore).estado is Estado.PASS


def test_wheel_que_ficou_para_tras_do_fonte_reprova(arvore: Path):
    fonte = arvore / portao.PACOTE / "src" / "outbox_relay" / "relay.py"
    fonte.write_text(
        RELAY + "# a correcao de bug que nao foi entregue\n", encoding="utf-8"
    )

    relatorio = portao.rodar(arvore)

    assert relatorio.estado is Estado.FAIL
    assert "relay.py divergiu do fonte" in relatorio.render()


def test_modulo_novo_do_fonte_ausente_da_wheel_reprova(arvore: Path):
    novo = arvore / portao.PACOTE / "src" / "outbox_relay" / "assinatura.py"
    novo.write_text("CHAVE = 1\n", encoding="utf-8")

    relatorio = portao.rodar(arvore)

    assert relatorio.estado is Estado.FAIL
    assert "NÃO está dentro da wheel" in relatorio.render()


def test_wheel_renomeada_sem_ser_reconstruida_reprova(arvore: Path):
    """Trocar o número no nome do arquivo não é publicar versão nova."""
    (arvore / portao.PACOTE / "pyproject.toml").write_text(
        '[project]\nname = "outbox-relay"\nversion = "0.4.0"\n', encoding="utf-8"
    )
    vendor = arvore / "services" / "falsa" / "vendor"
    antiga = vendor / "outbox_relay-0.3.1-py3-none-any.whl"
    antiga.rename(vendor / "outbox_relay-0.4.0-py3-none-any.whl")
    (arvore / "services" / "falsa" / "requirements.txt").write_text(
        "services/falsa/vendor/outbox_relay-0.4.0-py3-none-any.whl\n", encoding="utf-8"
    )

    relatorio = portao.rodar(arvore)

    assert relatorio.estado is Estado.FAIL
    assert "renomeada, não reconstruída" in relatorio.render()


def test_modulo_apagado_do_fonte_que_sobrou_na_wheel_reprova(arvore: Path):
    """Apagar código do pacote também é mudança que a wheel precisa receber."""
    (arvore / portao.PACOTE / "src" / "outbox_relay" / "relay.py").unlink()

    relatorio = portao.rodar(arvore)

    assert relatorio.estado is Estado.FAIL
    assert "NÃO existe no fonte" in relatorio.render()


def test_versao_subida_no_pyproject_sem_wheel_nova_reprova(arvore: Path):
    """Subir o número no pyproject e deixar a wheel velha na pasta é mentir
    sobre o que a imagem instala."""
    (arvore / portao.PACOTE / "pyproject.toml").write_text(
        '[project]\nname = "outbox-relay"\nversion = "0.4.0"\n', encoding="utf-8"
    )

    relatorio = portao.rodar(arvore)

    assert relatorio.estado is Estado.FAIL
    assert "o nome do arquivo diz versão 0.3.1" in relatorio.render()


def test_requirements_apontando_outra_wheel_reprova(arvore: Path):
    """A imagem instala o que o requirements diz, não o que está na pasta."""
    (arvore / "services" / "falsa" / "requirements.txt").write_text(
        "services/falsa/vendor/outbox_relay-0.2.0-py3-none-any.whl\n", encoding="utf-8"
    )

    relatorio = portao.rodar(arvore)

    assert relatorio.estado is Estado.FAIL
    assert "a imagem publicaria outra coisa" in relatorio.render()


def test_sem_consumidor_algum_e_ERROR_e_nao_PASS(arvore: Path):
    """Apagar a wheel não pode ser o jeito de deixar o portão verde."""
    for wheel in (arvore / "services").glob("*/vendor/*.whl"):
        wheel.unlink()

    relatorio = portao.rodar(arvore)

    assert relatorio.estado is Estado.ERROR
    assert "nenhuma célula vendoriza" in relatorio.render()


def test_pacote_fora_do_lugar_e_ERROR_e_nao_PASS(arvore: Path):
    """Sem fonte não há comparação, e comparar nada nunca é aprovação."""
    for arquivo in (arvore / portao.PACOTE / "src" / "outbox_relay").glob("*.py"):
        arquivo.unlink()

    relatorio = portao.rodar(arvore)

    assert relatorio.estado is Estado.ERROR
    assert "não tem módulo algum" in relatorio.render()


def test_celula_que_vendoriza_sem_requirements_e_ERROR(arvore: Path):
    """Sem requirements não dá para provar o que a imagem instala."""
    (arvore / "services" / "falsa" / "requirements.txt").unlink()

    relatorio = portao.rodar(arvore)

    assert relatorio.estado is Estado.ERROR
    assert "não tem requirements.txt" in relatorio.render()


@pytest.mark.parametrize(
    "metadata, esperado",
    [
        (None, "arquivos METADATA"),
        ("Metadata-Version: 2.4\nName: outbox-relay\n", "não declara versão"),
    ],
    ids=["sem-metadata", "metadata-sem-versao"],
)
def test_wheel_sem_versao_legivel_e_ERROR(arvore: Path, metadata, esperado):
    """Não conseguir ler a versão é não conseguir medir, e isso não é PASS."""
    vendor = arvore / "services" / "falsa" / "vendor"
    antiga = next(vendor.glob("*.whl"))
    with zipfile.ZipFile(antiga) as zf:
        conteudo = {n: zf.read(n) for n in zf.namelist()}
    antiga.unlink()
    with zipfile.ZipFile(antiga, "w") as zf:
        for nome, corpo in conteudo.items():
            if nome.endswith(".dist-info/METADATA"):
                if metadata is None:
                    continue
                corpo = metadata.encode("utf-8")
            zf.writestr(nome, corpo)

    relatorio = portao.rodar(arvore)

    assert relatorio.estado is Estado.ERROR
    assert esperado in relatorio.render()


def test_wheel_ilegivel_e_ERROR_e_nao_FAIL(arvore: Path):
    """Instrumento quebrado não é culpa do código sob teste."""
    wheel = next((arvore / "services").glob("*/vendor/*.whl"))
    wheel.write_bytes(b"isto nao e um zip")

    relatorio = portao.rodar(arvore)

    assert relatorio.estado is Estado.ERROR
    assert "não consegui abrir a wheel" in relatorio.render()


def test_a_linha_de_comando_devolve_os_tres_codigos(arvore: Path):
    """0, 1 e 2 são o que a CI lê. PASS, FAIL e ERROR precisam chegar lá."""

    def rodar_cli(raiz: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(PORTAO), "--raiz", str(raiz)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    assert rodar_cli(arvore).returncode == 0

    fonte = arvore / portao.PACOTE / "src" / "outbox_relay" / "relay.py"
    fonte.write_text(RELAY + "# divergiu\n", encoding="utf-8")
    reprovado = rodar_cli(arvore)
    assert reprovado.returncode == 1
    assert portao.CONSERTO in reprovado.stdout

    for wheel in (arvore / "services").glob("*/vendor/*.whl"):
        wheel.unlink()
    assert rodar_cli(arvore).returncode == 2
