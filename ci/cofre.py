"""O cofre de segredos da máquina do mantenedor: o Gerenciador de Credenciais
do Windows, o mesmo onde o `gh` e o `git` já guardam os tokens deles.

Só biblioteca padrão (ctypes sobre `advapi32`: CredWriteW, CredReadW,
CredEnumerateW, CredDeleteW). Cada segredo é uma credencial genérica com alvo
`sitesdoreino/<NOME>`, persistida no perfil do usuário (CRED_PERSIST_LOCAL_MACHINE):
vale em sessão nova e depois de reiniciar, e o Windows a cifra com o login do
usuário (DPAPI). Nenhum arquivo de texto.

    python ci/cofre.py guardar NOME              # valor pelo stdin; nunca ecoa
    python ci/cofre.py usar NOME[,NOME] -- cmd   # injeta só esses no filho
    python ci/cofre.py listar                    # só nomes
    python ci/cofre.py conferir NOME             # presente/ausente e tamanho
    python ci/cofre.py revogar NOME              # tira do cofre

`usar` entrega cada segredo ao processo filho como variável de ambiente cujo
nome é o NOME em maiúsculas, com `-` e `.` trocados por `_` (`robo-admin` vira
`ROBO_ADMIN`). O cofre não escreve nada no stdout em `usar`: o que aparece é
do comando filho.

RECUPERAR E REVOGAR A CREDENCIAL DO ROBÔ DO ADMIN

A credencial não é recuperável: o servidor guarda só o sha256 dela. Perdeu,
vazou ou quer trocar? Emita outra pela VPS, que a anterior deixa de valer no
mesmo instante, e o valor vai do cano direto para este cofre, sem tela:

    ssh sitesdoreino-vps 'docker exec $(docker ps -q --filter label=com.docker.compose.project=plataforma --filter label=com.docker.compose.service=aplicacao | head -n1) python -m config.comando admin conta_do_robo emitir' | python ci/cofre.py guardar robo-admin

Para cortar o acesso do robô sem emitir outra:

    ssh sitesdoreino-vps 'docker exec $(docker ps -q --filter label=com.docker.compose.project=plataforma --filter label=com.docker.compose.service=aplicacao | head -n1) python -m config.comando admin conta_do_robo revogar'
    python ci/cofre.py revogar robo-admin
"""

from __future__ import annotations

import ctypes
import functools
import getpass
import os
import re
import subprocess
import sys

PREFIXO = "sitesdoreino/"
NOME_VALIDO = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,63}$")
TETO_EM_BYTES = 5 * 512  # CRED_MAX_CREDENTIAL_BLOB_SIZE

CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2
ERROR_NOT_FOUND = 1168


class Recusa(Exception):
    """Erro que pode ser mostrado: nunca carrega o valor de um segredo."""


@functools.lru_cache(maxsize=None)
def _api():
    if sys.platform != "win32":
        raise Recusa("o cofre usa o Gerenciador de Credenciais do Windows")
    from ctypes import wintypes

    class FILETIME(ctypes.Structure):
        _fields_ = [("baixo", wintypes.DWORD), ("alto", wintypes.DWORD)]

    class CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]

    P = ctypes.POINTER(CREDENTIAL)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi32.CredWriteW.argtypes = [P, wintypes.DWORD]
    advapi32.CredWriteW.restype = wintypes.BOOL
    advapi32.CredReadW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(P),
    ]
    advapi32.CredReadW.restype = wintypes.BOOL
    advapi32.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    advapi32.CredDeleteW.restype = wintypes.BOOL
    advapi32.CredEnumerateW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(ctypes.POINTER(P)),
    ]
    advapi32.CredEnumerateW.restype = wintypes.BOOL
    advapi32.CredFree.argtypes = [ctypes.c_void_p]
    advapi32.CredFree.restype = None
    return advapi32, CREDENTIAL, P, wintypes


def _alvo(nome: str) -> str:
    if not NOME_VALIDO.match(nome):
        raise Recusa(
            f"nome inválido: {nome!r} (letra no começo; letras, números, . _ -)"
        )
    return PREFIXO + nome


