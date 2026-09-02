"""O script que LIGA a IA do fórum, EXECUTADO — não lido.

`infra/por-a-chave-da-ia-do-forum.sh` guarda a chave da Anthropic no
`env/forum.env` da VPS e recarrega a célula. Ele roda **na máquina do
mantenedor**, com uma linha, e um erro ali custa o pior tipo de tempo que este
projeto tem: o dele, no terminal, sem saber o que fazer com a tela.

Por isso este guarda **roda o script de verdade**, contra uma plataforma de
mentira em `tmp_path`, em vez de afirmar coisas sobre o texto dele. É irmão de
`test_provisionar_par_da_economia.py` e mede seis promessas:

1. **A chave NUNCA aparece na tela** (`armadilhas/090`). É a promessa que dá nome
   ao script: ela é PERGUNTADA com digitação invisível, e não passada como
   argumento — argumento aparece na tela, fica no histórico do shell, é lido pelo
   `ps aux` de qualquer processo, e vai junto no print que o mantenedor manda ao
   agente para provar que funcionou. Foi assim que o segredo do OAuth do Google
   vazou em 24/08/2026.
2. **Recusa fail-closed ANTES de perguntar.** Sem `env/forum.env`, ele para sem
   ter pedido segredo nenhum: descobrir depois faria o mantenedor colar uma chave
   à toa, e chave colada à toa é como uma chave acaba num lugar errado.
3. **Chave estranha é recusada e NADA é escrito.**
4. **Rodar de novo TROCA, nunca duplica.** É como se troca uma chave revogada, e
   duas linhas `ANTHROPIC_API_KEY=` no mesmo env fazem o valor depender da ordem
   de leitura.
5. **O resto do env sobrevive inteiro** (`armadilhas/111`).
6. **Env sem quebra de linha no fim não gruda a chave no último valor** — o caso
   que o `garantir()` do provisionamento também trata, e pelo mesmo motivo.

[INV-CI01]: sem `bash` nesta máquina o guarda não tem o que medir, e isso é
ERRO, nunca um OK silencioso.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "infra" / "por-a-chave-da-ia-do-forum.sh"

# Uma chave de mentira com a FORMA da real: prefixo certo e comprimento acima do
# mínimo que o script exige. Ela é o que os testes procuram na tela.
CHAVE = "sk-ant-api03-" + "N0tAr3alK3y" * 6

# O env do fórum como o provisionamento o escreve, com a linha da chave VAZIA.
FORUM_ENV = (
    "DJANGO_SECRET_KEY=x\n"
    "DATABASE_URL=postgres://forum_user:senha@postgres:5432/forum_db\n"
    "SCRIPT_NAME=/forum\n"
    "ADMIN_EMAILS=dono@exemplo.com\n"
    "FORUM_BUSCA_CONFIG=portugues_sem_acento\n"
    "ANTHROPIC_API_KEY=\n"
)


def _bash() -> str:
    caminho = shutil.which("bash")
    assert caminho, (
        "não achei `bash` nesta máquina. Este guarda EXECUTA o script; sem "
        "interpretador ele não tem o que medir, e isso não é um OK ([INV-CI01])."
    )
    return caminho


def _plataforma(tmp_path: Path, *, forum_env: str | None = FORUM_ENV) -> Path:
    """Uma /opt/plataforma de mentira. `forum_env=None` = célula não provisionada."""
    raiz = tmp_path / "plataforma"
    (raiz / "env").mkdir(parents=True)
    (raiz / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    # A referência de dono e permissão que o script copia.
    (raiz / "env" / "alunos.env").write_text("DJANGO_SECRET_KEY=y\n", encoding="utf-8")
    if forum_env is not None:
        (raiz / "env" / "forum.env").write_text(forum_env, encoding="utf-8")
    return raiz


def _rodar(raiz: Path, digitado: str) -> subprocess.CompletedProcess:
    """Roda o script com `digitado` chegando pelo teclado (a pergunta invisível).

    A plataforma de mentira não tem serviço `forum` no compose, e isso é de
    propósito: o script tem um caminho declarado para quando não há o que
    recarregar (grava o arquivo, avisa que não recarregou, e sai com 0). É o
    mesmo caminho que rodaria numa VPS onde o docker mudou de nome, e ele
    precisa ser o caminho testado. Assim o guarda não depende de haver docker
    na máquina que roda a suíte.
    """
    ambiente = dict(os.environ, PLATAFORMA_DIR=str(raiz))
    return subprocess.run(
        [_bash(), str(SCRIPT)],
        input=digitado,
        capture_output=True,
        text=True,
        # O script fala PORTUGUÊS, com acento e com o "PAROU POR SEGURANÇA".
        # Sem dizer o encoding aqui, o Python de uma máquina Windows tenta
        # cp1252 e a leitura da tela estoura antes de qualquer asserção.
        encoding="utf-8",
        errors="replace",
        env=ambiente,
    )


def _valor(raiz: Path, chave: str) -> str | None:
    for linha in (raiz / "env" / "forum.env").read_text(encoding="utf-8").splitlines():
        if linha.startswith(chave + "="):
            return linha.split("=", 1)[1]
    return None


def _linhas_da_chave(raiz: Path) -> int:
    texto = (raiz / "env" / "forum.env").read_text(encoding="utf-8")
    return sum(1 for x in texto.splitlines() if x.startswith("ANTHROPIC_API_KEY="))


# ---------------------------------------------------------------------------
# 1. A PROMESSA QUE DÁ NOME AO SCRIPT
# ---------------------------------------------------------------------------


def test_a_chave_nunca_aparece_na_tela(tmp_path):
    raiz = _plataforma(tmp_path)
    r = _rodar(raiz, CHAVE + "\n")

    tela = r.stdout + r.stderr
    assert CHAVE not in tela, (
        "a chave apareceu na tela. É exatamente por esse caminho que o segredo "
        "do OAuth vazou em 24/08/2026 (`armadilhas/090`): o mantenedor manda o "
        "print para provar que funcionou."
    )
    # E nem um pedaço dela: metade de uma chave ainda é meia chave vazada.
    assert CHAVE[:20] not in tela
    # Mas o script FALA: silêncio total seria indistinguível de travado.
    assert "caracteres" in tela
    assert _valor(raiz, "ANTHROPIC_API_KEY") == CHAVE


# ---------------------------------------------------------------------------
# 2. FAIL-CLOSED, E ANTES DE PEDIR O SEGREDO
# ---------------------------------------------------------------------------


def test_sem_o_env_do_forum_ele_para_sem_pedir_a_chave(tmp_path):
    raiz = _plataforma(tmp_path, forum_env=None)
    r = _rodar(raiz, CHAVE + "\n")

    assert r.returncode != 0
    assert "PAROU POR SEGURANÇA" in (r.stdout + r.stderr)
    # A ordem importa: ele não pode ter pedido a chave antes de descobrir.
    assert "Cole a chave" not in r.stdout
    assert not (raiz / "env" / "forum.env").exists()


def test_sem_a_plataforma_ele_para(tmp_path):
    r = _rodar(tmp_path / "lugar-nenhum", CHAVE + "\n")
    assert r.returncode != 0
    assert "PAROU POR SEGURANÇA" in (r.stdout + r.stderr)


@pytest.mark.parametrize(
    "digitado,porque",
    [
        ("", "vazio: o mantenedor apertou Enter sem colar"),
        ("   \n", "só espaço"),
        ("minha-chave\n", "não tem o prefixo sk-ant-"),
        ("sk-ant-curta\n", "veio pela metade"),
        ("sk-ant-" + "a" * 40 + " com espaço no meio\n", "colou junto com outra coisa"),
    ],
)
def test_chave_estranha_e_recusada_e_nada_e_escrito(tmp_path, digitado, porque):
    raiz = _plataforma(tmp_path)
    antes = (raiz / "env" / "forum.env").read_text(encoding="utf-8")

    r = _rodar(raiz, digitado)

    assert r.returncode != 0, porque
    assert "PAROU POR SEGURANÇA" in (r.stdout + r.stderr)
    assert (raiz / "env" / "forum.env").read_text(encoding="utf-8") == antes, (
        "recusou e mesmo assim mexeu no arquivo: " + porque
    )


# ---------------------------------------------------------------------------
# 3. TROCAR A CHAVE É O CASO NORMAL, NÃO O EXCEPCIONAL
# ---------------------------------------------------------------------------


def test_rodar_de_novo_troca_a_chave_e_nao_duplica_a_linha(tmp_path):
    """É como se troca uma chave revogada. Duas linhas fariam o valor depender
    da ordem em que alguém lê o arquivo."""
    raiz = _plataforma(tmp_path)
    outra = "sk-ant-api03-" + "S3gundaCh4v3" * 5

    assert _rodar(raiz, CHAVE + "\n").returncode == 0
    assert _rodar(raiz, outra + "\n").returncode == 0

    assert _linhas_da_chave(raiz) == 1
    assert _valor(raiz, "ANTHROPIC_API_KEY") == outra


def test_o_resto_do_env_sobrevive_inteiro(tmp_path):
    """`armadilhas/111`: variável que some do env é falha silenciosa com deploy
    verde. Este script edita UMA linha e não pode encostar nas outras."""
    raiz = _plataforma(tmp_path)

    assert _rodar(raiz, CHAVE + "\n").returncode == 0

    assert _valor(raiz, "DJANGO_SECRET_KEY") == "x"
    assert _valor(raiz, "SCRIPT_NAME") == "/forum"
    assert _valor(raiz, "ADMIN_EMAILS") == "dono@exemplo.com"
    assert _valor(raiz, "FORUM_BUSCA_CONFIG") == "portugues_sem_acento"
    assert _valor(raiz, "DATABASE_URL", ) == (
        "postgres://forum_user:senha@postgres:5432/forum_db"
    )


def test_env_sem_quebra_de_linha_no_fim_nao_gruda_a_chave_no_ultimo_valor(tmp_path):
    """O caso que o `garantir()` do provisionamento também trata: a última linha
    de um env é um VALOR, e um `>>` sem a quebra o corromperia em silêncio."""
    # Sem a linha da chave (o env de antes desta entrega) e sem `\n` no fim.
    raiz = _plataforma(
        tmp_path,
        forum_env="DJANGO_SECRET_KEY=x\nADMIN_EMAILS=dono@exemplo.com",
    )

    assert _rodar(raiz, CHAVE + "\n").returncode == 0

    assert _valor(raiz, "ADMIN_EMAILS") == "dono@exemplo.com"
    assert _valor(raiz, "ANTHROPIC_API_KEY") == CHAVE
    assert _linhas_da_chave(raiz) == 1


# ---------------------------------------------------------------------------
# 4. O QUE O SCRIPT PROMETE POR ESCRITO, ele cumpre no texto
# ---------------------------------------------------------------------------


def test_ele_pergunta_em_vez_de_aceitar_a_chave_como_argumento():
    """A leitura invisível é a peça, e um `read` sem `-s` a desfaz sem quebrar nada.

    Este é o único caso deste arquivo que lê o texto em vez de executar, e a
    razão é que o defeito é INVISÍVEL na execução: um `read` sem `-s` funciona
    perfeitamente, grava a chave certa, e só vaza quando há uma pessoa olhando a
    tela. Nenhuma asserção sobre o resultado o pegaria.
    """
    fonte = SCRIPT.read_text(encoding="utf-8")
    assert "read -r -s CHAVE" in fonte, (
        "o script deixou de perguntar a chave com digitação invisível "
        "(`read -r -s`). Sem o `-s` ela é ecoada na tela do mantenedor."
    )
    assert 'bash script.sh "' not in fonte
