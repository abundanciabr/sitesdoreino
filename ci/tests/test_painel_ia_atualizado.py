"""GUARDA — o mapa para IA (`painel/ia/`) não pode ficar cego a uma célula nova.

[padrão 2, RETROSPECTIVA-FASE-D] Uma garantia escrita em prosa ("mantenha
isto atualizado") sem mecanismo que a imponha apodrece — é exatamente a
forma como o `ARMADILHAS.md` monolítico e os painéis antigos (`arquivos/
painel-*.html`) ficaram desatualizados sem que ninguém percebesse a tempo.

Este teste não prova que `painel/ia/` está completo ou correto — só que a
lista de células que `services/` tem de verdade continua citada em algum
documento do mapa. É a forma mais barata de detecção: célula nova nasce,
ninguém lembra de atualizar `04-arquitetura-de-celulas-e-contratos.md`, o
mapa mente por omissão para a próxima IA que o ler.
"""

from __future__ import annotations

from pathlib import Path

CI = Path(__file__).resolve().parents[1]
RAIZ = CI.parent
SERVICES = RAIZ / "services"
PAINEL_IA = RAIZ / "painel" / "ia"


def _texto_do_mapa() -> str:
    return "\n".join(
        arquivo.read_text(encoding="utf-8") for arquivo in sorted(PAINEL_IA.glob("*.md"))
    )


def test_toda_celula_de_services_aparece_no_mapa_para_ia() -> None:
    celulas = sorted(p.name for p in SERVICES.iterdir() if p.is_dir())
    assert celulas, f"nenhuma célula encontrada em {SERVICES} — o próprio teste está cego"

    texto = _texto_do_mapa()
    faltando = [c for c in celulas if c not in texto]
    assert not faltando, (
        f"célula(s) ausente(s) do mapa painel/ia/: {', '.join(faltando)}\n"
        "Atualize painel/ia/04-arquitetura-de-celulas-e-contratos.md (e o "
        "INDICE.md, se a célula merecer nota própria) no mesmo PR que criou "
        "a célula."
    )


def test_indice_lista_todos_os_documentos_do_mapa() -> None:
    indice = (PAINEL_IA / "INDICE.md").read_text(encoding="utf-8")
    documentos = sorted(
        p.name for p in PAINEL_IA.glob("*.md") if p.name != "INDICE.md"
    )
    faltando = [nome for nome in documentos if nome not in indice]
    assert not faltando, (
        f"documento(s) ausente(s) da tabela em painel/ia/INDICE.md: {', '.join(faltando)}\n"
        "Todo documento novo em painel/ia/ precisa de uma linha no índice — "
        "senão vira leitura que ninguém sabe que existe."
    )
