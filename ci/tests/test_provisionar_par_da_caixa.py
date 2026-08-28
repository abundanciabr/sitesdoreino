"""O script que liga a Caixa dentro do Admin, EXECUTADO — não lido.

`infra/provisionar-par-da-caixa.sh` liga o par `admin→sugestoes`
(`docs/decisoes/DECISAO-a-gestao-da-caixa-mora-no-admin.md`) escrevendo três
chaves em dois `env` da VPS. Ele roda **na máquina do mantenedor**, com uma
linha, e um erro ali custa o pior tipo de tempo que este projeto tem: o dele, no
terminal, sem saber o que fazer com a tela — a lição de 24/08/2026, quando um
passo entregue como texto falhou três vezes seguidas com ele.

Por isso este guarda **roda o script de verdade**, contra uma plataforma de
mentira em `tmp_path`, em vez de afirmar coisas sobre o texto dele. É irmão de
`test_provisionar_pares_de_categorias.py` e mede as mesmas promessas, porque são
as mesmas que, quebradas, ele descobre tarde:

1. **Nenhum segredo aparece na tela** (`armadilhas/090`) — o que vai para o
   terminal vai para o print que ele manda para provar que funcionou.
2. **Rodar de novo não rotaciona** — trocar um token em uso dá 401 intermitente,
   o mais caro de diagnosticar daqui.
3. **O par fica igual dos dois lados** — valor diferente é 401 silencioso, e do
   lado de dentro é indistinguível de "esta pessoa não tem acesso".
4. **Recusa fail-closed de verdade**: pasta errada ou `env` faltando param
   **sem escrever nada**, e não com aviso seguido de escrita.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "infra" / "provisionar-par-da-caixa.sh"

CAIXA_URL = "http://sugestoes:8000/interno"

SEMENTES = {
    "sugestoes.env": "DJANGO_SECRET_KEY=x\nDATABASE_URL=postgres://a\n",
    # Sem quebra de linha no fim DE PROPÓSITO: é o caso que gruda a chave nova
    # no fim da última linha, e a última linha de um env é um valor.
    "admin.env": "DJANGO_SECRET_KEY=z\nADMIN_EMAILS=dono@exemplo.com",
}


def _bash() -> str:
    caminho = shutil.which("bash")
    assert caminho, (
        "não achei `bash` nesta máquina. Este guarda EXECUTA o script; sem "
        "interpretador ele não tem o que medir, e isso não é um OK ([INV-CI01])."
    )
    return caminho


def _plataforma(tmp_path: Path, faltando: str | None = None) -> Path:
    raiz = tmp_path / "plataforma"
    (raiz / "env").mkdir(parents=True)
    for nome, conteudo in SEMENTES.items():
        if nome == faltando:
            continue
        (raiz / "env" / nome).write_text(conteudo, encoding="utf-8")
    return raiz


def _rodar(raiz: Path):
    """Roda o script e devolve a saída como TEXTO UTF-8.

    `encoding` explícito: `text=True` sozinho decodifica pelo idioma do sistema
    — em Windows, cp1252 — e estoura na primeira mensagem acentuada do script.
    O env é HERDADO (com `PLATAFORMA_DIR` por cima) porque o script usa
    `openssl`, `stat` e `date`; um PATH inventado mediria a ausência das
    ferramentas, não o script.
    """
    ambiente = dict(os.environ)
    ambiente["PLATAFORMA_DIR"] = str(raiz)
    return subprocess.run(
        [_bash(), str(SCRIPT)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ambiente,
    )


def _valor(raiz: Path, arquivo: str, chave: str) -> str | None:
    texto = (raiz / "env" / arquivo).read_text(encoding="utf-8")
    achado = re.search(rf"^{re.escape(chave)}=(.*)$", texto, re.MULTILINE)
    return achado.group(1).strip() if achado else None


def test_o_script_existe_e_e_executavel_por_bash():
    """[INV-CI01] — sem isto, os testes abaixo passariam medindo o nada."""
    assert SCRIPT.is_file(), SCRIPT
    texto = SCRIPT.read_text(encoding="utf-8")
    assert texto.startswith("#!/usr/bin/env bash"), "faltou o shebang"
    assert (
        "PAROU POR SEGURANÇA" in texto
    ), "o script não fala a língua fail-closed da casa"
    # A linha de UMA LINHA que o mantenedor vai colar tem de estar no cabeçalho:
    # é ela que faz este passo não ser um texto para digitar.
    assert "curl -fsSL" in texto and "provisionar-par-da-caixa.sh" in texto


# ------------------------------------------------------------ o caminho feliz


def test_liga_o_par_e_ele_bate_dos_dois_lados(tmp_path):
    raiz = _plataforma(tmp_path)

    r = _rodar(raiz)

    assert r.returncode == 0, r.stdout + r.stderr
    assert "PRONTO:" in r.stdout, r.stdout
    provedor = _valor(raiz, "sugestoes.env", "TOKENS_ACEITOS_ADMIN")
    consumidor = _valor(raiz, "admin.env", "SUGESTOES_API_TOKEN")
    assert provedor and provedor == consumidor, "o par não bate — daria 401 silencioso"
    assert len(provedor) >= 32, f"o token nasceu curto demais: {len(provedor)}"
    assert _valor(raiz, "admin.env", "SUGESTOES_API_URL") == CAIXA_URL


def test_a_chave_nova_nao_gruda_na_ultima_linha_de_um_env_sem_quebra(tmp_path):
    """`admin.env` da semente termina SEM quebra de linha — o caso que gruda."""
    raiz = _plataforma(tmp_path)

    _rodar(raiz)

    assert _valor(raiz, "admin.env", "ADMIN_EMAILS") == "dono@exemplo.com"
    assert _valor(raiz, "admin.env", "SUGESTOES_API_TOKEN")


def test_nenhum_segredo_aparece_na_tela(tmp_path):
    """A `armadilhas/090` medida pelo resultado, e não pela leitura do código."""
    raiz = _plataforma(tmp_path)

    r = _rodar(raiz)

    gravado = _valor(raiz, "sugestoes.env", "TOKENS_ACEITOS_ADMIN")
    assert gravado
    assert gravado not in r.stdout, "o token gravado VAZOU para a tela"
    assert gravado not in r.stderr, "o token gravado VAZOU para o stderr"


def test_rodar_de_novo_nao_rotaciona_nada(tmp_path):
    """Trocar um token em uso derruba as chamadas até o outro lado reiniciar."""
    raiz = _plataforma(tmp_path)
    _rodar(raiz)
    antes = _valor(raiz, "sugestoes.env", "TOKENS_ACEITOS_ADMIN")

    segunda = _rodar(raiz)

    assert segunda.returncode == 0, segunda.stdout + segunda.stderr
    assert _valor(raiz, "sugestoes.env", "TOKENS_ACEITOS_ADMIN") == antes
    assert _valor(raiz, "admin.env", "SUGESTOES_API_TOKEN") == antes
    assert "já estava tudo ligado" in segunda.stdout


def test_nenhuma_chave_fica_repetida(tmp_path):
    """Chave repetida: o Compose usa a ÚLTIMA, e o valor velho fica por baixo."""
    raiz = _plataforma(tmp_path)
    _rodar(raiz)
    _rodar(raiz)

    for arquivo, chave in (
        ("sugestoes.env", "TOKENS_ACEITOS_ADMIN"),
        ("admin.env", "SUGESTOES_API_TOKEN"),
        ("admin.env", "SUGESTOES_API_URL"),
    ):
        texto = (raiz / "env" / arquivo).read_text(encoding="utf-8")
        assert (
            len(re.findall(rf"^{chave}=", texto, re.MULTILINE)) == 1
        ), f"{chave} aparece mais de uma vez em {arquivo}"


def test_o_par_dessincronizado_a_mao_e_curado_pelo_provedor(tmp_path):
    """Alguém edita um lado; rodar de novo cura, e o PROVEDOR é quem manda."""
    raiz = _plataforma(tmp_path)
    _rodar(raiz)
    do_provedor = _valor(raiz, "sugestoes.env", "TOKENS_ACEITOS_ADMIN")
    admin = raiz / "env" / "admin.env"
    admin.write_text(
        admin.read_text(encoding="utf-8").replace(do_provedor, "valor-errado"),
        encoding="utf-8",
    )

    r = _rodar(raiz)

    assert r.returncode == 0, r.stdout + r.stderr
    assert _valor(raiz, "admin.env", "SUGESTOES_API_TOKEN") == do_provedor


# ------------------------------------------------------------ as recusas


def test_pasta_errada_para_sem_escrever(tmp_path):
    r = _rodar(tmp_path / "nao-existe")

    assert r.returncode != 0
    assert "PAROU POR SEGURANÇA" in r.stdout


@pytest.mark.parametrize("faltando", ["sugestoes.env", "admin.env"])
def test_env_faltando_para_e_nao_toca_no_outro(tmp_path, faltando):
    """Fail-closed de verdade: nada é escrito quando um dos lados não existe."""
    raiz = _plataforma(tmp_path, faltando=faltando)
    sobrou = [nome for nome in SEMENTES if nome != faltando][0]
    antes = (raiz / "env" / sobrou).read_text(encoding="utf-8")

    r = _rodar(raiz)

    assert r.returncode != 0
    assert "PAROU POR SEGURANÇA" in r.stdout
    assert (raiz / "env" / sobrou).read_text(encoding="utf-8") == antes


def test_carregado_com_source_recusa_em_vez_de_derrubar_a_sessao():
    """O modo de falha de 24/08: `set -e`/`exit` num shell carregado com `.`
    derruba a sessão interativa do mantenedor. Aconteceu, três vezes."""
    ambiente = dict(os.environ)
    ambiente["PLATAFORMA_DIR"] = "/tmp/nao-existe-mesmo"
    r = subprocess.run(
        [_bash(), "-c", f'. "{SCRIPT}"; echo SOBREVIVI'],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ambiente,
    )

    assert "PAROU POR SEGURANÇA" in r.stdout
    assert (
        "SOBREVIVI" in r.stdout
    ), "o `return` não protegeu a sessão de quem deu source"


def test_o_provedor_e_escrito_antes_do_consumidor():
    """A ordem inversa tem janela ruim: token que o provedor ainda não aceita.

    Medido no TEXTO de propósito — é uma propriedade da ordem das linhas, e
    encená-la exigiria interromper o script no meio, que é um teste mais frágil
    do que a coisa que ele mediria.
    """
    texto = SCRIPT.read_text(encoding="utf-8")
    provedor = texto.index('garantir "$ENV_SUGESTOES" TOKENS_ACEITOS_ADMIN')
    consumidor = texto.index('garantir "$ENV_ADMIN" SUGESTOES_API_TOKEN')

    assert provedor < consumidor
