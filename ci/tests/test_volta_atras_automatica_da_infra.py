"""A infraestrutura volta sozinha quando a troca dá errado.

Por que este arquivo existe. Até 15/09/2026, `infra/sincronizar-infra-na-vps.sh`
IMPRIMIA o caminho de volta e não o aplicava, com a frase "RESTAURAÇÃO (você, na
VPS)". O pressuposto era que alguém com chave SSH leria o log e digitaria os
quatro comandos. O mantenedor não usa terminal e o agente não tem chave, então,
na prática, uma troca ruim deixava a borda pública fora do ar por tempo
indeterminado: o mesmo Traefik serve as portas 80 e 443 de toda a plataforma.

O que se prova aqui é comportamento, não intenção: a função de volta é extraída
do script de verdade e EXECUTADA contra uma /opt/plataforma de mentira, com
`docker` dublado, e no fim os arquivos que estavam no ar precisam ter voltado.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "infra" / "sincronizar-infra-na-vps.sh"
NOME_DA_FUNCAO = "restaurar_o_que_estava_no_ar"


def bash_de_verdade() -> str:
    """O bash que roda scripts, e não o atalho do WSL.

    No Windows, `bash` no PATH é `System32\bash.exe`, que entra no WSL e não
    enxerga os caminhos deste teste. O bash do Git é o mesmo interpretador que
    a VPS usa na prática para este script.
    """
    for candidato in (
        r"C:\Program Files\Gitinash.exe",
        r"C:\Program Files (x86)\Gitinash.exe",
    ):
        if Path(candidato).is_file():
            return candidato
    achado = shutil.which("bash")
    if not achado:
        raise AssertionError("nenhum bash disponível para provar a volta atrás")
    return achado


def fonte() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def corpo_da_funcao() -> str:
    """O texto da função, do cabeçalho até a chave que a fecha na coluna 0."""
    texto = fonte()
    abertura = f"{NOME_DA_FUNCAO}() {{"
    inicio = texto.index(abertura)
    fim = texto.index("\n}\n", inicio) + len("\n}\n")
    return texto[inicio:fim]


def test_a_funcao_de_volta_existe_no_script():
    assert f"{NOME_DA_FUNCAO}() {{" in fonte(), (
        f"{SCRIPT} precisa definir {NOME_DA_FUNCAO}(); sem ela não há volta atrás."
    )


def test_a_volta_dispara_sozinha_por_trap_e_so_depois_da_troca():
    texto = fonte()
    assert re.search(rf"trap\s+.*{NOME_DA_FUNCAO}.*EXIT", texto), (
        "a volta precisa estar armada num trap de EXIT; chamada só nos ifs "
        "conhecidos deixa de fora a falha que ninguém previu."
    )
    assert "TROCADO=1" in texto, (
        "o trap precisa de uma marca dizendo que a troca já aconteceu; sem ela "
        "uma falha ANTES da troca restauraria por cima de um estado intacto."
    )
    assert texto.index("TROCADO=1") > texto.index("mv -f docker-compose.yml.new"), (
        "a marca TROCADO=1 tem de vir DEPOIS da troca dos arquivos."
    )


def test_o_script_nao_manda_mais_o_mantenedor_restaurar_a_mao():
    texto = fonte()
    assert "RESTAURAÇÃO (você, na VPS" not in texto, (
        "esta frase mandava o dono da casa abrir terminal na VPS, que é "
        "exatamente o que ele não faz."
    )


def test_a_funcao_traz_de_volta_o_que_estava_no_ar(tmp_path):
    """Prova de comportamento: depois de uma troca ruim, o que estava no ar volta."""
    plataforma = tmp_path / "opt" / "plataforma"
    plataforma.mkdir(parents=True)
    (plataforma / "docker-compose.yml").write_text("versao: ruim\n", encoding="utf-8")
    (plataforma / "docker-compose.yml.bak-STAMP").write_text("versao: boa\n", encoding="utf-8")
    traefik = plataforma / "traefik"
    traefik.mkdir()
    (traefik / "traefik.yml").write_text("entryPoints: ruim\n", encoding="utf-8")
    backup = plataforma / "traefik.bak-STAMP"
    backup.mkdir()
    (backup / "traefik.yml").write_text("entryPoints: bom\n", encoding="utf-8")

    dublê = tmp_path / "bin"
    dublê.mkdir()
    chamadas = tmp_path / "chamadas.txt"
    (dublê / "docker").write_text(
        f'#!/usr/bin/env bash\necho "$@" >> "{chamadas}"\n', encoding="utf-8"
    )
    (dublê / "docker").chmod(0o755)

    roteiro = tmp_path / "roteiro.sh"
    roteiro.write_text(
        "set -eu\n"
        f'cd "{plataforma}"\n'
        'STAMP=STAMP\n'
        f"{corpo_da_funcao()}\n"
        f"{NOME_DA_FUNCAO}\n",
        encoding="utf-8",
    )

    ambiente = dict(os.environ, PATH=f"{dublê}{os.pathsep}{os.environ['PATH']}")
    fim = subprocess.run(
        [bash_de_verdade(), str(roteiro)], capture_output=True, text=True, env=ambiente
    )
    assert fim.returncode == 0, fim.stderr

    assert (plataforma / "docker-compose.yml").read_text(encoding="utf-8") == "versao: boa\n"
    assert (traefik / "traefik.yml").read_text(encoding="utf-8") == "entryPoints: bom\n"
    aplicadas = chamadas.read_text(encoding="utf-8")
    assert "up -d" in aplicadas, "restaurar arquivo sem subir o container deixa a borda parada"
    assert "--force-recreate traefik" in aplicadas, (
        "o bind mount prende o inode: sem recriar, o Traefik continua lendo o diretório errado"
    )
