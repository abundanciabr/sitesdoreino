"""O SQL DA BUSCA SEM ACENTO MORA EM DOIS LUGARES — e este guarda os obriga a concordar.

O FATO (TAR-047, 30/08/2026)
----------------------------
A configuração de busca que ignora acento (`armadilhas/154`) é criada por um SQL
que existe em DUAS cópias, e as duas se declaram cópia uma da outra:

    services/forum/apps/forum/config_de_busca.py   (`SQL_DA_CURA`, a fonte)
    infra/provisionar-forum.sh                     (o heredoc `SQL_DA_BUSCA`)

A duplicação tem motivo real: o script de provisionamento roda COLADO numa VPS
que não tem o repositório, então não pode ler o arquivo da célula. Mas a lei
anti-duplicação do `CLAUDE.md` não aceita fato em dois lugares sem mecanismo, e
o preço de divergirem é alto: o script criaria no banco uma configuração com
nome ou definição diferente da que o código espera, e o fórum quebraria em TODA
escrita e TODA busca, com o deploy verde.

POR QUE ESTE GUARDA MORA EM `ci/tests/`, E NÃO NA SUÍTE DO FÓRUM
----------------------------------------------------------------
A constituição da célula (`constituicoes/AGENTS.forum.md`, Fronteiras) proíbe o
fórum até de LER `infra/`. Quem pode olhar os dois lados ao mesmo tempo é a CI
da raiz, e é ela que roda este arquivo (`python ci/ci.py --apenas testador`).

O QUE ELE COMPARA
-----------------
1. O SQL da cura, normalizando só espaço em branco (quebra de linha e indentação
   são livres; palavra, ordem e pontuação, não).
2. O NOME da configuração que o script grava no env (`BUSCA_CONFIG=...`) contra
   o `CONFIG_SEM_ACENTO` do código: é esse nome que o env liga, e é o contrato
   entre os dois lados.

FAIL-CLOSED ([INV-CI01]): arquivo ausente, heredoc não encontrado ou SQL vazio
REPROVAM. "Não consegui olhar" nunca é "está igual".

E o guarda tem dentes provados aqui mesmo (`armadilhas/132`): há um teste que
fabrica a divergência em memória e exige o vermelho.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[2]

A_FONTE = "services/forum/apps/forum/config_de_busca.py"
A_COPIA = "infra/provisionar-forum.sh"

# O heredoc do script: `<<'SQL_DA_BUSCA'` ... linha só com `SQL_DA_BUSCA`.
RE_HEREDOC = re.compile(
    r"<<'?(SQL_DA_BUSCA)'?\n(?P<corpo>.*?)^\1$", re.DOTALL | re.MULTILINE
)
# O nome que o script grava no env quando a cura deu certo.
RE_BUSCA_CONFIG = re.compile(r'^\s*BUSCA_CONFIG="([^"]+)"\s*$', re.MULTILINE)


def normalizar(sql: str) -> str:
    """Espaço em branco é livre; tudo o mais conta."""
    return " ".join(sql.split())


def _texto(caminho: str) -> str:
    alvo = RAIZ / caminho
    assert alvo.is_file(), (
        f"{caminho} não existe. Este guarda não tem o que medir, e isso não é "
        "um OK ([INV-CI01])."
    )
    conteudo = alvo.read_text(encoding="utf-8")
    assert conteudo.strip(), f"{caminho} está vazio."
    return conteudo


def carregar_a_fonte(caminho: Path) -> ModuleType:
    """Importa `config_de_busca.py` pelo caminho, sem Django nem `sys.path`.

    O módulo só importa `os`, de propósito (é lido no boot da célula). Importar
    de verdade, em vez de raspar o texto, é o que faz o f-string de
    `SQL_DA_CURA` chegar aqui já resolvido: comparar o texto cru do arquivo
    compararia `{CONFIG_SEM_ACENTO}` com `portugues_sem_acento`, e o guarda
    reprovaria sempre ou, pior, alguém o afrouxaria até passar.
    """
    spec = importlib.util.spec_from_file_location("config_de_busca_sob_guarda", caminho)
    assert spec and spec.loader, f"não consegui montar o módulo a partir de {caminho}"
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def sql_da_copia(fonte_do_script: str, script: str = A_COPIA) -> str:
    achado = RE_HEREDOC.search(fonte_do_script)
    assert achado, (
        f"não achei o heredoc `<<'SQL_DA_BUSCA' … SQL_DA_BUSCA` em {script}. Se a "
        "forma de rodar o SQL mudou, este guarda precisa aprender a nova; não o "
        "apague, ensine-o."
    )
    corpo = achado.group("corpo")
    assert corpo.strip(), f"o heredoc SQL_DA_BUSCA de {script} está vazio."
    return corpo


def nome_gravado_no_env(fonte_do_script: str, script: str = A_COPIA) -> str:
    achado = RE_BUSCA_CONFIG.search(fonte_do_script)
    assert achado, (
        f"não achei `BUSCA_CONFIG=\"…\"` em {script}: é essa linha que liga a cura "
        "no env da célula. Sem ela o SQL roda e ninguém passa a usá-lo."
    )
    return achado.group(1)


# ---------------------------------------------------------------------------
# 1. Os dois lados reais concordam.
# ---------------------------------------------------------------------------
def test_o_sql_da_cura_e_o_mesmo_nos_dois_lugares() -> None:
    fonte = carregar_a_fonte(RAIZ / A_FONTE)
    assert normalizar(fonte.SQL_DA_CURA), f"`SQL_DA_CURA` de {A_FONTE} está vazio."
    copia = sql_da_copia(_texto(A_COPIA))
    assert normalizar(fonte.SQL_DA_CURA) == normalizar(copia), (
        "O SQL da busca sem acento DIVERGIU entre a fonte e a cópia.\n"
        f"  fonte ({A_FONTE}):\n    {normalizar(fonte.SQL_DA_CURA)}\n"
        f"  cópia ({A_COPIA}):\n    {normalizar(copia)}\n"
        "Os dois têm de mudar na MESMA edição: o script cria no banco o que o "
        "código espera encontrar, e o fórum quebra em toda busca se discordarem."
    )


def test_o_nome_que_o_script_grava_no_env_e_o_que_o_codigo_espera() -> None:
    fonte = carregar_a_fonte(RAIZ / A_FONTE)
    gravado = nome_gravado_no_env(_texto(A_COPIA))
    assert gravado == fonte.CONFIG_SEM_ACENTO, (
        f"{A_COPIA} grava FORUM_BUSCA_CONFIG={gravado!r}, mas o código espera "
        f"{fonte.CONFIG_SEM_ACENTO!r} ({A_FONTE}). O env ligaria uma configuração "
        "que não existe no banco."
    )
    assert fonte.CONFIG_SEM_ACENTO in normalizar(fonte.SQL_DA_CURA), (
        "o SQL da fonte não cria a configuração que o próprio código nomeia."
    )


# ---------------------------------------------------------------------------
# 2. O guarda tem dentes (armadilhas/132): a divergência fabricada fica vermelha.
# ---------------------------------------------------------------------------
_SCRIPT_FALSO = """\
if psql_super -d forum_db -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<'SQL_DA_BUSCA'
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE TEXT SEARCH CONFIGURATION {nome} (COPY = portuguese);
SQL_DA_BUSCA
then
  BUSCA_CONFIG="{nome}"
