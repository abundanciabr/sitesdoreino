"""O script que liga o e-mail de verdade, EXECUTADO — não lido.

`infra/provisionar-email.sh` roda **na máquina do mantenedor**, com uma linha, e
um erro ali custa o pior tipo de tempo que este projeto tem: o dele, no terminal,
sem saber o que fazer com a tela (a lição de 24/08/2026, quando um passo entregue
como texto falhou três vezes seguidas com ele).

E aqui há um agravante que os irmãos não têm: **este script recebe um SEGREDO de
verdade** — a chave SMTP do Brevo. `armadilhas/090` mediu, em 24/08/2026, o
segredo do OAuth do Google vazando por quatro caminhos ao mesmo tempo, e o quarto
é o que engana: *o print que a pessoa manda ao agente para provar que funcionou*.

Por isso o guarda que carrega este arquivo é
`test_a_chave_NUNCA_aparece_em_lugar_nenhum`: ele varre **toda** a saída do
script à procura do segredo. Se um dia alguém acrescentar um `echo` de
diagnóstico, ele reprova antes de o vazamento existir.

As outras quatro promessas medidas aqui:

1. **Fail-closed de verdade** — pasta errada, `env` faltando ou chave vazia
   param **sem escrever nada**, e não com um aviso seguido de escrita.
2. **Idempotente** — rodar de novo não duplica linha. Chave repetida num
   `env_file` faz o Docker Compose usar só a última, e o valor velho ficaria por
   baixo sem nada acusar.
3. **Não reescreve o env** — `env/mensageria.env` está vivo e é compartilhado
   pelos três containers da célula; refazê-lo rotacionaria a senha do banco em
   uso.
4. **Recusa o texto de exemplo** — colar o placeholder é o erro mais provável de
   quem segue instrução, e gravá-lo daria um sistema "configurado" que não manda
   nada.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "infra" / "provisionar-email.sh"

CHAVE_SECRETA = "xsmtpsib-2f4a9c8e1b7d3e5f-SEGREDOxyz"
LOGIN = "8f2a1b@smtp-brevo.com"

SEMENTES = {
    # Sem quebra de linha no fim DE PROPÓSITO: é o caso que gruda a chave nova no
    # fim da última linha, e a última linha de um env é um valor.
    "mensageria.env": "DJANGO_SECRET_KEY=x\nDATABASE_URL=postgres://a/b",
    "alunos.env": "DJANGO_SECRET_KEY=z\n",
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


def _rodar(raiz: Path, *argumentos: str, chave: str = CHAVE_SECRETA):
    """Roda o script de verdade, com a chave chegando pela ENTRADA PADRÃO.

    É assim que o `read -r -s` a recebe — e encenar isso aqui é parte do que se
    mede: se alguém trocar o prompt por um argumento, este teste continua
    passando a chave por stdin e o script gravaria vazio, quebrando alto.
    """
    ambiente = dict(os.environ)
    ambiente["PLATAFORMA_DIR"] = str(raiz)
    return subprocess.run(
        [_bash(), str(SCRIPT), *argumentos],
        input=chave + "\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ambiente,
    )


def _valor(raiz: Path, chave: str) -> str | None:
    texto = (raiz / "env" / "mensageria.env").read_text(encoding="utf-8")
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
    assert "curl -fsSL" in texto and "provisionar-email.sh" in texto


# --------------------------------------------------------- o guarda do segredo


def test_a_chave_NUNCA_aparece_em_lugar_nenhum(tmp_path):
    """O GUARDA QUE CARREGA ESTE ARQUIVO (`armadilhas/090`).

    A chave pode estar no arquivo de env — é para lá que ela vai. Não pode estar
    em NADA que o mantenedor veja ou copie: a tela é o print que ele manda de
    volta ao agente, e esse é o caminho de vazamento que a armadilha mediu.
    """
    raiz = _plataforma(tmp_path)
    resultado = _rodar(raiz, LOGIN, "escola@meshcraft.top")

    assert CHAVE_SECRETA not in resultado.stdout, "a chave VAZOU na saída do script"
    assert CHAVE_SECRETA not in resultado.stderr, "a chave VAZOU no stderr"
    # E ela chegou inteira onde devia.
    assert _valor(raiz, "SMTP_PASSWORD") == CHAVE_SECRETA


# ------------------------------------------------------------ o caminho feliz


def test_grava_as_cinco_chaves(tmp_path):
    raiz = _plataforma(tmp_path)
    resultado = _rodar(raiz, LOGIN, "escola@meshcraft.top")

    assert "PRONTO: e-mail da plataforma ligado." in resultado.stdout
    assert _valor(raiz, "SMTP_HOST") == "smtp-relay.brevo.com"
    assert _valor(raiz, "SMTP_PORT") == "587"
    assert _valor(raiz, "SMTP_USER") == LOGIN
    assert _valor(raiz, "SMTP_FROM") == "escola@meshcraft.top"
    assert _valor(raiz, "SMTP_PASSWORD") == CHAVE_SECRETA


def test_nao_reescreve_o_resto_do_env(tmp_path):
    """O env é compartilhado pelos três containers; refazê-lo rotacionaria a
    senha do banco em uso e derrubaria a célula inteira."""
    raiz = _plataforma(tmp_path)
    _rodar(raiz, LOGIN)

    texto = (raiz / "env" / "mensageria.env").read_text(encoding="utf-8")
    assert "DJANGO_SECRET_KEY=x" in texto
    assert "DATABASE_URL=postgres://a/b" in texto


def test_o_env_sem_quebra_de_linha_no_fim_nao_gruda_a_chave_no_valor_anterior(tmp_path):
    """A semente termina sem `\\n` de propósito — é o caso que o `>>` estraga."""
    raiz = _plataforma(tmp_path)
    _rodar(raiz, LOGIN)

    assert _valor(raiz, "DATABASE_URL") == "postgres://a/b"
    assert _valor(raiz, "SMTP_HOST") == "smtp-relay.brevo.com"


def test_rodar_de_novo_nao_duplica_nenhuma_linha(tmp_path):
    """Chave repetida num env_file: o Compose usa só a última, e a de baixo fica
    sem nada acusar."""
    raiz = _plataforma(tmp_path)
    _rodar(raiz, LOGIN)
    _rodar(raiz, LOGIN)

    texto = (raiz / "env" / "mensageria.env").read_text(encoding="utf-8")
    for chave in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"):
        assert texto.count(f"\n{chave}=") + texto.startswith(f"{chave}=") == 1, (
            f"{chave} aparece mais de uma vez"
        )


def test_rodar_de_novo_com_chave_nova_ATUALIZA(tmp_path):
    raiz = _plataforma(tmp_path)
    _rodar(raiz, LOGIN)
    _rodar(raiz, LOGIN, chave="xsmtpsib-OUTRA-CHAVE-9z8y7x")

    assert _valor(raiz, "SMTP_PASSWORD") == "xsmtpsib-OUTRA-CHAVE-9z8y7x"


# ----------------------------------------------------- as recusas fail-closed


def test_sem_login_para_sem_escrever_nada(tmp_path):
    raiz = _plataforma(tmp_path)
    antes = (raiz / "env" / "mensageria.env").read_text(encoding="utf-8")
    resultado = _rodar(raiz)

    assert resultado.returncode != 0
    assert "PAROU POR SEGURANÇA" in resultado.stdout
    assert (raiz / "env" / "mensageria.env").read_text(encoding="utf-8") == antes


def test_chave_vazia_para_sem_escrever_nada(tmp_path):
    raiz = _plataforma(tmp_path)
    antes = (raiz / "env" / "mensageria.env").read_text(encoding="utf-8")
    resultado = _rodar(raiz, LOGIN, chave="")

    assert resultado.returncode != 0
    assert "PAROU POR SEGURANÇA" in resultado.stdout
    assert (raiz / "env" / "mensageria.env").read_text(encoding="utf-8") == antes


def test_o_texto_de_exemplo_e_recusado(tmp_path):
    """O erro mais provável de quem segue instrução: colar o placeholder.

    Gravá-lo daria um sistema "configurado" que não manda nada — e a próxima
    pessoa a investigar acharia as cinco variáveis no lugar.
    """
    raiz = _plataforma(tmp_path)
    resultado = _rodar(raiz, "SEU_LOGIN_SMTP")

    assert resultado.returncode != 0
    assert "texto de exemplo" in resultado.stdout
    assert _valor(raiz, "SMTP_USER") is None


def test_remetente_malformado_e_recusado(tmp_path):
    raiz = _plataforma(tmp_path)
    resultado = _rodar(raiz, LOGIN, "isto-nao-e-email")

    assert resultado.returncode != 0
    assert "PAROU POR SEGURANÇA" in resultado.stdout
    assert _valor(raiz, "SMTP_USER") is None


def test_chave_com_cerquilha_e_recusada_em_vez_de_cortada(tmp_path):
    """`#` num arquivo de configuração começa comentário: o valor seria cortado
    pela metade, e o container leria meia chave sem nada acusar."""
    raiz = _plataforma(tmp_path)
    resultado = _rodar(raiz, LOGIN, chave="chave#com-cerquilha")

    assert resultado.returncode != 0
    assert _valor(raiz, "SMTP_PASSWORD") is None


def test_pasta_errada_para_antes_de_tocar_em_arquivo(tmp_path):
    resultado = _rodar(tmp_path / "nao-existe", LOGIN)

    assert resultado.returncode != 0
    assert "você está na VPS certa" in resultado.stdout


def test_env_da_mensageria_faltando_para_sem_criar(tmp_path):
    raiz = _plataforma(tmp_path, faltando="mensageria.env")
    resultado = _rodar(raiz, LOGIN)

    assert resultado.returncode != 0
    assert not (raiz / "env" / "mensageria.env").exists()


def test_env_de_referencia_faltando_para(tmp_path):
    """Sem a referência de dono/permissão o env nasceria ilegível para o
    pipeline (`armadilhas/091`), e o deploy reprovaria com 'permission denied'
    numa mensagem que não diz quem não conseguiu ler."""
    raiz = _plataforma(tmp_path, faltando="alunos.env")
    resultado = _rodar(raiz, LOGIN)

    assert resultado.returncode != 0
    assert _valor(raiz, "SMTP_HOST") is None
