#!/usr/bin/env bash
# Sincroniza configuração sob trava e preserva pins de imagem, com recuperação provada.

set -eo pipefail

echo "SINCRONIZACAO-INICIADA: $(date -u +%Y%m%dT%H%M%SZ)"

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
cd "$RAIZ"
# Pasta de envio própria de cada sincronização (o publicador da VPS cria uma por vez).
STAGING="${STAGING:-infra.new}"
case "$STAGING" in infra.new|infra.new.[A-Za-z0-9_-]*) ;; *) echo "ERRO: STAGING invalido; use infra.new ou infra.new.<id>." >&2; exit 1 ;; esac
if [ -f "$RAIZ/publicacoes/imagens.json" ]; then
  export COMPOSE_FILE="$RAIZ/docker-compose.yml:$RAIZ/publicacoes/imagens.json"
fi

conferir_publicacao_admin() {
  python3 - "$RAIZ/publicacoes-candidatos/admin.json" "$RAIZ/.env" <<'PY'
import json
import re
from pathlib import Path
import sys

estado, ambiente = map(Path, sys.argv[1:])
try:
    estado.lstat()
except FileNotFoundError:
    raise SystemExit(0)
except OSError as erro:
    print(f"ERRO: nao li o estado duravel da publicacao admin: {erro}. Confira permissoes antes de repetir.", file=sys.stderr)
    raise SystemExit(1)
try:
    if estado.is_symlink():
        raise ValueError("estado duravel nao pode ser link")
    dado = json.loads(estado.read_text(encoding="utf-8"))
    campos = {"estado", "candidato", "digest", "imagem_id", "anterior", "anterior_digest", "aceite_funcional"}
    if not isinstance(dado, dict) or set(dado) != campos:
        raise ValueError("estrutura inesperada")
    if dado["estado"] not in {"autorizada", "incerta", "publicada", "falhou"}:
        raise ValueError("estado desconhecido")
    if any(not isinstance(dado[chave], str) or not dado[chave]
           for chave in ("candidato", "digest", "imagem_id", "anterior_digest")):
        raise ValueError("identidade de imagem incompleta")
    if not isinstance(dado["anterior"], dict):
        raise ValueError("mapa de imagens anteriores invalido")
    if dado["estado"] in {"autorizada", "incerta"}:
        raise ValueError("publicacao admin autorizada ou incerta em andamento")
    if dado["aceite_funcional"] not in {"pendente", "conferido"}:
        raise ValueError("aceite funcional desconhecido")
    if dado["estado"] == "publicada" and dado["aceite_funcional"] == "pendente":
        raise ValueError("publicacao admin aguarda aceite funcional")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", dado["digest"]):
        raise ValueError("digest publicado invalido")
    prefixo = "ghcr.io/abundanciabr/plataforma-admin@"
    if not re.fullmatch(re.escape(prefixo) + r"sha256:[0-9a-f]{64}", dado["anterior_digest"]):
        raise ValueError("digest anterior invalido")
    pin_esperado = (prefixo + dado["digest"] if dado["estado"] == "publicada"
                    else dado["anterior_digest"])
    pinos = [linha.removeprefix("ADMIN_IMAGE=") for linha in ambiente.read_text(encoding="utf-8").splitlines()
             if linha.startswith("ADMIN_IMAGE=")]
    if pinos != [pin_esperado]:
        raise ValueError("ADMIN_IMAGE nao corresponde ao estado duravel")
except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as erro:
    print(f"ERRO: publicacao admin nao permite sincronizar: {erro}. Confira o estado duravel e o pin antes de repetir.", file=sys.stderr)
    raise SystemExit(1)
PY
}
conferir_publicacao_admin

for ARQUIVO in docker-compose.yml sites.json sincronizar_sites.py provisionar-usuario-ponte.sh instalar-provisionador-usuario-ponte.sh; do
  [ -f "${STAGING}/$ARQUIVO" ] || { echo "ERRO: ${STAGING}/$ARQUIVO ausente; reenviar o staging pelo deploy-infra antes de repetir." >&2; exit 1; }
