#!/bin/sh
# Atalho estável na VPS (/opt/plataforma/bin/plataforma): roda infra/publicar.py da main recebida.
# Uso: plataforma receber | publicar CELULA SHA | recuperar CELULA | vigiar | estado | operar ...
set -eu
RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
REPO="$RAIZ/codigo/repo.git"
FERRAMENTAS="$RAIZ/codigo/ferramentas"
mkdir -p "$FERRAMENTAS"
if [ ! -d "$REPO" ]; then
  git clone --quiet --bare https://github.com/abundanciabr/sitesdoreino.git "$REPO"
fi
case "${1:-}" in
  receber|publicar)
    git -C "$REPO" fetch --quiet origin +refs/heads/main:refs/heads/main ;;
esac
SHA=$(git -C "$REPO" rev-parse refs/heads/main)
if [ ! -d "$FERRAMENTAS/$SHA" ]; then
  NOVA=$(mktemp -d "$FERRAMENTAS/.nova.XXXXXX")
  # services/admin/Dockerfile só marca a raiz para ci/_nucleo.py.
  git -C "$REPO" archive "$SHA" infra ci e2e celulas.yml services/admin/Dockerfile | tar -x -C "$NOVA"
  mv -T "$NOVA" "$FERRAMENTAS/$SHA" 2>/dev/null || rm -rf "$NOVA"
  ln -sfn "$SHA" "$FERRAMENTAS/.atual.$$" && mv -T "$FERRAMENTAS/.atual.$$" "$FERRAMENTAS/atual"
  find "$FERRAMENTAS" -mindepth 1 -maxdepth 1 -name '[0-9a-f]*' -mmin +1440 ! -name "$SHA" -exec rm -rf {} +
fi
exec python3 "$FERRAMENTAS/$SHA/infra/publicar.py" "$@"
