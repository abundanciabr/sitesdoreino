"""O script que liga o aviso no celular, EXECUTADO — não lido.

`infra/provisionar-aviso-no-celular.sh` gera a chave VAPID dentro da VPS e a
escreve nos `env` de duas células. Ele roda **na máquina do mantenedor**, com
uma linha, e um erro ali custa o pior tipo de tempo que este projeto tem: o
dele, no terminal, sem saber o que fazer com a tela.

Por isso este guarda **roda o script de verdade**, contra uma plataforma de
mentira em `tmp_path`. As quatro promessas medidas são as quatro que, quebradas,
o mantenedor descobre tarde:

1. **A metade privada nunca aparece na tela.** É a `armadilhas/090`: o que vai
   para o terminal vai para o histórico do shell, para o `ps aux` e — o caminho
   que mais pega — para o print que ele manda para provar que funcionou.

2. **Rodar de novo NÃO gera outra chave.** Aqui isto é mais grave que nos
   scripts irmãos: uma chave nova invalida, de uma vez, todo aparelho já
   inscrito. Cada um pararia de receber aviso em silêncio, e só voltaria se a
   pessoa desinstalasse e instalasse o app de novo.

3. **As duas metades são do MESMO par, nos dois arquivos.** Metades trocadas
   fazem o navegador recusar a inscrição num erro que só aparece no celular da
   pessoa — deste lado, tudo pareceria certo.

4. **O que ele escreve é uma chave VÁLIDA.** O teste deriva a metade pública a
   partir da privada gravada e compara com a que foi escrita: é a diferença
   entre "escreveu duas linhas" e "escreveu um par que funciona".

E os caminhos de recusa: pasta errada e `env` faltando. Em todos, o script tem
de parar sem escrever nada — fail-closed de verdade, não aviso seguido de
escrita.
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "infra" / "provisionar-aviso-no-celular.sh"

SEMENTES = {
    "notificacoes.env": "DJANGO_SECRET_KEY=x\nDATABASE_URL=postgres://a\n",
    # Sem quebra de linha no fim DE PROPÓSITO: é o caso que grudaria a chave
    # nova no fim da última linha, e a última linha de um env é um valor.
    "funil.env": "DJANGO_SECRET_KEY=y\nIDENTIDADE_API_TOKEN=tok",
}


def _plataforma(tmp_path: Path, sementes=None) -> Path:
    raiz = tmp_path / "plataforma"
    (raiz / "env").mkdir(parents=True)
    for nome, conteudo in (sementes or SEMENTES).items():
        (raiz / "env" / nome).write_text(conteudo, encoding="utf-8")
    return raiz


def _rodar(raiz: Path) -> subprocess.CompletedProcess:
    assert SCRIPT.is_file(), (
        f"{SCRIPT} não existe. Este guarda não tem o que medir, e isso não é um "
        "OK — [INV-CI01]."
    )
    ambiente = {**os.environ, "PLATAFORMA_DIR": str(raiz)}
    # O CAMINHO COMPLETO do bash, nunca a palavra solta: no Windows do
    # mantenedor, `bash` sem caminho encontra o do WSL, que não enxerga estes
    # arquivos e devolve um erro que não tem nada a ver com o script. Mesma
    # forma do guarda irmão `test_provisionar_pares_de_categorias.py`.
    return subprocess.run(
        [shutil.which("bash"), str(SCRIPT)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ambiente,
        stdin=subprocess.DEVNULL,
    )


def _valor(raiz: Path, arquivo: str, chave: str) -> str:
    for linha in (raiz / "env" / arquivo).read_text(encoding="utf-8").splitlines():
        if linha.startswith(f"{chave}="):
            return linha.split("=", 1)[1].strip()
    return ""


bash_ausente = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("openssl") is None,
    reason="sem bash ou sem openssl nesta máquina — o guarda não tem como medir",
)


@bash_ausente
def test_escreve_o_par_nos_dois_lados_e_nao_mostra_a_chave_privada(tmp_path):
    raiz = _plataforma(tmp_path)

    resultado = _rodar(raiz)

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    privada = _valor(raiz, "notificacoes.env", "VAPID_PRIVATE_KEY")
    publica = _valor(raiz, "notificacoes.env", "VAPID_PUBLIC_KEY")
    assert len(privada) == 43 and len(publica) == 87
    assert _valor(raiz, "funil.env", "VAPID_PUBLIC_KEY") == publica
    assert _valor(raiz, "notificacoes.env", "VAPID_SUBJECT").startswith("mailto:")

    # A promessa que mais custa quando quebra: nada da metade privada no que
    # ele imprime.
    assert privada not in resultado.stdout
    assert privada not in resultado.stderr


@bash_ausente
def test_a_chave_gravada_e_um_par_de_verdade(tmp_path):
    """Deriva a pública a partir da privada e compara com a que foi escrita.
    É a diferença entre "escreveu duas linhas" e "escreveu um par que
    funciona" — um par quebrado só apareceria no celular de alguém."""
    cryptography = pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    raiz = _plataforma(tmp_path)
    _rodar(raiz)

    def de_base64url(texto: str) -> bytes:
        return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))

    privada = ec.derive_private_key(
        int.from_bytes(
            de_base64url(_valor(raiz, "notificacoes.env", "VAPID_PRIVATE_KEY")), "big"
        ),
        ec.SECP256R1(),
    )
    derivada = base64.urlsafe_b64encode(
        privada.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
    ).decode().rstrip("=")

    assert derivada == _valor(raiz, "notificacoes.env", "VAPID_PUBLIC_KEY")


@bash_ausente
def test_rodar_de_novo_nao_troca_a_chave(tmp_path):
    """Uma chave nova invalidaria TODO aparelho já inscrito, em silêncio."""
    raiz = _plataforma(tmp_path)
    _rodar(raiz)
    primeira = _valor(raiz, "notificacoes.env", "VAPID_PRIVATE_KEY")

    _rodar(raiz)

    assert _valor(raiz, "notificacoes.env", "VAPID_PRIVATE_KEY") == primeira
    assert _valor(raiz, "funil.env", "VAPID_PUBLIC_KEY") == _valor(
        raiz, "notificacoes.env", "VAPID_PUBLIC_KEY"
    )


@bash_ausente
def test_nao_duplica_a_chave_nem_come_a_ultima_linha(tmp_path):
    """`funil.env` nasce SEM quebra de linha no fim, de propósito: sem o
    cuidado do script, a chave nova grudaria no valor da última linha e as
    duas iriam para o lixo juntas."""
    raiz = _plataforma(tmp_path)

    _rodar(raiz)

    linhas = (raiz / "env" / "funil.env").read_text(encoding="utf-8").splitlines()
    assert sum(1 for l in linhas if l.startswith("VAPID_PUBLIC_KEY=")) == 1
    assert "IDENTIDADE_API_TOKEN=tok" in linhas


@bash_ausente
def test_para_sem_escrever_quando_falta_um_env(tmp_path):
    raiz = _plataforma(tmp_path, {"notificacoes.env": "DJANGO_SECRET_KEY=x\n"})

    resultado = _rodar(raiz)

    assert resultado.returncode != 0
    assert "PAROU POR SEGURANÇA" in resultado.stdout
    assert "VAPID" not in (raiz / "env" / "notificacoes.env").read_text(
        encoding="utf-8"
    )


@bash_ausente
def test_para_quando_a_pasta_nao_e_a_plataforma(tmp_path):
    resultado = _rodar(tmp_path / "lugar-nenhum")

    assert resultado.returncode != 0
    assert "PAROU POR SEGURANÇA" in resultado.stdout
