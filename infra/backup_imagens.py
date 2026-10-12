"""Reutiliza imagens imutáveis sem mudar dumps, código ou retenção."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess

from armazenamento_codigo import digest, image_archive, new_json, locked, sync_dir
from ensaio_entregas import _imagem_id_tar


def docker(*args):
    return subprocess.run(["docker", *args], capture_output=True, text=True,
                          timeout=900, check=True).stdout.strip()


def backup_image(reference, destination, store):
    identity = docker("image", "inspect", "--format", "{{.Id}}", reference)
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", identity):
        raise ValueError("identidade de imagem inválida")
    if reference.startswith("sha256:") and identity != reference:
        raise ValueError("imagem aprovada divergente")
    destination = Path(destination)
    result = image_archive(store, identity, destination, _imagem_id_tar)
    # A tag não identifica o conteúdo. Guardá-la separadamente permite
    # reconstruir o nome original mesmo se outra tag reutilizar o mesmo ID.
    record = {"format": "meshcraft-imagem-1", "image_id": identity,
              "reference": reference, "archive_sha256": result["sha256"], **result}
    new_json(destination.with_suffix(destination.suffix + ".json"), record)
    with locked(store) as root:
        usage = root/"uso.json"
        totals = json.loads(usage.read_text()) if usage.exists() else {}
        for key, value in {"exportacoes": int(not result["reused"]),
                           "reutilizacoes": int(result["reused"]),
                           "novos_bytes": result["new_bytes"], "bytes_evitados": result["saved_bytes"]}.items():
            totals[key] = totals.get(key, 0) + value
        totals["coletada_em"] = datetime.now(timezone.utc).isoformat()
        temp = root/".uso-novo"
        with temp.open("w") as stream:
            os.chmod(temp, 0o600)
            json.dump(totals, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, usage)
        sync_dir(root)
    return record


def restore_image(destination):
    """Restaura imagem e nome original; nunca restaura banco ou apaga arquivo."""
    destination = Path(destination)
    record = json.loads(destination.with_suffix(destination.suffix + ".json").read_text())
    if (record.get("format") != "meshcraft-imagem-1"
            or digest(destination) != record["archive_sha256"]
            or _imagem_id_tar(destination) != record["image_id"]):
        raise ValueError("backup de imagem divergente")
    docker("load", "-i", str(destination))
    if docker("image", "inspect", "--format", "{{.Id}}", record["image_id"]) != record["image_id"]:
        raise ValueError("recuperação de imagem divergente")
    if record["reference"] != record["image_id"]:
        docker("tag", record["image_id"], record["reference"])
    return record["image_id"]
