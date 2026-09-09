"""Guarda o mesmo nome de configuração entre quem lê e quem escreve."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
NOMES_ADMIN = {"ADMIN_API_URL", "ADMIN_API_TOKEN"}
NOME_TOKEN_PROVEDOR = "TOKENS_ACEITOS_PAGES"


def _fontes() -> dict[str, str]:
    caminhos = {
        "clientes": "services/pages/apps/core/clients.py",
        "paginas": "infra/provisionar-pages.sh",
        "par": "infra/provisionar-par-do-portfolio-com-a-admin.sh",
        "molde_paginas": "infra/env/pages.env.exemplo",
        "admin": "infra/provisionar-admin.sh",
        "molde_admin": "infra/env/admin.env.exemplo",
        "config_admin": "services/admin/config/settings.py",
    }
    fontes = {}
    for nome, relativo in caminhos.items():
        caminho = RAIZ / relativo
        assert caminho.is_file(), f"não achei o arquivo necessário: {relativo}"
        fontes[nome] = caminho.read_text(encoding="utf-8")
    return fontes


def _nomes_lidos_pelo_admin(fonte: str) -> set[str]:
    bloco = re.search(
        r"^class AdminClient:.*?(?=^class |\Z)", fonte, flags=re.MULTILINE | re.DOTALL
    )
    assert bloco, "AdminClient não foi encontrado em clients.py"
    nomes = set(re.findall(r'exigir\("([A-Z_][A-Z0-9_]*)"\)', bloco.group(0)))
    assert nomes, "AdminClient não tem nenhuma chamada exigir() para medir"
    assert nomes == NOMES_ADMIN, f"nomes lidos mudaram sem atualizar o guarda: {nomes}"
    return nomes


def _chaves_do_roteiro(fonte: str) -> set[str]:
    achados = re.findall(r'CHAVES_QUE_EU_GERO="([^"]+)"', fonte)
    assert len(achados) == 1, "o roteiro não tem exatamente uma CHAVES_QUE_EU_GERO"
    return set(achados[0].split())


def _heredoc_de_paginas(fonte: str) -> str:
    achado = re.search(
        r"^cat > env/pages\.env <<ENV\n(.*?)^ENV$", fonte, flags=re.MULTILINE | re.DOTALL
    )
    assert achado, "o heredoc de env/pages.env não foi encontrado"
    return achado.group(1)


def _chave_no_heredoc(fonte: str, chave: str) -> bool:
    return bool(re.search(rf"^{re.escape(chave)}=", fonte, flags=re.MULTILINE))


def _garantir_no_par(fonte: str, chave: str, arquivo: str) -> bool:
    return bool(
        re.search(
            rf'garantir\s+"\$ENV_{arquivo}"\s+{re.escape(chave)}\s+',
            fonte,
        )
    )


def _verificar_nomes(fontes: dict[str, str]) -> None:
    nomes = _nomes_lidos_pelo_admin(fontes["clientes"])
    chaves_paginas = _chaves_do_roteiro(fontes["paginas"])
    heredoc_paginas = _heredoc_de_paginas(fontes["paginas"])

    for nome in nomes:
        assert nome in chaves_paginas, f"{nome} não está na CHAVES_QUE_EU_GERO de pages"
        assert _chave_no_heredoc(heredoc_paginas, nome), (
            f"{nome} não está no heredoc de pages"
        )
        assert _garantir_no_par(fontes["par"], nome, "PAGES"), (
            f"{nome} não é escrito pelo roteiro do par pages->admin"
        )
        assert _chave_no_heredoc(fontes["molde_paginas"], nome), (
            f"{nome} não está no molde de pages"
        )

    assert NOME_TOKEN_PROVEDOR in _chaves_do_roteiro(fontes["admin"]), (
        "TOKENS_ACEITOS_PAGES não está na lista do roteiro de admin"
    )
    assert _garantir_no_par(
        fontes["par"], NOME_TOKEN_PROVEDOR, "ADMIN"
    ), "TOKENS_ACEITOS_PAGES não é escrito no env da admin pelo roteiro do par"
    assert _chave_no_heredoc(fontes["molde_admin"], NOME_TOKEN_PROVEDOR), (
        "TOKENS_ACEITOS_PAGES não está no molde de admin"
    )
    assert 'chave.startswith("TOKENS_ACEITOS_")' in fontes["config_admin"], (
        "settings.py não reconhece o prefixo dos tokens aceitos"
    )


def test_nomes_do_par_pages_admin_sao_iguais_em_todas_as_casas():
    """O consumidor e os quatro escritores devem usar as mesmas chaves."""
    _verificar_nomes(_fontes())


def test_o_guarda_morde_a_mutacao_do_nome_em_cada_casa():
    fontes = _fontes()
    _verificar_nomes(fontes)
    mutacoes = (
        (
            "clientes",
            'exigir("ADMIN_API_TOKEN")',
            'exigir("ADMIN_API_TOKEN_VELHO")',
        ),
        (
            "paginas",
            "ADMIN_API_TOKEN=$T_ADMIN",
            "ADMIN_API_TOKEN_VELHO=$T_ADMIN",
        ),
        (
            "par",
            'garantir "$ENV_PAGES" ADMIN_API_TOKEN ',
            'garantir "$ENV_PAGES" ADMIN_API_TOKEN_VELHO ',
        ),
        (
            "molde_paginas",
            "ADMIN_API_TOKEN=",
            "ADMIN_API_TOKEN_VELHO=",
        ),
        (
            "admin",
            "TOKENS_ACEITOS_PAGES\"",
            "TOKENS_ACEITOS_PAGES_VELHO\"",
        ),
    )
    for arquivo, antigo, novo in mutacoes:
        sabotadas = dict(fontes)
        sabotadas[arquivo] = fontes[arquivo].replace(antigo, novo, 1)
        assert sabotadas[arquivo] != fontes[arquivo], f"mutação não atingiu {arquivo}"
        with pytest.raises(AssertionError):
            _verificar_nomes(sabotadas)