done
[ -d ${STAGING}/traefik ] || { echo "ERRO: ${STAGING}/traefik ausente; reenviar o staging pelo deploy-infra antes de repetir." >&2; exit 1; }
bash -n ${STAGING}/provisionar-usuario-ponte.sh ${STAGING}/instalar-provisionador-usuario-ponte.sh || {
  echo "ERRO: roteiro da ponte incompleto ou invalido no staging; corrija o PR e reenvie ${STAGING}." >&2; exit 1;
}
python3 -m json.tool ${STAGING}/sites.json >/dev/null || {
  echo "ERRO: sites.json invalido em ${STAGING}; NADA foi trocado. Corrija o PR e reenvie." >&2; exit 1;
}
for CHAVE in ALUNOS_API_TOKEN TOKEN_CATALOGO; do
  VALOR=$(grep -m1 "^$CHAVE=" env/admin.env | cut -d= -f2-) || VALOR=""
  if [ -z "$VALOR" ]; then
    echo "ERRO: $CHAVE ausente em /opt/plataforma/env/admin.env — a entrada privada nao pode nascer sem ele. NADA foi trocado."
    exit 1
  fi
  export "$CHAVE=$VALOR"
done
unset VALOR

if ! docker compose --project-directory "$RAIZ" -f "$RAIZ/${STAGING}/docker-compose.yml" config --quiet; then
  echo "ERRO: compose novo reprovou ainda em ${STAGING}; nenhuma mutacao root ou troca foi iniciada. Corrija o PR e reenvie." >&2
  exit 1
fi
STAGING_ANTES=$(tar -C ${STAGING} --sort=name -cf - . | sha256sum | cut -d' ' -f1)

PROVISIONADOR_DA_PONTE=/usr/local/sbin/provisionar-usuario-ponte
PONTE_INSTALADA=0
if [ -e "$PROVISIONADOR_DA_PONTE" ]; then
  if [ ! -x "$PROVISIONADOR_DA_PONTE" ] || ! cmp -s "$PROVISIONADOR_DA_PONTE" ${STAGING}/provisionar-usuario-ponte.sh; then
    echo "ERRO: a copia root da ponte diverge do staging; ${STAGING} foi preservada." >&2
    echo "      No console root, confira o kit e rode: bash $RAIZ/${STAGING}/instalar-provisionador-usuario-ponte.sh $RAIZ/${STAGING}/provisionar-usuario-ponte.sh" >&2
    exit 1
  fi
  PONTE_INSTALADA=1
  sudo -n "$PROVISIONADOR_DA_PONTE"
else
  echo "PONTE: ainda nao ligada nesta VPS. A sincronizacao da infraestrutura segue normalmente."
  echo "       Para ligar no console root depois deste deploy:"
  echo "       bash $RAIZ/instalar-provisionador-usuario-ponte.sh $RAIZ/provisionar-usuario-ponte.sh"
fi

conferir_publicacao_admin
STAGING_AGORA=$(tar -C ${STAGING} --sort=name -cf - . | sha256sum | cut -d' ' -f1)
if [ "$STAGING_AGORA" != "$STAGING_ANTES" ]; then
  echo "ERRO: ${STAGING} mudou durante a fase root; NADA foi consumido. Reenvie o staging pelo deploy-infra." >&2
  exit 1
fi
if [ "$PONTE_INSTALADA" = 1 ]; then
  cmp -s "$PROVISIONADOR_DA_PONTE" ${STAGING}/provisionar-usuario-ponte.sh || {
    echo "ERRO: a copia root mudou antes da troca; ${STAGING} foi preservada. Confira o kit root e repita." >&2; exit 1;
  }
elif [ -e "$PROVISIONADOR_DA_PONTE" ]; then
  echo "ERRO: a copia root apareceu durante a fase root; ${STAGING} foi preservada. Confira o kit e repita." >&2
  exit 1
fi
if ! docker compose --project-directory "$RAIZ" -f "$RAIZ/${STAGING}/docker-compose.yml" config --quiet; then
  echo "ERRO: compose novo reprovou apos a fase root; nenhuma troca de infraestrutura foi iniciada. Confira a ponte e reenvie o staging." >&2
  exit 1
