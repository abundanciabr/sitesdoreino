#!/usr/bin/env bash
set -eu

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
cd "$RAIZ" || { echo "ERRO: plataforma ausente; confira a instalação oficial." >&2; exit 1; }
TRAVA_PUBLICACAO="$RAIZ/.publicacao.lock"
command -v flock >/dev/null 2>&1 || { echo "ERRO: flock ausente; instale util-linux antes de consultar." >&2; exit 1; }
if ! [ "$TRAVA_PUBLICACAO" -ef "/proc/$$/fd/8" ]; then
  if [ ! -f "$TRAVA_PUBLICACAO" ]; then
    (umask 022; : >>"$TRAVA_PUBLICACAO") || { echo "ERRO: não criei a trava comum; confira permissões da plataforma." >&2; exit 1; }
  fi
  exec 8<"$TRAVA_PUBLICACAO" || { echo "ERRO: não li a trava comum; confira permissões." >&2; exit 1; }
fi
flock --exclusive 8 || { echo "ERRO: não obtive a trava comum; repita após o mutador terminar." >&2; exit 1; }

docker compose --env-file "$RAIZ/env/admin.env" exec -T \
  -e "COORTE=${COORTE:-}" -e "TRANSICAO=${TRANSICAO:-}" \
  -e "FASE=${FASE:-}" -e "NONCE=${NONCE:-}" admin python - <<'PY'
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def parar(mensagem):
    print("ERRO: " + mensagem, file=sys.stderr)
    raise SystemExit(1)


coorte = os.environ.get("COORTE", "")
transicao = os.environ.get("TRANSICAO", "")
fase = os.environ.get("FASE", "")
nonce = os.environ.get("NONCE", "")
token = os.environ.get("COORDENACAO_TRANSICIONADOR_TOKEN", "")
if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", coorte):
    parar("coorte inválida; informe o ID registrado no piloto.")
if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9-]{0,79}", transicao):
    parar("transição inválida; informe o ID da pausa vigente.")
if fase not in ("preparada", "ativa") or not re.fullmatch(r"[0-9a-f]{32}", nonce):
    parar("fase ou nonce inválido; o job principal deve gerar 16 bytes por consulta.")
if not token:
    parar("identidade transicionadora ausente; provisione-a no ambiente do admin.")
pedido = {
    "operacao": "consultar_transicao",
    "coorte": coorte,
    "transicao": transicao,
    "fase": fase,
    "nonce": nonce,
}
requisicao = Request(
    "http://127.0.0.1:8000/interno/coordenacao/epocas",
    data=json.dumps(pedido, separators=(",", ":")).encode(),
    headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    method="POST",
)
try:
    with urlopen(requisicao, timeout=10) as resposta:
        if resposta.status != 200:
            parar("API recusou a consulta; confira a coorte e a pausa antes de repetir.")
        bruto = resposta.read(8193)
    if len(bruto) > 8192:
        parar("resposta da API excedeu o contrato; mantenha a coorte pausada.")
    envelope = json.loads(bruto)
except HTTPError as erro:
    parar(f"API recusou a consulta (HTTP {erro.code}); confira papel, coorte e pausa.")
except (URLError, TimeoutError, OSError, ValueError):
    parar("API interna indisponível; mantenha a coorte pausada e repita a consulta.")
if not isinstance(envelope, dict) or set(envelope) != {"estado", "resultado"} or envelope["estado"] != "PASS":
    parar("resposta da API fora do contrato; mantenha a coorte pausada.")
resultado = envelope["resultado"]
campos = {
    "coorte", "epoca_atual", "epoca", "transicao", "pausada",
    "concessoes_invalidas", "watermark_sha256", "autoridade_sha256", "fase", "nonce",
}
if not isinstance(resultado, dict) or set(resultado) != campos:
    parar("estado da transição incompleto; mantenha a coorte pausada.")
if (
    resultado["coorte"] != coorte
    or resultado["transicao"] != transicao
    or resultado["fase"] != fase
    or resultado["nonce"] != nonce
    or resultado["pausada"] is not True
    or resultado["concessoes_invalidas"] is not True
    or type(resultado["epoca_atual"]) is not int
    or type(resultado["epoca"]) is not int
    or resultado["epoca_atual"] < 1
    or resultado["epoca"] != resultado["epoca_atual"] + (fase == "preparada")
    or not all(
        isinstance(resultado[campo], str) and re.fullmatch(r"[0-9a-f]{64}", resultado[campo])
        for campo in ("watermark_sha256", "autoridade_sha256")
    )
):
    parar("estado da transição divergiu; mantenha a coorte pausada.")
print(json.dumps(resultado, sort_keys=True, separators=(",", ":")))
PY