fi
"""


def test_o_guarda_reprova_quando_so_um_lado_muda() -> None:
    fonte = carregar_a_fonte(RAIZ / A_FONTE)
    sabotado = _SCRIPT_FALSO.format(nome=fonte.CONFIG_SEM_ACENTO)
    assert normalizar(sql_da_copia(sabotado, "falso.sh")) != normalizar(fonte.SQL_DA_CURA)


def test_o_guarda_reprova_quando_so_o_nome_do_env_muda() -> None:
    fonte = carregar_a_fonte(RAIZ / A_FONTE)
    sabotado = _SCRIPT_FALSO.format(nome=fonte.CONFIG_SEM_ACENTO + "s")
    assert nome_gravado_no_env(sabotado, "falso.sh") != fonte.CONFIG_SEM_ACENTO


def test_normalizar_perdoa_so_espaco_em_branco() -> None:
    assert normalizar("A  B\n  C\tD") == normalizar("A B C D")
    assert normalizar("A B;") != normalizar("A B")
    assert normalizar("portugues_sem_acento") != normalizar("portugues_sem_acentos")


def test_fail_closed_sem_heredoc() -> None:
    with pytest.raises(AssertionError, match="não achei o heredoc"):
        sql_da_copia("echo sem sql nenhum\n", "falso.sh")
    with pytest.raises(AssertionError, match="BUSCA_CONFIG"):
        nome_gravado_no_env("echo nada\n", "falso.sh")
