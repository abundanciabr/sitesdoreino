"""Guardas do portão que exige número PEDIDO para armadilha nova.

O que estes testes protegem, e por quê:

1. **O portão morde.** Entrada nova com número escolhido à mão reprova. Sem
   esta asserção, o portão poderia estar sempre verde e ninguém notaria — foi
   exatamente assim que os greens históricos do deploy mentiram até 21/08/2026.

2. **O portão CALA quando deve.** Ele mede só o que é NOVO em relação à base.
   As ~170 entradas históricas não são cobradas retroativamente, e renomear o
   slug de uma entrada antiga não é entrada nova. Um portão que reprova PR
   correto é pior que a colisão que ele evita: ensina a ignorar o vermelho.

3. **Servidor mudo é ERROR, nunca PASS** ([INV-CI01]). Este é o coração: sem
   falar com o servidor não há como saber se a reserva existe. Ler silêncio
   como "tem reserva" seria a trava que parece funcionar e não funciona — a
   categoria de falha mais cara deste projeto.

O cenário é um repositório Git DE VERDADE com um `origin` de verdade: as refs
de reserva são criadas com `git update-ref` no bare, e o portão as lê com
`ls-remote`, como faria em produção. Dublê aqui esconderia justamente a parte
que já enganou este projeto (`armadilhas/061`).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import reservas_das_armadilhas as reservas  # noqa: E402
from _nucleo import ErroDeInstrumentacao, Estado  # noqa: E402


def _git(raiz: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(raiz),
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.fixture
def cenario(tmp_path: Path) -> tuple[Path, Path]:
    """Um repo com `origin` bare e três entradas históricas já na base."""
    bare = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "-b", "main", str(bare)],
        check=True,
        capture_output=True,
        timeout=120,
    )

    raiz = tmp_path / "repo"
    (raiz / "armadilhas").mkdir(parents=True)
    (raiz / "ci").mkdir()
    for marca in ("CONSTITUICAO.md", "INVARIANTES.md"):
        (raiz / marca).write_text("cenario", encoding="utf-8")
    for numero in ("001", "002", "003"):
        (raiz / "armadilhas" / f"{numero}-historica.md").write_text(
            f"# entrada {numero}\n", encoding="utf-8"
        )

    _git(raiz.parent, "init", "-q", "-b", "main", str(raiz))
    _git(raiz, "config", "user.email", "t@e")
    _git(raiz, "config", "user.name", "t")
    _git(raiz, "remote", "add", "origin", str(bare))
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-qm", "base")
    _git(raiz, "push", "-q", "origin", "main")
    return raiz, bare


def _reservar(bare: Path, numero: str) -> None:
    """Cria a ref de reserva no servidor, como `ci/reservar.py` faria."""
    sha = subprocess.run(
        ["git", "rev-parse", "main"],
        cwd=str(bare),
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    ).stdout.strip()
    _git(bare, "update-ref", f"{reservas.NS}/{numero}", sha)


def _entrada_nova(raiz: Path, nome: str) -> None:
    (raiz / "armadilhas" / nome).write_text(f"# {nome}\n", encoding="utf-8")


# --------------------------------------------------------------------------
# 1 — o portão morde
# --------------------------------------------------------------------------


def test_entrada_nova_com_numero_escolhido_a_mao_reprova(cenario):
    raiz, _bare = cenario
    _entrada_nova(raiz, "047-escolhida-a-mao.md")

    relatorio = reservas.conferir(raiz, base="origin/main")

    assert relatorio.estado is Estado.FAIL, relatorio.render()
    assert "047" in relatorio.render()


def test_a_recusa_ensina_o_conserto_executavel(cenario):
    """Terceira exigência da linha de precisão: alternativa executável na hora."""
    raiz, _bare = cenario
    _entrada_nova(raiz, "047-escolhida-a-mao.md")

    texto = reservas.conferir(raiz, base="origin/main").render()

    assert "ci/reservar.py numero armadilha" in texto
    assert "ci/indice_de_armadilhas.py" in texto


# --------------------------------------------------------------------------
# 2 — o portão cala quando deve
# --------------------------------------------------------------------------


def test_entrada_nova_com_numero_pedido_passa(cenario):
    raiz, bare = cenario
    _reservar(bare, "047")
    _entrada_nova(raiz, "047-pedida-ao-almoxarife.md")

    relatorio = reservas.conferir(raiz, base="origin/main")

    assert relatorio.estado is Estado.PASS, relatorio.render()


def test_catalogo_historico_sem_reserva_nao_e_cobrado(cenario):
    """As ~170 entradas antigas nasceram antes da regra — cobrá-las seria
    vermelho que ninguém pode consertar."""
    raiz, _bare = cenario

    relatorio = reservas.conferir(raiz, base="origin/main")

    assert relatorio.estado is Estado.PASS, relatorio.render()
    assert "nenhuma entrada nova" in relatorio.render()


def test_renomear_o_slug_de_entrada_antiga_nao_e_entrada_nova(cenario):
    """O número é a identidade; o nome do arquivo não é."""
    raiz, _bare = cenario
    antiga = raiz / "armadilhas" / "002-historica.md"
    antiga.rename(raiz / "armadilhas" / "002-com-slug-melhor.md")

    relatorio = reservas.conferir(raiz, base="origin/main")

    assert relatorio.estado is Estado.PASS, relatorio.render()


def test_o_numero_e_comparado_com_tres_digitos(cenario):
    """`47` no disco e `047` no servidor são o MESMO número.

    Sem a normalização, uma reserva legítima passaria despercebida e o portão
    reprovaria quem fez tudo certo.
    """
    raiz, bare = cenario
    _reservar(bare, "047")
    _entrada_nova(raiz, "47-sem-zero-a-esquerda.md")

    relatorio = reservas.conferir(raiz, base="origin/main")

    assert relatorio.estado is Estado.PASS, relatorio.render()


# --------------------------------------------------------------------------
# 3 — não conseguir medir NUNCA vira PASS
# --------------------------------------------------------------------------


def test_servidor_inalcancavel_e_ERROR_e_nao_pass(cenario, tmp_path):
    """A asserção que sustenta o portão inteiro ([INV-CI01])."""
    raiz, _bare = cenario
    _entrada_nova(raiz, "047-escolhida-a-mao.md")
    _git(raiz, "remote", "set-url", "origin", str(tmp_path / "nao-existe.git"))

    with pytest.raises(ErroDeInstrumentacao) as erro:
        reservas.conferir(raiz, base="origin/main")

    assert "não" in str(erro.value).lower()


def test_base_inexistente_e_ERROR_e_nao_pass(cenario):
    """Sem a base não dá para saber o que é NOVO — e supor seria cobrar o
    catálogo inteiro, ou não cobrar ninguém."""
    raiz, _bare = cenario

    with pytest.raises(ErroDeInstrumentacao):
        reservas.conferir(raiz, base="origin/ramo-que-nao-existe")


def test_pasta_de_armadilhas_vazia_e_ERROR_e_nao_pass(tmp_path: Path):
    """Zero entradas é instrumento quebrado, não catálogo limpo."""
    raiz = tmp_path / "vazio"
    (raiz / "armadilhas").mkdir(parents=True)

    with pytest.raises(ErroDeInstrumentacao):
        reservas.numeros_no_disco(raiz)


# --------------------------------------------------------------------------
# 4 — a muralha está de fato ligada em ci.py
# --------------------------------------------------------------------------


def test_a_muralha_esta_na_lista_que_o_ci_roda():
    """Portão que existe e ninguém chama é garantia sem mecanismo — o padrão 2
    da RETROSPECTIVA-FASE-D, aqui em forma de asserção."""
    import ci as runner

    nomes = {portao.nome for portao in runner.MURALHAS}
    assert "muralha-das-reservas" in nomes


def test_o_script_da_muralha_existe_e_aponta_para_o_portao():
    script = CI / "muralha-das-reservas.sh"
    assert script.is_file()
    assert "ci/reservas_das_armadilhas.py" in script.read_text(encoding="utf-8")