fi
unset STAGING_ANTES STAGING_AGORA PONTE_INSTALADA

ls ${STAGING}
rm -rf traefik.new
mv -f ${STAGING}/docker-compose.yml docker-compose.yml.new
mv ${STAGING}/traefik traefik.new
mv -f ${STAGING}/sites.json sites.json.new
mv -f ${STAGING}/sincronizar_sites.py sincronizar_sites.py.new
mv -f ${STAGING}/provisionar-usuario-ponte.sh provisionar-usuario-ponte.sh
mv -f ${STAGING}/instalar-provisionador-usuario-ponte.sh instalar-provisionador-usuario-ponte.sh
mv -f ${STAGING}/publicacao-local.py publicacao-local.py
rmdir ${STAGING}

if ! docker compose -f docker-compose.yml.new config --quiet; then
  echo "ERRO: o compose novo reprovou na validação — NADA foi trocado."
  echo "O material recusado ficou em docker-compose.yml.new e traefik.new/ para inspeção."
  exit 1
fi
if ! python3 -m json.tool sites.json.new >/dev/null; then
  echo "ERRO: sites.json novo não é JSON válido — NADA foi trocado."
  exit 1
fi

mkdir -p admin-dados
touch admin-dados/.permissao-deploy-teste
rm -f admin-dados/.permissao-deploy-teste

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
cp -a docker-compose.yml "docker-compose.yml.bak-$STAMP"
cp -a traefik "traefik.bak-$STAMP"
if [ -f sites.json ]; then cp -a sites.json "sites.json.bak-$STAMP"; fi
echo "Backup: docker-compose.yml.bak-$STAMP e traefik.bak-$STAMP"

TROCADO=0

restaurar_o_que_estava_no_ar() {
  TROCADO=0
  echo "VOLTA ATRAS AUTOMATICA: a troca deu errado, devolvendo o que estava no ar."
  cp -a "docker-compose.yml.bak-$STAMP" docker-compose.yml || return 1
  rm -rf traefik || return 1
  cp -a "traefik.bak-$STAMP" traefik || return 1
  if [ -f "sites.json.bak-$STAMP" ]; then cp -a "sites.json.bak-$STAMP" sites.json || return 1; fi
  docker compose up -d --wait --wait-timeout 180 || return 1
  docker compose up -d --wait --wait-timeout 180 --force-recreate traefik || return 1
  echo "── docker compose ps depois da volta atras ──"
  docker compose ps || return 1
  python3 "$RAIZ/publicacao-local.py" conferir-infra || return 1
  echo "VOLTA ATRAS CONCLUIDA: a plataforma esta com a configuracao anterior."
}

# O trap cobre tambem a falha que ninguem previu, e nao so os dois `if` abaixo.
trap 'CODIGO=$?; if [ "$CODIGO" -ne 0 ] && [ "$TROCADO" = 1 ]; then if ! restaurar_o_que_estava_no_ar; then echo "RECUPERACAO-TERMINAL: infra falhou; tentativa encerrada, diagnostique configuração, rede e disco. Banco preservado." >&2; exit 2; fi; fi; exit $CODIGO' EXIT

TROCADO=1
mv -f docker-compose.yml.new docker-compose.yml
rm -rf traefik
mv traefik.new traefik
mv -f sites.json.new sites.json
mv -f sincronizar_sites.py.new sincronizar_sites.py
TROCADO=1
docker compose up -d

if ! diff -r "traefik.bak-$STAMP" traefik >/dev/null; then
  echo "traefik/ mudou — recriando o container para o bind mount enxergar os arquivos novos"
  docker compose up -d --force-recreate traefik
fi

