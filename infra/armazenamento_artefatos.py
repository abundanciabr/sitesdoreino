"""Armazenamento de artefatos *novos* com restauração independente do cache.

O chamador deve concluir a escrita da árvore antes de consolidá-la. Nenhuma API
deste módulo recebe um destino existente para snapshots ou exportações.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

if os.name == "posix":
    import fcntl


_SHA = re.compile(r"^[0-9a-f]{64}$")


def _no_symlink_ancestors(path: Path) -> None:
    current = path.absolute()
    while True:
        if current.is_symlink():
            raise ValueError(f"caminho contém link simbólico: {current}")
        if current == current.parent:
            break
        current = current.parent


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _private_cache(root: Path) -> Path:
    root = Path(root)
    _no_symlink_ancestors(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not stat.S_ISDIR(root.lstat().st_mode) or (os.name == "posix" and root.stat().st_mode & 0o077):
        raise ValueError("cache deve ser diretório privado (0700)")
    return root


def _tmp(parent: Path) -> Path:
    fd, name = tempfile.mkstemp(prefix=".artefato-", dir=parent)
    os.close(fd)
    return Path(name)


def _copy_verified(source: Path, target: Path, digest: str, mode: int) -> None:
    try:
        with source.open("rb") as entrada, target.open("wb") as saida:
            shutil.copyfileobj(entrada, saida, 1024 * 1024)
        if _digest(target) != digest:
            raise ValueError(f"fonte mudou durante a cópia: {source}")
        target.chmod(mode)
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def _object(source: Path, directory: Path, key: str, digest: str,
            mode: int, uid: int | None = None, gid: int | None = None,
            mtime_ns: int | None = None) -> tuple[Path, bool]:
    if directory.is_symlink():
        raise ValueError("diretório do cache é link")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    obj = directory / key
    if obj.is_symlink():
        raise ValueError(f"objeto do cache é link: {obj}")
    if not obj.exists():
        temp = _tmp(directory)
        try:
            _copy_verified(source, temp, digest, mode)
            if (uid is not None and gid is not None and hasattr(os, "chown") and
                    (temp.stat().st_uid, temp.stat().st_gid) != (uid, gid)):
                os.chown(temp, uid, gid)
            if mtime_ns is not None:
                os.utime(temp, ns=(mtime_ns, mtime_ns))
            try:
                os.link(temp, obj)
                created = True
            except FileExistsError:
                created = False
        finally:
            temp.unlink(missing_ok=True)
    else:
        created = False
    meta = obj.lstat()
    if (not stat.S_ISREG(meta.st_mode) or _digest(obj) != digest or
            stat.S_IMODE(meta.st_mode) != mode or meta.st_size != source.stat().st_size or
            (uid is not None and meta.st_uid != uid) or
            (gid is not None and meta.st_gid != gid) or
            (mtime_ns is not None and meta.st_mtime_ns != mtime_ns)):
        raise ValueError(f"objeto do cache inválido: {obj}")
    return obj, created


def _walk_regular(tree: Path) -> list[Path]:
    if tree.is_symlink() or not tree.is_dir():
        raise ValueError("árvore nova inválida")
    files = []
    for base, dirs, names in os.walk(tree, followlinks=False):
        for name in dirs + names:
            path = Path(base) / name
            typ = path.lstat().st_mode
            if stat.S_ISLNK(typ):
                raise ValueError(f"árvore contém link simbólico: {path}")
            if not (stat.S_ISDIR(typ) or stat.S_ISREG(typ)):
                raise ValueError(f"tipo de arquivo não suportado: {path}")
        files.extend(Path(base) / n for n in names)
    return files


def consolidar_arvore_nova(tree: Path, cache_root: Path) -> dict:
    """Deduplica uma árvore nova finalizada; recusa links e cache corrompido.

