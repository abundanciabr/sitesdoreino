from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
ARQUIVOS_REMOVIDOS = (
    "continuidade.py",
    "continuar-o-trabalho.cmd",
    "ligar-a-vigilia.cmd",
    "desligar-a-vigilia.cmd",
    "prompt-da-continuidade.md",
)


def test_continuidade_local_nao_tem_launcher_reativavel():
    # guarda: ci/tests/test_continuidade_local_removida.py:17
    assert len(ARQUIVOS_REMOVIDOS) == 5
    pasta = RAIZ / "administracao-local"
    presentes = [nome for nome in ARQUIVOS_REMOVIDOS if (pasta / nome).exists()]

    assert presentes == []


def test_administracao_local_nao_chama_claude_nem_radio():
    chamadas_proibidas = ("claude", "ci/radio.py")
    pasta = RAIZ / "administracao-local"
    ocorrencias = []

    for caminho in sorted(pasta.iterdir()):
        if caminho.suffix not in {".cmd", ".md", ".py"}:
            continue
        texto = caminho.read_text(encoding="utf-8").casefold()
        for chamada in chamadas_proibidas:
            if chamada in texto:
                ocorrencias.append(f"{caminho.name}: {chamada}")

    assert ocorrencias == []