sleep 20
ESPERADOS=$(docker compose config --services | sort)
RODANDO=$(docker compose ps --services --status running | sort)
echo "── docker compose ps (evidência do run) ──"
docker compose ps
if [ "$ESPERADOS" != "$RODANDO" ]; then
  echo "ERRO: divergência entre o compose e o que está em estado running."
  echo "Declarados: $(printf '%s' "$ESPERADOS" | tr '\n' ' ')"
  echo "Rodando:    $(printf '%s' "$RODANDO" | tr '\n' ' ')"
  FALHOS=""
  for s in $ESPERADOS; do
    if ! printf '%s\n' "$RODANDO" | grep -qx -- "$s"; then
      FALHOS="$FALHOS $s"
    fi
  done
  if [ -n "$FALHOS" ]; then
    echo "── logs (tail 60) dos serviços não-rodando:$FALHOS ──"
    docker compose logs --tail 60 $FALHOS
  fi
  exit 1
fi
echo "OK: infra sincronizada — todos os serviços declarados estão rodando."

docker compose exec -T -e SITES_JSON="$(cat sites.json)" catalogo python manage.py shell -c "$(cat sincronizar_sites.py)"
for H in $(python3 -c "import json; print(' '.join(s['host'] for s in json.load(open('sites.json'))['sites']))"); do
  CODIGO=000
  for _ in 1 2 3 4 5 6 7 8; do
    CODIGO=$(curl -sk -L --max-redirs 3 --resolve "$H:443:127.0.0.1" --resolve "$H:80:127.0.0.1" -o /dev/null -w '%{http_code}' "https://$H/") || CODIGO=000
    if [ "$CODIGO" = "200" ]; then break; fi
    sleep 10
  done
  if [ "$CODIGO" != "200" ]; then
    echo "ERRO: a raiz de $H terminou em $CODIGO (esperava 200 ao seguir o redirecionamento) — cadastro convergiu mas o site não serve."
    exit 1
  fi
  echo "OK: $H serve 200 na raiz (seguindo redirecionamento; smoke por dentro da VPS)"
done
echo "OK: sites do sites.json cadastrados/convergidos e provados."

echo "── sonda da entrada privada (127.0.0.1:8443) ──"
PERMITIDOS="/alunos/api/alunos/pre-matriculas?status=aguardando
/alunos/api/alunos/pre-matriculas?status=recusada
/alunos/api/alunos/matriculas
/catalogo/api/catalogo/produtos"
printf '%s
' "$PERMITIDOS" | while IFS= read -r CAMINHO; do
  [ -n "$CAMINHO" ] || continue
  CODIGO=000
  for _ in 1 2 3 4 5 6; do
    CODIGO=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:8443$CAMINHO") || CODIGO=000
    if [ "$CODIGO" = "200" ]; then break; fi
    sleep 5
  done
  if [ "$CODIGO" != "200" ]; then
    echo "ERRO: a entrada privada respondeu $CODIGO em $CAMINHO (esperava 200)."
    exit 1
  fi
  echo "OK: 200 em $CAMINHO"
done || exit 1

recusar() {
  ROTULO=$1
  shift
  CODIGO=$(curl -s -o /dev/null -w '%{http_code}' "$@") || CODIGO=000
  if [ "$CODIGO" != "404" ]; then
    echo "ERRO: a entrada privada respondeu $CODIGO em $ROTULO — o que nao esta na lista tem de receber 404."
    exit 1
  fi
  echo "OK: 404 em $ROTULO"
}

recusar "POST na lista de matriculas" -X POST "http://127.0.0.1:8443/alunos/api/alunos/matriculas"
recusar "caminho vizinho de matriculas" "http://127.0.0.1:8443/alunos/api/alunos/matriculas/1"
recusar "pre-matriculas sem o status permitido" "http://127.0.0.1:8443/alunos/api/alunos/pre-matriculas"
recusar "pre-matriculas com status fora da lista" "http://127.0.0.1:8443/alunos/api/alunos/pre-matriculas?status=ativa"
recusar "escrita no catalogo" -X POST "http://127.0.0.1:8443/catalogo/api/catalogo/produtos"
echo "OK: entrada privada com as quatro leituras servindo e o resto recusado."

python3 "$RAIZ/publicacao-local.py" conferir-infra
echo "SINCRONIZACAO-CONCLUIDA: $STAMP"