O inode de cada arquivo na árvore passa a apontar para o objeto imutável por
convenção. Seu tamanho, conteúdo, modo, uid, gid e mtime permanecem iguais.
"""
    tree = Path(tree)
    files = _walk_regular(tree)  # valida tudo antes da primeira alteração
    cache = _private_cache(cache_root) / "arvores"
    stats = {"arquivos": 0, "objetos_criados": 0, "links_criados": 0,
             "bytes_logicos": 0, "bytes_economizados_estimados": 0}
    for path in files:
        meta = path.lstat()
        mode = stat.S_IMODE(meta.st_mode)
        digest = _digest(path)
        key = f"{digest}-{mode:04o}-{meta.st_uid}-{meta.st_gid}-{meta.st_mtime_ns}"
        obj, created = _object(path, cache, key, digest, mode, meta.st_uid, meta.st_gid,
                               meta.st_mtime_ns)
        stats["arquivos"] += 1
        stats["bytes_logicos"] += meta.st_size
        stats["objetos_criados"] += int(created)
        if path.stat().st_ino == obj.stat().st_ino and path.stat().st_dev == obj.stat().st_dev:
            continue
        temp = _tmp(path.parent)
        temp.unlink()
        try:
            os.link(obj, temp)
            # Garante que o arquivo finalizado não foi alterado depois da leitura.
            now = path.lstat()
            if (now.st_ino, now.st_dev, now.st_size) != (meta.st_ino, meta.st_dev, meta.st_size) or _digest(path) != digest:
                raise ValueError(f"árvore mudou durante consolidação: {path}")
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
        stats["links_criados"] += 1
        if not created:
            stats["bytes_economizados_estimados"] += meta.st_blocks * 512 if hasattr(meta, "st_blocks") else meta.st_size
    return stats


def _image_digest(image: str) -> str:
    if not isinstance(image, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise ValueError("imagem deve ser ID Docker imutável sha256:<64 hex>")
    return image[7:]


@contextmanager
def _image_lock(cache: Path, digest: str):
    """Serializa exportações do mesmo ID no Linux de produção."""
    lock = cache / (digest + ".lock")
    with lock.open("a+b") as stream:
        if os.name == "posix":
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "posix":
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _verify_image_tar(path: Path, expected: str) -> None:
    with tarfile.open(path, "r:") as tar:
        members = {item.name: item for item in tar.getmembers()}
        if len(members) != len(tar.getmembers()):
            raise ValueError("tar contém nomes duplicados")

        def read(name, digest=None, size=None, json_limit=False):
            item = members[name]
            if not item.isfile() or (size is not None and item.size != size):
                raise ValueError("membro inválido da imagem")
            if json_limit and item.size > 16 * 1024 * 1024:
                raise ValueError("metadado de imagem grande demais")
            h = hashlib.sha256()
            output = bytearray() if json_limit else None
            with tar.extractfile(item) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(chunk)
                    if output is not None:
                        output.extend(chunk)
            if digest is not None and h.hexdigest() != digest:
                raise ValueError("digest divergente em imagem")
            return bytes(output) if output is not None else None

        def js(name, digest=None, size=None):
            return json.loads(read(name, digest, size, True))

        def sha(value):
            if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
                raise ValueError("digest inválido em imagem")
            return value[7:]

        legacy_config = None
        if "manifest.json" in members:
            legacy = js("manifest.json")
            if not isinstance(legacy, list) or len(legacy) != 1:
                raise ValueError("manifesto Docker ambíguo")
            name = legacy[0]["Config"]
            if not isinstance(name, str) or not re.fullmatch(r"(?:blobs/sha256/)?[0-9a-f]{64}(?:\.json)?", name):
                raise ValueError("configuração Docker inválida")
            legacy_config = name.rsplit("/", 1)[-1].removesuffix(".json")
            if not isinstance(js(name, legacy_config), dict):
                raise ValueError("configuração Docker inválida")
        if "index.json" not in members:
            if legacy_config != expected:
                raise ValueError("imagem Docker não corresponde ao ID")
            return
        index = js("index.json")
        if (not isinstance(index, dict) or index.get("schemaVersion") != 2 or
                not isinstance(index.get("manifests"), list) or len(index["manifests"]) != 1):
            raise ValueError("índice OCI ambíguo")
        root = index["manifests"][0]
        if sha(root.get("digest")) != expected:
            raise ValueError("imagem OCI não corresponde ao ID")
        image_configs = []
        visited = set()
        index_types = {"application/vnd.oci.image.index.v1+json",
                       "application/vnd.docker.distribution.manifest.list.v2+json"}
        image_types = {"application/vnd.oci.image.manifest.v1+json",
                       "application/vnd.docker.distribution.manifest.v2+json"}

        def visit(desc, depth=0):
            if not isinstance(desc, dict) or depth > 4:
                raise ValueError("descritor OCI inválido")
            digest = sha(desc.get("digest"))
            size = desc.get("size")
            media = desc.get("mediaType")
            if (media not in index_types | image_types or type(size) is not int or
                    size < 0 or digest in visited):
                raise ValueError("descritor OCI inválido")
            visited.add(digest)
            doc = js("blobs/sha256/" + digest, digest, size)
            if not isinstance(doc, dict) or doc.get("schemaVersion") != 2:
                raise ValueError("manifesto OCI inválido")
            if media in index_types:
                children = doc.get("manifests")
                if not isinstance(children, list) or not children:
                    raise ValueError("índice OCI vazio")
                for child in children:
                    visit(child, depth + 1)
                return
            config = doc.get("config")
            layers = doc.get("layers")
            if not isinstance(config, dict) or not isinstance(layers, list):
                raise ValueError("manifesto OCI inválido")
            for part in [config, *layers]:
                if not isinstance(part, dict) or not isinstance(part.get("mediaType"), str):
                    raise ValueError("blob OCI inválido")
                part_digest = sha(part.get("digest"))
                part_size = part.get("size")
                if type(part_size) is not int or part_size < 0:
                    raise ValueError("tamanho de blob OCI inválido")
                name = "blobs/sha256/" + part_digest
                if part is config:
                    if not isinstance(js(name, part_digest, part_size), dict):
                        raise ValueError("configuração OCI inválida")
                else:
                    read(name, part_digest, part_size)
            platform = desc.get("platform", {})
            annotations = desc.get("annotations", {})
            attest = isinstance(annotations, dict) and annotations.get("vnd.docker.reference.type") == "attestation-manifest"
            unknown = isinstance(platform, dict) and platform.get("architecture") == "unknown" and platform.get("os") == "unknown"
            if not attest and not unknown:
                image_configs.append(config["digest"])

        visit(root)
        if len(image_configs) != 1 or (legacy_config and image_configs[0] != "sha256:" + legacy_config):
            raise ValueError("configuração OCI ambígua")


def exportar_imagem_nova(imagem: str, dest: Path, cache_root: Path,
                        registro: dict | None = None) -> dict:
    """Exporta um ID de imagem verificado; repetições criam apenas hardlinks."""
    digest = _image_digest(imagem)
    dest = Path(dest)
    _no_symlink_ancestors(dest.parent)
    if dest.exists() or dest.is_symlink():
        raise FileExistsError(dest)
    cache = _private_cache(cache_root) / "imagens"
    if cache.is_symlink():
        raise ValueError("diretório de imagens é link")
    cache.mkdir(mode=0o700, exist_ok=True)
    obj = cache / (digest + ".tar")
    sidecar = cache / (digest + ".sha256")
    with _image_lock(cache, digest):
        if obj.is_symlink() or sidecar.is_symlink():
            raise ValueError("imagem do cache é link")
        created = False
        if not obj.exists():
            temp = _tmp(cache)
            try:
                with temp.open("wb") as output:
                    subprocess.run(["docker", "save", imagem], stdout=output, check=True)
                _verify_image_tar(temp, digest)
                tar_digest = _digest(temp)
                temp.chmod(0o400)
                side_temp = _tmp(cache)
                try:
                    side_temp.write_text(tar_digest, encoding="ascii")
                    side_temp.chmod(0o400)
                    os.replace(side_temp, sidecar)
                finally:
                    side_temp.unlink(missing_ok=True)
                os.link(temp, obj)
                created = True
            finally:
                temp.unlink(missing_ok=True)
        if (not stat.S_ISREG(obj.lstat().st_mode) or
                stat.S_IMODE(obj.stat().st_mode) != 0o400 or
                not sidecar.is_file() or
                _digest(obj) != sidecar.read_text(encoding="ascii")):
            raise ValueError("imagem em cache inválida")
        _verify_image_tar(obj, digest)
        os.link(obj, dest)  # exclusividade atômica; jamais substitui destino
    result = {"imagem": imagem, "bytes": obj.stat().st_size, "exportacao_nova": created,
              "bytes_economizados_estimados": 0 if created else obj.stat().st_size}
    if registro is not None:
        registro.update(result)
    return result


def _arcname(name: str) -> str:
    posix = PurePosixPath(name)
    if (not name or name.startswith("/") or "\\" in name or
            any(p in ("", ".", "..") for p in name.split("/")) or
            posix.as_posix() != name):
        raise ValueError(f"nome inseguro no snapshot: {name}")
    return name


def criar_snapshot(paths: list[tuple[Path, str]], destino_novo: Path,
                   cache_root: Path) -> dict:
    """Cria snapshot de arquivos/diretórios, independente do cache depois de pronto."""
    dest = Path(destino_novo)
    _no_symlink_ancestors(dest.parent)
    if dest.exists() or dest.is_symlink():
        raise FileExistsError(dest)
    cache = _private_cache(cache_root) / "snapshots"
    seen = set()
    entries = []
    sources = []
    for source, arc in paths:
        source = Path(source)
        _arcname(arc)
        if source.is_symlink():
            raise ValueError("raiz de origem é link simbólico")
        if not source.exists():
            raise FileNotFoundError(source)
        nodes = [source]
        if source.is_dir():
            nodes += sorted(source.rglob("*"))
        for node in nodes:
            rel = "/".join((arc, *node.relative_to(source).parts)) if node != source else arc
            _arcname(rel)
            if rel in seen:
                raise ValueError(f"nome repetido: {rel}")
            seen.add(rel)
            sources.append((node, rel))
    dest.mkdir(mode=0o700, parents=False)
    objects = dest / "objetos"
    objects.mkdir(mode=0o700)
    try:
        for source, rel in sources:
            meta = source.lstat()
            entry = {"path": rel, "mode": stat.S_IMODE(meta.st_mode), "uid": meta.st_uid,
                     "gid": meta.st_gid, "mtime_ns": meta.st_mtime_ns}
            if stat.S_ISDIR(meta.st_mode):
                entry["type"] = "dir"
            elif stat.S_ISLNK(meta.st_mode):
                entry.update(type="symlink", target=os.readlink(source))
            elif stat.S_ISREG(meta.st_mode):
                digest = _digest(source)
                obj, _ = _object(source, cache, digest, digest, 0o400)
                snapshot_obj = objects / digest
                if not snapshot_obj.exists():
                    os.link(obj, snapshot_obj)
                entry.update(type="file", sha256=digest, size=meta.st_size)
            else:
                raise ValueError(f"tipo não suportado: {source}")
            entries.append(entry)
        shutil.copyfile(Path(__file__), dest / "restaurar.py")
        (dest / "restaurar.py").chmod(0o500)
        manifest = {"formato": 2, "entradas": entries}
        temp = _tmp(dest)
        try:
            temp.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True), encoding="utf-8")
            temp.chmod(0o400)
            os.replace(temp, dest / "manifesto.json")
        finally:
            temp.unlink(missing_ok=True)
    except BaseException:
        shutil.rmtree(dest)
        raise
    return {"entradas": len(entries), "objetos": len(list(objects.iterdir())),
            "bytes_logicos": sum(x.get("size", 0) for x in entries)}


def verificar_snapshot(snapshot: Path) -> dict:
    snapshot = Path(snapshot)
    manifest = json.loads((snapshot / "manifesto.json").read_text(encoding="utf-8"))
    if manifest.get("formato") != 2 or not isinstance(manifest.get("entradas"), list):
        raise ValueError("formato de snapshot inválido")
    seen = set()
    for entry in manifest["entradas"]:
        rel = _arcname(entry["path"])
        if rel in seen:
            raise ValueError("nome repetido no snapshot")
        seen.add(rel)
        typ = entry["type"]
        if typ == "file":
            digest = entry["sha256"]
            if not _SHA.fullmatch(digest):
                raise ValueError("SHA inválido")
            obj = snapshot / "objetos" / digest
            if obj.is_symlink() or not stat.S_ISREG(obj.lstat().st_mode):
                raise ValueError("objeto ausente ou link")
            if obj.stat().st_size != entry["size"] or _digest(obj) != digest:
                raise ValueError("objeto corrompido")
        elif typ == "symlink":
            if not isinstance(entry.get("target"), str):
                raise ValueError("link inválido")
        elif typ != "dir":
            raise ValueError("tipo inválido")
    return manifest


def restaurar_snapshot(snapshot: Path, destino_novo: Path) -> dict:
    """Restaura em pasta inexistente. Confere todos os objetos antes de escrever."""
    manifest = verificar_snapshot(snapshot)
    dest = Path(destino_novo)
    if dest.exists() or dest.is_symlink():
        raise FileExistsError(dest)
    _no_symlink_ancestors(dest.parent)
    dest.mkdir(mode=0o700)
    dirs = []
    try:
        for entry in sorted(manifest["entradas"], key=lambda e: e["path"].count("/")):
            rel = entry["path"]
            path = dest.joinpath(*rel.split("/"))
            if any(p.is_symlink() for p in list(path.parents)[:-1] if p != dest.parent):
                raise ValueError("pai no snapshot é link simbólico")
            typ = entry["type"]
            if typ == "dir":
                path.mkdir(mode=0o700, parents=True, exist_ok=True)
                dirs.append((path, entry))
                continue
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if path.exists() or path.is_symlink():
                raise ValueError("conflito de nomes no snapshot")
            if typ == "file":
                source = Path(snapshot) / "objetos" / entry["sha256"]
                shutil.copyfile(source, path, follow_symlinks=False)
                if _digest(path) != entry["sha256"]:
                    raise ValueError("objeto mudou durante restauração")
                _metadata(path, entry)
            else:
                path.symlink_to(entry["target"])
                _metadata(path, entry, symlink=True)
        for path, entry in reversed(dirs):
            _metadata(path, entry)
    except BaseException:
        shutil.rmtree(dest)
        raise
    return {"entradas": len(manifest["entradas"]), "destino": str(dest)}


def _metadata(path: Path, entry: dict, symlink: bool = False) -> None:
    if hasattr(os, "chown") and getattr(os, "geteuid", lambda: 1)() == 0:
        os.chown(path, entry["uid"], entry["gid"], follow_symlinks=not symlink)
    if not symlink:
        path.chmod(entry["mode"])
    os.utime(path, ns=(entry["mtime_ns"], entry["mtime_ns"]), follow_symlinks=not symlink)


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "restaurar":
        sys.exit("uso: python restaurar.py restaurar SNAPSHOT DESTINO_NOVO")
    print(json.dumps(restaurar_snapshot(Path(sys.argv[2]), Path(sys.argv[3]))))
