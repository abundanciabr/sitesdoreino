"""Conferência de integridade da integração Mercado Pago.

O manifesto deve ser criado a partir de uma versão aprovada e guardado fora da
versão candidata. Este módulo apenas compara a árvore recebida com essa base.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path, PurePosixPath
from typing import Mapping


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_DIRETORIO_SHA256 = hashlib.sha256(b"diretorio\0").hexdigest()
_ROTA_FUNIL = re.compile(
    rb'(\n  services:\s*\n    funil:\s*\n      loadBalancer:\s*\n        servers: \[ \{ url: ")([^"]+)(" \} \])'
)
_ALVO_FUNIL = re.compile(rb"http://(?:aplicacao|meshcraft-funil-[0-9a-f]{12}-[0-9a-f]{8}):8000\Z")
_URL_FUNIL_CANONICA = b"http://funil-aprovado:8000"


class IntegridadeMercadoPagoErro(ValueError):
    """A versão examinada diverge da base aprovada ou a base é inválida."""


def _relativo(nome: object, *, diretorio: bool = False) -> str:
    if not isinstance(nome, str) or not nome or "\\" in nome or ":" in nome:
        raise IntegridadeMercadoPagoErro("Manifesto contém caminho inválido")
    caminho = nome[:-1] if diretorio and nome.endswith("/") else nome
    if not caminho or caminho.startswith("/") or caminho.endswith("/"):
        raise IntegridadeMercadoPagoErro("Manifesto contém caminho inválido")
    if any(parte in ("", ".", "..") for parte in caminho.split("/")):
        raise IntegridadeMercadoPagoErro("Manifesto contém caminho inválido")
    if str(PurePosixPath(caminho)) != caminho:
        raise IntegridadeMercadoPagoErro("Manifesto contém caminho inválido")
    return caminho


def _lista(caminhos: object) -> list[str]:
    if not isinstance(caminhos, list):
        raise IntegridadeMercadoPagoErro("Manifesto contém lista de caminhos inválida")
    nomes = [_relativo(caminho) for caminho in caminhos]
    if len(nomes) != len(set(nomes)):
        raise IntegridadeMercadoPagoErro("Manifesto contém caminho repetido")
    return nomes


def _raiz(pasta: os.PathLike[str] | str) -> Path:
    raiz = Path(pasta).absolute()
    if raiz.is_symlink() or not raiz.is_dir():
        raise IntegridadeMercadoPagoErro("Raiz protegida ausente ou inválida")
    return raiz


def _seguro(raiz: Path, nome: str, *, diretorio: bool) -> Path:
    caminho = raiz
    for parte in nome.split("/"):
        caminho = caminho / parte
        if caminho.is_symlink():
            raise IntegridadeMercadoPagoErro(f"Link simbólico em {nome}")
    if diretorio and not caminho.is_dir():
        raise IntegridadeMercadoPagoErro(f"Diretório protegido ausente: {nome}")
    if not diretorio and not caminho.is_file():
        raise IntegridadeMercadoPagoErro(f"Arquivo protegido ausente: {nome}")
    return caminho


def _hash_arquivo(caminho: Path, nome: str) -> str:
    try:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descritor = os.open(caminho, flags)
        with os.fdopen(descritor, "rb") as arquivo:
            if not stat.S_ISREG(os.fstat(arquivo.fileno()).st_mode):
                raise IntegridadeMercadoPagoErro(f"Arquivo protegido inválido: {nome}")
            digest = hashlib.sha256()
            for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
                digest.update(bloco)
            return digest.hexdigest()
    except OSError as erro:
        raise IntegridadeMercadoPagoErro(f"Não foi possível ler {nome}") from erro


def capturar_arvore(
    root: os.PathLike[str] | str,
    prefixos: list[str],
    arquivos: list[str],
) -> dict[str, str]:
    """Obtém hashes de arquivos e marcadores dos diretórios protegidos.

    Caminhos usam `/` e são relativos a ``root``. Um diretório é representado
    pela chave terminada em `/`, inclusive se estiver vazio.
    """
    nomes_prefixos = _lista(prefixos)
    nomes_arquivos = _lista(arquivos)
    if not nomes_prefixos and not nomes_arquivos:
        raise IntegridadeMercadoPagoErro("Nenhum caminho protegido definido")
    raiz = _raiz(root)
    capturado: dict[str, str] = {}
    for prefixo in nomes_prefixos:
        pasta = _seguro(raiz, prefixo, diretorio=True)
        def falha_listagem(erro: OSError) -> None:
            raise IntegridadeMercadoPagoErro(f"Não foi possível listar {prefixo}") from erro

        for diretorio_atual, diretorios, arquivos_atuais in os.walk(
            pasta, followlinks=False, onerror=falha_listagem
        ):
            atual = Path(diretorio_atual)
            relativo = atual.relative_to(raiz).as_posix()
            capturado[relativo + "/"] = _DIRETORIO_SHA256
            for nome in diretorios:
                filho = (atual / nome).relative_to(raiz).as_posix()
                _seguro(raiz, filho, diretorio=True)
            for nome in arquivos_atuais:
                filho = (atual / nome).relative_to(raiz).as_posix()
                caminho = _seguro(raiz, filho, diretorio=False)
                capturado[filho] = _hash_arquivo(caminho, filho)
    for nome in nomes_arquivos:
        caminho = _seguro(raiz, nome, diretorio=False)
        capturado[nome] = _hash_arquivo(caminho, nome)
    return dict(sorted(capturado.items()))


def _secao(manifesto: Mapping[str, object], campo: str) -> tuple[list[str], list[str], dict[str, str]]:
    secao = manifesto.get(campo)
    if not isinstance(secao, dict):
        raise IntegridadeMercadoPagoErro(f"Seção {campo} ausente no manifesto")
    prefixos = _lista(secao.get("prefixos", []))
    arquivos = _lista(secao.get("arquivos", []))
    hashes = secao.get("hashes")
    if not prefixos and not arquivos or not isinstance(hashes, dict) or not hashes:
        raise IntegridadeMercadoPagoErro(f"Base protegida {campo} vazia ou inválida")
    verificados: dict[str, str] = {}
    for nome, digest in hashes.items():
        if not isinstance(nome, str):
            raise IntegridadeMercadoPagoErro("Manifesto contém caminho inválido")
        pasta = nome.endswith("/")
        canonico = _relativo(nome, diretorio=pasta)
        if pasta and not any(canonico == p or canonico.startswith(p + "/") for p in prefixos):
            raise IntegridadeMercadoPagoErro("Manifesto contém caminho fora do escopo")
        if not pasta and nome not in arquivos and not any(nome.startswith(p + "/") for p in prefixos):
            raise IntegridadeMercadoPagoErro("Manifesto contém caminho fora do escopo")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise IntegridadeMercadoPagoErro(f"Hash inválido em {nome}")
        if pasta and digest != _DIRETORIO_SHA256:
            raise IntegridadeMercadoPagoErro(f"Marcador de diretório inválido em {nome}")
        verificados[nome] = digest
    for nome in arquivos:
        if nome not in verificados:
            raise IntegridadeMercadoPagoErro(f"Base sem arquivo protegido: {nome}")
    for nome in prefixos:
        if nome + "/" not in verificados:
            raise IntegridadeMercadoPagoErro(f"Base sem diretório protegido: {nome}")
    return prefixos, arquivos, verificados


def conferir_arvore(root: os.PathLike[str] | str, manifesto: Mapping[str, object], campo: str = "fontes") -> None:
    """Compara uma árvore com manifesto externo já confiável; lança em divergência."""
    if not isinstance(manifesto, Mapping):
        raise IntegridadeMercadoPagoErro("Manifesto inválido")
    prefixos, arquivos, esperados = _secao(manifesto, campo)
    encontrados = capturar_arvore(root, prefixos, arquivos)
    alterados = sorted(nome for nome in esperados.keys() & encontrados.keys() if esperados[nome] != encontrados[nome])
    removidos = sorted(esperados.keys() - encontrados.keys())
    adicionados = sorted(encontrados.keys() - esperados.keys())
    if alterados or removidos or adicionados:
        partes = []
        if alterados:
            partes.append("alterados: " + ", ".join(alterados))
        if removidos:
            partes.append("removidos: " + ", ".join(removidos))
        if adicionados:
            partes.append("adicionados: " + ", ".join(adicionados))
        raise IntegridadeMercadoPagoErro(f"{campo}: " + "; ".join(partes))


def conferir_fontes(pasta: os.PathLike[str] | str, politica: Mapping[str, object]) -> None:
    conferir_arvore(pasta, politica, "fontes")


def conferir_ambiente(raiz_plataforma: os.PathLike[str] | str, politica: Mapping[str, object]) -> None:
    conferir_arvore(raiz_plataforma, politica, "ambiente")
    if "rotas_sha256" in politica:
        conferir_rotas(raiz_plataforma, politica)


def conferir_pacote(pasta: os.PathLike[str] | str, imagem: str, politica: Mapping[str, object]) -> None:
    esperada = politica.get("imagem") if isinstance(politica, Mapping) else None
    if not isinstance(esperada, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", esperada):
        raise IntegridadeMercadoPagoErro("Imagem aprovada ausente ou inválida")
    if imagem != esperada:
        raise IntegridadeMercadoPagoErro("Imagem do pacote divergente")
    conferir_arvore(pasta, politica, "pacote")


def capturar_rotas(root: os.PathLike[str] | str) -> str:
    """Hash da configuração Traefik com somente o destino variável do funil normalizado."""
    nome = "traefik/dynamic/plataforma.yml"
    caminho = _seguro(_raiz(root), nome, diretorio=False)
    try:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descritor = os.open(caminho, flags)
        with os.fdopen(descritor, "rb") as arquivo:
            if not stat.S_ISREG(os.fstat(arquivo.fileno()).st_mode):
                raise IntegridadeMercadoPagoErro(f"Arquivo protegido inválido: {nome}")
            texto = arquivo.read()
    except OSError as erro:
        raise IntegridadeMercadoPagoErro(f"Não foi possível ler {nome}") from erro

    marcadores = list(re.finditer(rb"(?m)^  services:[ \t]*\r?$", texto))
    if len(marcadores) != 1:
        raise IntegridadeMercadoPagoErro(f"Bloco de serviços ausente ou duplicado em {nome}")
    apos_servicos = texto[marcadores[0].end():]
    proxima_secao = re.search(rb"(?m)^  [A-Za-z][A-Za-z0-9_-]*:[ \t]*\r?$", apos_servicos)
    bloco = apos_servicos[:proxima_secao.start()] if proxima_secao else apos_servicos
    if len(re.findall(rb"(?m)^    funil:[ \t]*\r?$", bloco)) != 1:
        raise IntegridadeMercadoPagoErro(f"Rota funil ausente ou duplicada em {nome}")
    encontrados = list(_ROTA_FUNIL.finditer(texto))
    if len(encontrados) != 1 or not _ALVO_FUNIL.fullmatch(encontrados[0].group(2)):
        raise IntegridadeMercadoPagoErro(f"Destino funil inválido em {nome}")
    correspondencia = encontrados[0]
    normalizado = (
        texto[:correspondencia.start()]
        + correspondencia.group(1)
        + _URL_FUNIL_CANONICA
        + correspondencia.group(3)
        + texto[correspondencia.end():]
    )
    return hashlib.sha256(normalizado).hexdigest()


def conferir_rotas(root: os.PathLike[str] | str, politica: Mapping[str, object]) -> None:
    """Compara as rotas com hash externo sem expor o conteúdo da configuração."""
    esperado = politica.get("rotas_sha256") if isinstance(politica, Mapping) else None
    if not isinstance(esperado, str) or not _SHA256.fullmatch(esperado):
        raise IntegridadeMercadoPagoErro("Hash aprovado das rotas ausente ou inválido")
    if capturar_rotas(root) != esperado:
        raise IntegridadeMercadoPagoErro("Rotas protegidas alteradas: traefik/dynamic/plataforma.yml")
