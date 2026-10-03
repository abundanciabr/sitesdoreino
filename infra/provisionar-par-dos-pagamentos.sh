#!/usr/bin/env bash
# Liga apenas o par admin -> pagamentos. O segredo nasce e permanece na VPS.
set -euo pipefail

if [ "${BASH_SOURCE[0]}" != "$0" ]; then
  echo "Execute este roteiro com bash, sem source." >&2
  return 1
fi

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
cd "$RAIZ"
. "${RAIZ}/codigo/ferramentas/atual/infra/operacao-aplicacao.sh" 2>/dev/null || . "$(dirname "$0")/operacao-aplicacao.sh"

for arquivo in env/admin.env env/pagamentos.env; do
  [ -f "$arquivo" ] || { echo "Env ausente: $arquivo" >&2; exit 1; }
  [ -w "$(dirname "$arquivo")" ] || { echo "Pasta env sem escrita: $arquivo" >&2; exit 1; }
done

ler() { sed -n "s/^$2=//p" "$1" | tail -1; }
TOKEN="$(ler env/pagamentos.env TOKENS_ACEITOS_ADMIN)"
if [ -z "$TOKEN" ]; then TOKEN="$(openssl rand -hex 32)"; fi
[ "${#TOKEN}" -ge 32 ] || { echo "Token anterior curto; nada alterado" >&2; exit 1; }

gravar() {
  local arquivo="$1" chave="$2" valor="$3"
  [ "$(ler "$arquivo" "$chave")" = "$valor" ] && return 0
  # O valor vai por stdin, nunca por argumento de processo nem por stdout.
  python3 - "$arquivo" "$chave" 3<<<"$valor" <<'PY'
import os, pathlib, shutil, sys, tempfile
arquivo = pathlib.Path(sys.argv[1])
chave = sys.argv[2]
valor = os.fdopen(3).read().rstrip('\n')
linhas = arquivo.read_text().splitlines()
linhas = [linha for linha in linhas if not linha.startswith(chave + '=')]
linhas.append(chave + '=' + valor)
stat = arquivo.stat()
backup = arquivo.with_name(arquivo.name + '.bak-par-pagamentos')
if not backup.exists():
    backup_fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with arquivo.open('rb') as origem, os.fdopen(backup_fd, 'wb') as destino:
            shutil.copyfileobj(origem, destino)
    except BaseException:
        backup.unlink(missing_ok=True)
        raise
os.chmod(backup, 0o600)
fd, nome = tempfile.mkstemp(prefix='.par-pagamentos-', dir=arquivo.parent)
try:
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'w') as saida:
        saida.write('\n'.join(linhas) + '\n')
    if os.geteuid() == 0:
        os.chown(nome, stat.st_uid, stat.st_gid)
    os.replace(nome, arquivo)
    os.chmod(arquivo, 0o600)
finally:
    if os.path.exists(nome):
        os.unlink(nome)
PY
}

gravar env/pagamentos.env TOKENS_ACEITOS_ADMIN "$TOKEN"
gravar env/admin.env PAGAMENTOS_API_URL 'http://pagamentos:8000/api/pagamentos'
gravar env/admin.env PAGAMENTOS_API_TOKEN "$TOKEN"
unset TOKEN

recarregar_servicos "provisionar-par-dos-pagamentos.sh"
echo 'Par admin → pagamentos configurado e aplicação recarregada.'