def variavel(nome: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", nome).upper()


def _falhou(o_que: str) -> Recusa:
    return Recusa(f"{o_que} falhou (erro do Windows {ctypes.get_last_error()})")


def guardar(nome: str, valor: str) -> None:
    advapi32, CREDENTIAL, _P, _w = _api()
    alvo = _alvo(nome)
    dados = valor.encode("utf-8")
    if not dados:
        raise Recusa("valor vazio: nada foi guardado")
    if len(dados) > TETO_EM_BYTES:
        raise Recusa(f"valor maior que {TETO_EM_BYTES} bytes: nada foi guardado")
    buffer = (ctypes.c_ubyte * len(dados)).from_buffer_copy(dados)
    cred = CREDENTIAL()
    cred.Type = CRED_TYPE_GENERIC
    cred.TargetName = alvo
    cred.Comment = "sitesdoreino: ci/cofre.py"
    cred.CredentialBlobSize = len(dados)
    cred.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
    cred.Persist = CRED_PERSIST_LOCAL_MACHINE
    cred.UserName = nome
    try:
        if not advapi32.CredWriteW(ctypes.byref(cred), 0):
            raise _falhou("guardar")
    finally:
        ctypes.memset(ctypes.addressof(buffer), 0, len(dados))


def ler(nome: str) -> str | None:
    advapi32, _C, P, _w = _api()
    ponteiro = P()
    if not advapi32.CredReadW(
        _alvo(nome), CRED_TYPE_GENERIC, 0, ctypes.byref(ponteiro)
    ):
        if ctypes.get_last_error() == ERROR_NOT_FOUND:
            return None
        raise _falhou("ler")
    try:
        cred = ponteiro.contents
        return ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize).decode(
            "utf-8"
        )
    finally:
        advapi32.CredFree(ponteiro)


def listar() -> list[str]:
    advapi32, _C, P, wintypes = _api()
    quantos = wintypes.DWORD()
    lista = ctypes.POINTER(P)()
    if not advapi32.CredEnumerateW(
        PREFIXO + "*", 0, ctypes.byref(quantos), ctypes.byref(lista)
    ):
        if ctypes.get_last_error() == ERROR_NOT_FOUND:
            return []
        raise _falhou("listar")
    try:
        return sorted(
            lista[i].contents.TargetName[len(PREFIXO) :] for i in range(quantos.value)
        )
    finally:
        advapi32.CredFree(lista)


def revogar(nome: str) -> bool:
    advapi32, _C, _P, _w = _api()
    if advapi32.CredDeleteW(_alvo(nome), CRED_TYPE_GENERIC, 0):
        return True
    if ctypes.get_last_error() == ERROR_NOT_FOUND:
        return False
    raise _falhou("revogar")


def _valor_do_stdin() -> str:
    if sys.stdin is None:
        raise Recusa("sem stdin: mande o valor pelo cano")
    if sys.stdin.isatty():
        return getpass.getpass("valor (não aparece na tela): ")
    bruto = sys.stdin.buffer.read().decode("utf-8")
    return bruto.lstrip("﻿").rstrip("\r\n")


def _usar(nomes: str, comando: list[str]) -> int:
    if not comando:
        raise Recusa("faltou o comando depois de --")
    ambiente = dict(os.environ)
    for nome in [n.strip() for n in nomes.split(",") if n.strip()]:
        valor = ler(nome)
        if valor is None:
            raise Recusa(f"ausente: {nome}; nada foi executado")
        ambiente[variavel(nome)] = valor
    try:
        return subprocess.run(comando, env=ambiente).returncode
    except FileNotFoundError:
        raise Recusa(f"comando não encontrado: {comando[0]}") from None


USO = (
    "uso: cofre.py guardar NOME | usar NOME[,NOME] -- comando ... | listar | "
    "conferir NOME | revogar NOME"
)


def main(argv: list[str]) -> int:
    if not argv:
        print(USO, file=sys.stderr)
        return 2
    acao, resto = argv[0], argv[1:]
    try:
        if acao == "guardar" and len(resto) == 1:
            guardar(resto[0], _valor_do_stdin())
            print(f"guardado: {resto[0]}")
            return 0
        if acao == "usar" and len(resto) >= 2 and resto[1] == "--":
            return _usar(resto[0], resto[2:])
        if acao == "listar" and not resto:
            for nome in listar():
                print(nome)
            return 0
        if acao == "conferir" and len(resto) == 1:
            valor = ler(resto[0])
            if valor is None:
                print(f"{resto[0]}: ausente")
                return 1
            print(f"{resto[0]}: presente, {len(valor)} caracteres")
            return 0
        if acao == "revogar" and len(resto) == 1:
            if revogar(resto[0]):
                print(f"revogado: {resto[0]}")
                return 0
            print(f"{resto[0]}: ausente")
            return 1
    except Recusa as recusa:
        print(f"cofre: {recusa}", file=sys.stderr)
        return 2
    print(USO, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
