# Exclusao comum no receptor; o descritor herdado precisa apontar ao mesmo inode.
TRAVA_PUBLICACAO="${PLATAFORMA_DIR:-/opt/plataforma}/.publicacao.lock"
command -v flock >/dev/null 2>&1 || { echo "ERRO: flock ausente; instale util-linux na VPS antes de publicar." >&2; exit 1; }
if ! [ "$TRAVA_PUBLICACAO" -ef "/proc/$$/fd/8" ]; then
  if [ ! -f "$TRAVA_PUBLICACAO" ]; then
    (umask 022; : >>"$TRAVA_PUBLICACAO") || { echo "ERRO: nao criei a trava comum; confira permissoes da plataforma." >&2; exit 1; }
  fi
  exec 8<"$TRAVA_PUBLICACAO" || { echo "ERRO: nao li a trava comum; o dono deve liberar leitura sem remover o arquivo." >&2; exit 1; }
fi
flock --exclusive 8 || { echo "ERRO: nao obtive a trava comum; confira o mutador em andamento antes de repetir." >&2; exit 1; }
unset TRAVA_PUBLICACAO
