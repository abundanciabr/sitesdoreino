#!/usr/bin/env python3
"""Atualiza só os três assets do checkout Appmax de teste já publicado.

Uso no console administrativo: python3 publicar_assets_pix.py RAIZ_DO_CODIGO_REVISADO
RAIZ_DO_CODIGO_REVISADO contém services/checkout_appmax/assets/.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import signal
import stat
import subprocess
import sys
import urllib.request


ROOT = Path("/opt/plataforma")
TASK = ROOT / "appmax-clones/checkout-roblox-20261009"
DEST = TASK / "servico/assets"
TOOLS = Path("/usr/local/lib/meshcraft-publicador/v1-20261006T184415Z")
POLICY = TOOLS / "mercadopago/politica.json"
JOURNAL = ROOT / "publicacoes/aplicacao.json"
WEB = "meshcraft-checkout-appmax-roblox-20261009"
URL = "https://meshcraft.top/checkout/comprar-desafio-como-ganhar-em-dolar-com-roblox/"
MP_URL = "https://meshcraft.top/checkout/desafio-como-ganhar-em-dolar-com-roblox/"
ASSETS = ("checkout.css", "checkout.js", "checkout.html")
SANDBOX_SCRIPT = "https://scripts.sandboxappmax.com.br/appmax.min.js"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def regular(path: Path) -> os.stat_result:
    if path.is_symlink():
        raise RuntimeError("Link simbólico recusado")
    info = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode):
        raise RuntimeError("Asset regular ausente")
    return info


def sync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic(path: Path, data: bytes, owner: os.stat_result, expected_inode: int | None = None) -> None:
    temporary = path.with_name("." + path.name + ".pix-" + secrets.token_hex(8))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chown(temporary, owner.st_uid, owner.st_gid)
        os.chmod(temporary, stat.S_IMODE(owner.st_mode))
        if regular(path).st_ino != (owner.st_ino if expected_inode is None else expected_inode):
            raise RuntimeError("Asset mudou durante a publicação")
        os.replace(temporary, path)
        sync_dir(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def request(url: str) -> tuple[int, bytes]:
    # GET somente: não cria sessão nem pedido. Query única evita cache de assets.
    with urllib.request.urlopen(url, timeout=20) as response:
        return response.status, response.read()


def config_from_page(page: bytes) -> dict:
    match = re.search(rb'<script id="checkout-config" type="application/json">(.*?)</script>', page, re.S)
    if match is None:
        raise RuntimeError("Checkout de teste sem configuração")
    config = json.loads(match.group(1))
    if config.get("environment") != "sandbox" or config.get("scriptURL") != SANDBOX_SCRIPT:
        raise RuntimeError("Checkout deixou de ser sandbox")
    if b"mercadopago.com" in page.lower() or b"MP_DEVICE_SESSION_ID" in page:
        raise RuntimeError("Checkout de teste contém SDK Mercado Pago")
    return config


def assert_frozen() -> None:
    spec = importlib.util.spec_from_file_location("mercadopago_congelado", TOOLS / "infra/mercadopago_congelado.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    approved = json.loads(JOURNAL.read_text(encoding="utf-8"))["aprovada"]
    checker.conferir_ambiente(ROOT, policy)
    checker.conferir_rotas(ROOT, policy)
    checker.conferir_pacote(approved["codigo"], approved["imagem"], policy)
    checker.conferir_pacote(TASK / "codigo-aprovado-copia", approved["imagem"], policy)


def assert_clone() -> None:
    result = subprocess.run(["docker", "inspect", WEB], capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise RuntimeError("Contêiner da cópia indisponível")
    current = json.loads(result.stdout)[0]
    if not current["State"]["Running"]:
        raise RuntimeError("Cópia Appmax não está em execução")
    if "meshcraft-appmax-roblox-sandbox-20261009" not in current["NetworkSettings"]["Networks"]:
        raise RuntimeError("Rede privada sandbox ausente")
    mounts = {item["Destination"]: item for item in current.get("Mounts", [])}
    clone = mounts.get("/clone", {})
    if clone.get("Source") != str(TASK / "servico") or clone.get("RW") is not False:
        raise RuntimeError("Montagem da cópia mudou")
    approved = json.loads(JOURNAL.read_text(encoding="utf-8"))["aprovada"]
    if current["Image"] != approved["imagem"]:
        raise RuntimeError("Imagem aprovada da cópia mudou")
    status, page = request(URL)
    if status != 200:
        raise RuntimeError("Checkout de teste indisponível")
    config_from_page(page)


def backup_assets(folder: Path, originals: dict[str, bytes], owners: dict[str, os.stat_result]) -> None:
    if folder.parent.is_symlink():
        raise RuntimeError("Diretório de backup inválido")
    folder.parent.mkdir(mode=0o700, exist_ok=True)
    os.chmod(folder.parent, 0o700)
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    details = {}
    for name in ASSETS:
        data, owner = originals[name], owners[name]
        target = folder / name
        with target.open("xb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        details[name] = {"sha256": digest(data), "uid": owner.st_uid,
                         "gid": owner.st_gid, "mode": oct(stat.S_IMODE(owner.st_mode))}
    meta = folder / "manifesto.json"
    with meta.open("x", encoding="utf-8") as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(details, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    sync_dir(folder)
    sync_dir(folder.parent)
    for name in ASSETS:
        if digest((folder / name).read_bytes()) != details[name]["sha256"]:
            raise RuntimeError("Backup de asset falhou")


def prove(source: dict[str, bytes]) -> dict[str, int]:
    statuses = {}
    for url in (URL, URL + "assets/checkout.css", URL + "assets/checkout.js",
                "https://meshcraft.top/", MP_URL):
        probe = url + ("?prova=" + secrets.token_hex(6) if "/assets/" in url else "")
        status, body = request(probe)
        statuses[url] = status
        if status != 200:
            raise RuntimeError("Prova pública HTTP falhou")
        if url.endswith("checkout.css") and body != source["checkout.css"]:
            raise RuntimeError("CSS publicado diverge")
        if url.endswith("checkout.js") and body != source["checkout.js"]:
            raise RuntimeError("JavaScript publicado diverge")
        if url == URL:
            config_from_page(body)
            normalized = re.sub(rb'(<script id="checkout-config" type="application/json">).*?(</script>)',
                                rb'\g<1>__CHECKOUT_CONFIG__\g<2>', body, count=1, flags=re.S)
            expected_html = source["checkout.html"].decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
            if normalized != expected_html:
                raise RuntimeError("HTML publicado diverge")
        if url == MP_URL and (b"mercadopago.com" not in body.lower() or b"checkout-config" in body):
            raise RuntimeError("Checkout Mercado Pago anterior mudou")
    return statuses


def run(source_root: Path) -> None:
    if os.geteuid() != 0:
        raise RuntimeError("Use o console administrativo da hospedagem")
    source_dir = source_root / "services/checkout_appmax/assets"
    if source_dir.is_symlink() or not source_dir.is_dir():
        raise RuntimeError("Origem revisada ausente")
    for name in ASSETS:
        regular(source_dir / name)
    source = {name: (source_dir / name).read_bytes() for name in ASSETS}
    for name in ASSETS:
        if not source[name]:
            raise RuntimeError("Asset revisado vazio")
    if source["checkout.html"].count(b"__CHECKOUT_CONFIG__") != 1:
        raise RuntimeError("HTML revisado sem marcador da configuração")
    with (ROOT / "publicacoes/.receber.lock").open("a") as receiving, \
            (ROOT / "publicacoes/.ativacao.lock").open("a") as activation:
        fcntl.flock(receiving, fcntl.LOCK_EX)
        fcntl.flock(activation, fcntl.LOCK_EX)
        assert_frozen()
        assert_clone()
        owners = {name: regular(DEST / name) for name in ASSETS}
        originals = {name: (DEST / name).read_bytes() for name in ASSETS}
        if originals == source:
            http = prove(source)
            print(json.dumps({"publicado": True, "alteracoes": 0, "motivo": "assets já presentes", "http": http}))
            return
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = TASK / "backups-assets-pix" / (stamp + "-" + str(os.getpid()))
        backup_assets(backup, originals, owners)
        changed = []
        try:
            for name in ASSETS:
                if source[name] != originals[name]:
                    changed.append(name)
                    atomic(DEST / name, source[name], owners[name])
            http = prove(source)
            assert_frozen()
            print(json.dumps({"publicado": True, "assets": changed, "backup_privado": str(backup),
                              "http": http, "bancos_restaurados": False}, ensure_ascii=False))
        except BaseException:
            restored = True
            for name in reversed(changed):
                try:
                    atomic(DEST / name, originals[name], owners[name], regular(DEST / name).st_ino)
                except Exception:
                    restored = False
            if restored:
                try:
                    assert_frozen()
                except Exception:
                    restored = False
            print(json.dumps({"publicado": False, "assets_restaurados": restored,
                              "backup_privado": str(backup), "bancos_restaurados": False}, ensure_ascii=False))
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path)
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(InterruptedError("publicação interrompida")))
    run(args.source_root)


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        print(json.dumps({"publicado": False, "erro_tipo": type(error).__name__}))
        raise SystemExit(1)
