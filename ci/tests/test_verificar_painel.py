"""O verificador do painel, provado nos TRÊS estados — e sabotado sete vezes.

Um verificador que nunca foi visto reprovando é um verificador que ninguém sabe
se reprova. A regra da casa nasceu do registro `20260826-032`, no dia em que um
guarda listado como "corrigido COM protetor que morde" foi sabotado de propósito
e continuou verde: *o valor esperado de um teste nunca pode ser produzido pela
mesma engrenagem que o teste existe para vigiar.*

Este arquivo é o par disso para `ci/verificar_painel.py`. Cada sabotagem monta um
repositório de mentira, quebra UMA coisa, e exige o vermelho — porque é
exatamente contra essas nove formas de mentira que o verificador existe:

  1. registro no Git e fora dos artefatos  → sumiu da tela
  2. registro nos artefatos e fora do Git  → o painel inventou
  3. id repetido dentro do mês             → o caso A B C C que passa por A B C D
  4. conteúdo trocado no empacotamento     → id certo, texto errado
  5. contagem declarada mentindo           → a página promete o que não entrega
  6. mês fantasma no disco                 → servido sem ninguém reivindicar
  7. `livro.js` de volta                   → o desenho antigo voltando em silêncio
  8. carimbos divergentes entre artefatos  → a Memória quebrada para sempre
  9. página sem carimbo                    → o diagnóstico perde uma distinção

O que NÃO é testado aqui: a validação de cada registro (essa é do gerador, e tem
suíte adversarial própria em `painel/testes/teste_gerador.js`). Este verificador
responde a uma pergunta só, e é a que o gerador não consegue responder sobre si
mesmo: *o que está nos artefatos é o que está no livro?*
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import BASH

RAIZ = Path(__file__).resolve().parents[2]
MARCAS_DA_RAIZ = ("CONSTITUICAO.md", "INVARIANTES.md", "ci", "contracts", "services")

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None or shutil.which("git") is None,
    reason="o verificador do painel precisa de node E git no PATH",
)


def _roda(raiz: Path) -> subprocess.CompletedProcess[str]:
    """Roda o verificador que mora DENTRO da raiz dada.

    Chamar o `ci/` de outra árvore mediria a outra árvore (`armadilhas/147`) —
    então cada cenário recebe a própria cópia do script.
    """
    return subprocess.run(
        [sys.executable, str(raiz / "ci" / "verificar_painel.py")],
        cwd=str(raiz),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )


def _repo_falso(tmp_path: Path) -> Path:
    """Um repositório de verdade (com Git) e um painel real dentro dele.

    Precisa ser um repositório Git de verdade porque a fonte independente do
    verificador é `git ls-files` — o ponto inteiro do arquivo que ele testa.
    """
    raiz = tmp_path / "repo"
    raiz.mkdir()
    shutil.copytree(RAIZ / "painel", raiz / "painel")
    # Os artefatos são MATERIALIZADOS aqui, e nunca commitados — é o desenho de
    # escritor único da Onda 3, e o cenário precisa reproduzi-lo para medir o
    # verificador de verdade. Gerar em vez de confiar na cópia também torna o
    # cenário independente do que existe no disco de quem roda os testes.
    shutil.copy(RAIZ / ".gitignore", raiz / ".gitignore")
    (raiz / "ci").mkdir()
    for arquivo in ("verificar_painel.py", "_nucleo.py"):
        shutil.copy(RAIZ / "ci" / arquivo, raiz / "ci" / arquivo)
    # As marcas que `raiz_do_repo()` exige para aceitar isto como raiz.
    for marca in MARCAS_DA_RAIZ:
        alvo = raiz / marca
        if not alvo.exists():
            if marca.endswith(".md"):
                alvo.write_text("cenário de teste\n", encoding="utf-8")
            else:
                alvo.mkdir(exist_ok=True)

    for comando in (
        ["node", "painel/gerar_manifesto.js"],
        ["git", "init", "-q"],
        ["git", "config", "user.email", "teste@exemplo"],
        ["git", "config", "user.name", "teste"],
        ["git", "add", "-A"],
        ["git", "commit", "-q", "-m", "cenário"],
    ):
        subprocess.run(
            comando, cwd=str(raiz), check=True, capture_output=True, timeout=120
        )
    return raiz


def _mes(raiz: Path) -> Path:
    return sorted((raiz / "painel").glob("livro-*.js"))[0]


def _registros_do_mes(caminho: Path) -> list[dict]:
    """Lê o arquivo de mês no formato de UMA LINHA POR REGISTRO (Onda 3)."""
    texto = caminho.read_text(encoding="utf-8")
    linhas = re.findall(r'^JSON\.parse\((".*")\),?$', texto, re.M)
    assert linhas, "o cenário não tem os registros em linha própria"
    return [json.loads(json.loads(linha)) for linha in linhas]


def _reescreve_mes(caminho: Path, registros: list[dict]) -> None:
    """Reescreve o bundle com a lista dada, sem passar pelo gerador.

    É assim que a sabotagem tem de ser feita: se o teste chamasse o gerador para
    produzir o arquivo errado, ele estaria medindo o gerador de novo — e a
    independência que este verificador existe para ter iria embora no teste.
    """
    texto = caminho.read_text(encoding="utf-8")
    linhas = [
        "JSON.parse("
        + json.dumps(json.dumps(r, ensure_ascii=False)).replace("<", "\u003c")
        + ")"
        + ("" if i == len(registros) - 1 else ",")
        for i, r in enumerate(registros)
    ]
    antes = texto[: texto.index("    registros: [") + len("    registros: [")]
    depois = texto[texto.index("    ]" + chr(10) + "  };") :]
    caminho.write_text(
        antes + chr(10) + chr(10).join(linhas) + chr(10) + depois, encoding="utf-8"
    )


# ------------------------------------------------------------------ o verde


def test_passa_no_repositorio_real() -> None:
    """PASS contra o repositório de verdade — o piso de que ele funciona."""
    proc = _roda(RAIZ)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS" in proc.stdout


def test_passa_num_repositorio_falso_intacto(tmp_path: Path) -> None:
    """E PASS no cenário intacto — senão as sabotagens não provariam nada.

    Sem este caso, um verificador que reprovasse SEMPRE passaria em todos os
    testes de sabotagem abaixo e pareceria perfeito.
    """
    proc = _roda(_repo_falso(tmp_path))
    assert proc.returncode == 0, proc.stdout + proc.stderr


# ------------------------------------------------- as sete formas de mentira


def test_registro_no_livro_e_fora_dos_artefatos_reprova(tmp_path: Path) -> None:
    """A mentira que o gerador não consegue ver em si mesmo.

    Um bug de varredura que pule um registro produz artefatos internamente
    coerentes: o `--conferir` do gerador compara a saída dele com a
    recomputação dele, com o mesmo bug dos dois lados, e fica verde. Só uma
    fonte externa — o índice do Git — acusa.
    """
    raiz = _repo_falso(tmp_path)
    caminho = _mes(raiz)
    registros = _registros_do_mes(caminho)
    sumido = registros.pop(3)["arquivo"]
    _reescreve_mes(caminho, registros)
    # A contagem declarada é ajustada junto: a sabotagem tem de sobreviver a
    # qualquer conferência por número, senão o teste prova o guarda errado.
    pagina = raiz / "painel" / "painel.html"
    texto = pagina.read_text(encoding="utf-8")
    total = len(registros)
    pagina.write_text(
        re.sub(r'("count":)\d+', rf"\g<1>{total}", texto),
        encoding="utf-8",
    )

    proc = _roda(raiz)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert sumido in proc.stdout
    assert "sumiu da tela" in proc.stdout


def test_registro_inventado_nos_artefatos_reprova(tmp_path: Path) -> None:
    """O contrário: o painel mostrando algo que não existe no livro."""
    raiz = _repo_falso(tmp_path)
    caminho = _mes(raiz)
    registros = _registros_do_mes(caminho)
    fantasma = dict(registros[0])
    fantasma["arquivo"] = "20260899-999-registro-que-nunca-existiu"
    registros.append(fantasma)
    _reescreve_mes(caminho, registros)

    proc = _roda(raiz)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "20260899-999-registro-que-nunca-existiu" in proc.stdout


def test_id_repetido_reprova_mesmo_com_a_contagem_certa(tmp_path: Path) -> None:
    """O caso A B C C que passa por A B C D — cardinalidade não é integridade.

    Um registro sai e outro entra em dobro: a contagem continua exata, e a
    trava antiga (comprimento contra comprimento) ficava verde com um registro
    a menos na tela.
    """
    raiz = _repo_falso(tmp_path)
    caminho = _mes(raiz)
    registros = _registros_do_mes(caminho)
    sumido = registros[5]["arquivo"]
    registros[5] = dict(registros[4])  # duplica o vizinho no lugar dele
    _reescreve_mes(caminho, registros)

    proc = _roda(raiz)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "aparece 2 vezes" in proc.stdout
    assert sumido in proc.stdout


def test_conteudo_alterado_no_empacotamento_reprova(tmp_path: Path) -> None:
    """Id certo, texto errado — o painel contando outra história."""
    raiz = _repo_falso(tmp_path)
    caminho = _mes(raiz)
    registros = _registros_do_mes(caminho)
    alvo = registros[2]["arquivo"]
    registros[2] = dict(registros[2], titulo="um título que o registro nunca teve")
    _reescreve_mes(caminho, registros)

    proc = _roda(raiz)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert alvo in proc.stdout
    assert "difere do arquivo-fonte" in proc.stdout


def test_contagem_declarada_mentirosa_reprova(tmp_path: Path) -> None:
    """A página prometendo mais do que o arquivo do mês entrega."""
    raiz = _repo_falso(tmp_path)
    pagina = raiz / "painel" / "painel.html"
    texto = pagina.read_text(encoding="utf-8")
    pagina.write_text(re.sub(r'("count":)\d+', r"\g<1>9999", texto), encoding="utf-8")

    proc = _roda(raiz)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "9999" in proc.stdout


def test_mes_fantasma_no_disco_reprova(tmp_path: Path) -> None:
    """Arquivo de mês que ninguém reivindica continua sendo servido."""
    raiz = _repo_falso(tmp_path)
    (raiz / "painel" / "livro-201501.js").write_text(
        "// mes que nao existe", encoding="utf-8"
    )

    proc = _roda(raiz)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "livro-201501.js" in proc.stdout


def test_o_livro_inteiro_de_volta_reprova(tmp_path: Path) -> None:
    """`livro.js` de volta = o custo de abrir voltou a crescer, em silêncio.

    O painel continuaria abrindo e funcionando — por isso nenhum teste de tela
    pegaria. É uma regressão de ARQUITETURA, e só um guarda que conheça o
    desenho aposentado consegue vê-la.
    """
    raiz = _repo_falso(tmp_path)
    (raiz / "painel" / "livro.js").write_text("// o desenho antigo", encoding="utf-8")

    proc = _roda(raiz)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "livro.js" in proc.stdout
    assert "aposentado" in proc.stdout


# --------------------------------------------- instrumento quebrado é ERROR


def test_pagina_ausente_e_ERROR_nunca_PASS(tmp_path: Path) -> None:
    """Sem a página não há o que conferir — e isso não é um verde."""
    raiz = _repo_falso(tmp_path)
    (raiz / "painel" / "painel.html").unlink()

    proc = _roda(raiz)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "ERROR" in proc.stdout
    assert "NÃO é um OK" in proc.stdout


def test_livro_fora_do_git_e_ERROR_nunca_PASS(tmp_path: Path) -> None:
    """Registros que o Git não conhece: a fonte independente sumiu.

    Este é o estado mais perigoso de todos — sem a fonte externa, o verificador
    perderia justamente a independência que ele existe para ter. Silenciar aqui
    seria pior do que não existir.
    """
    raiz = _repo_falso(tmp_path)
    subprocess.run(
        ["git", "rm", "-r", "-q", "--cached", "painel/registros"],
        cwd=str(raiz),
        check=True,
        capture_output=True,
        timeout=120,
    )

    proc = _roda(raiz)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "ERROR" in proc.stdout


# ------------------------------------------- o passo 4 da muralha está ligado


@pytest.mark.skipif(
    BASH is None, reason="a muralha do painel precisa de bash utilizável"
)
def test_a_muralha_reprova_pelo_que_SO_o_verificador_enxerga(tmp_path: Path) -> None:
    """Prova que o passo novo da muralha está mesmo ligado — e que ele vê o que
    os outros três não veem.

    A sabotagem é escolhida com cuidado: um registro NOVO no disco e fora do
    índice do Git. Para o gerador está tudo perfeito — ele varre a pasta, acha o
    arquivo, empacota, e o `--conferir` compara a saída dele com a recomputação
    dele e passa. Os passos 1 a 3 da muralha ficam verdes.

    Só a fonte externa acusa: o artefato carrega um id que o Git não conhece, e
    portanto que não vai existir no PR nem na imagem do deploy. É exatamente a
    classe de defeito que o gerador é incapaz de enxergar sobre si mesmo, e é
    para ela que o passo 4 existe.

    Se algum dia alguém desligar o passo 4, este teste fica vermelho.
    """
    raiz = _repo_falso(tmp_path)
    shutil.copy(
        RAIZ / "ci" / "muralha-do-painel.sh", raiz / "ci" / "muralha-do-painel.sh"
    )

    # Um registro que existe no disco e que o Git nunca viu.
    fora_do_git = "20260831-777-registro-que-o-git-nao-conhece"
    (raiz / "painel" / "registros" / f"{fora_do_git}.js").write_text(
        "(function(){ (window.REGISTROS = window.REGISTROS || []).push({"
        f'arquivo: "{fora_do_git}", tipo: "nota", quando: "2026-08-31",'
        'titulo: "t", detalhe: "d", autoridade: "sessao", evidencia: null,'
        "verificado_em: null, precisa_do_dono: false, responde_a: null,"
        'gravidade: "info", frente: null, vence_em_dias: null});})();',
        encoding="utf-8",
    )
    # Regenera: agora os artefatos o incluem, e o gerador está satisfeito.
    gerou = subprocess.run(
        ["node", "painel/gerar_manifesto.js"],
        cwd=str(raiz),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    assert gerou.returncode == 0, gerou.stdout + gerou.stderr

    conferir = subprocess.run(
        ["node", "painel/gerar_manifesto.js", "--conferir"],
        cwd=str(raiz),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    assert conferir.returncode == 0, (
        "o cenário não prova nada se o próprio gerador já reprovar: "
        + conferir.stdout
        + conferir.stderr
    )

    muralha = subprocess.run(
        [BASH, str(raiz / "ci" / "muralha-do-painel.sh")],
        cwd=str(raiz),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    assert muralha.returncode == 1, (
        "a muralha ficou verde com um registro fora do índice do Git — "
        "o passo do verificador não está ligado.\n" + muralha.stdout + muralha.stderr
    )
    assert fora_do_git in muralha.stdout
    assert "Git NÃO o conhece" in muralha.stdout


# ------------------------------------ o Git não junta os gerados sozinho


@pytest.mark.parametrize(
    "caminho",
    ["painel/painel.html", "painel/livro-202608.js", "painel/livro-209912.js"],
)
def test_o_git_nao_tenta_juntar_os_gerados(caminho: str) -> None:
    """`-merge` nos artefatos, medido pelo próprio Git — não pela linha escrita.

    `painel/registros/` é imune a conflito por construção: arquivo novo por
    ocorrência, nunca reescrito. Os gerados destroem essa vantagem — duas sessões
    que registram no mesmo dia reescrevem os mesmos arquivos. Deixado por conta
    do motor de merge de texto, o Git produziria uma junção PLAUSÍVEL e
    semanticamente errada (um registro a mais, um a menos), sem conflito e sem
    ninguém notar — e a trava de contagem do painel compararia dois números
    vindos desse mesmo merge sujo.

    Testado por `git check-attr` e não por `grep` no arquivo: uma linha presente
    com o padrão errado é exatamente a garantia sem mecanismo que esta casa
    persegue. O terceiro caso é um mês que ainda não existe — o padrão precisa
    valer para os meses futuros, não só para os de hoje.
    """
    proc = subprocess.run(
        ["git", "check-attr", "merge", "--", caminho],
        cwd=str(RAIZ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.strip().endswith(": merge: unset"), (
        f"{caminho} não está marcado com `-merge` no .gitattributes — "
        "o Git vai tentar juntar o arquivo gerado sozinho.\n" + proc.stdout
    )


def test_o_livro_de_registros_NAO_esta_marcado(tmp_path: Path) -> None:
    """O contrário também tem de valer, senão o teste acima não prova nada.

    A fonte precisa continuar com merge normal: é ela que faz duas sessões
    paralelas conviverem sem conflito.
    """
    proc = subprocess.run(
        [
            "git",
            "check-attr",
            "merge",
            "--",
            "painel/registros/20260819-001-h3-trava-de-merge-nativa.js",
        ],
        cwd=str(RAIZ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.strip().endswith(": merge: unspecified"), proc.stdout


# ------------------------------------------- o carimbo, que separa duas falhas


def test_carimbos_divergentes_entre_artefatos_reprovam(tmp_path: Path) -> None:
    """Página e mês do MESMO build têm de carregar o mesmo carimbo.

    O carimbo existe para a página conseguir dizer ao dono "estes arquivos são
    de gerações diferentes" em vez de "faltam registros" — são causas distintas
    e mandam procurar em lugares distintos. Mas isso só vale se, num build são,
    eles baterem. Um gerador que carimbasse diferente deixaria a Memória
    permanentemente quebrada, e a tela do dono seria o primeiro lugar a
    descobrir. Aqui não é.
    """
    raiz = _repo_falso(tmp_path)
    caminho = _mes(raiz)
    texto = caminho.read_text(encoding="utf-8")
    caminho.write_text(
        re.sub(r'carimbo: "[a-f0-9]+"', 'carimbo: "000000000000"', texto),
        encoding="utf-8",
    )

    proc = _roda(raiz)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "carimbo" in proc.stdout
    assert "000000000000" in proc.stdout


def test_pagina_sem_carimbo_reprova(tmp_path: Path) -> None:
    """Sem carimbo a página perde a capacidade de distinguir as duas falhas.

    Ela continuaria abrindo e funcionando — por isso nenhum teste de tela
    pegaria. É uma regressão de diagnóstico, silenciosa por natureza.
    """
    raiz = _repo_falso(tmp_path)
    pagina = raiz / "painel" / "painel.html"
    texto = pagina.read_text(encoding="utf-8")
    pagina.write_text(
        texto.replace('carimbo: "', 'carimboAntigo: "', 1), encoding="utf-8"
    )

    proc = _roda(raiz)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "não carrega carimbo" in proc.stdout
