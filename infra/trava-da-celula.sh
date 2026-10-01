# Publicacao de celula: convive com outras celulas, exclui a mesma celula e espera os mutadores comuns.
TRAVA_PUBLICACAO="${PLATAFORMA_DIR:-/opt/plataforma}/.publicacao.lock"
command -v flock >/dev/null 2>&1 || { echo "ERRO: flock ausente; instale util-linux na VPS antes de publicar." >&2; exit 1; }
case "${CELULA:-}" in ''|[!a-z]*|*[!a-z0-9_]*) echo "PAROU POR SEGURANÇA: a variável CELULA chegou vazia ou inválida." >&2; exit 1 ;; esac
if ! [ "$TRAVA_PUBLICACAO" -ef "/proc/$$/fd/8" ]; then
  if [ ! -f "$TRAVA_PUBLICACAO" ]; then
    (umask 022; : >>"$TRAVA_PUBLICACAO") || { echo "ERRO: nao criei a trava comum; confira permissoes da plataforma." >&2; exit 1; }
  fi
  exec 8<"$TRAVA_PUBLICACAO" || { echo "ERRO: nao li a trava comum; o dono deve liberar leitura sem remover o arquivo." >&2; exit 1; }
fi
flock --shared 8 || { echo "ERRO: nao obtive a trava comum; confira o mutador em andamento antes de repetir." >&2; exit 1; }
TRAVA_CELULA="${PLATAFORMA_DIR:-/opt/plataforma}/.publicacao-$CELULA.lock"
if ! [ "$TRAVA_CELULA" -ef "/proc/$$/fd/9" ]; then
  if [ ! -f "$TRAVA_CELULA" ]; then
    (umask 022; : >>"$TRAVA_CELULA") || { echo "ERRO: nao criei a trava da celula; confira permissoes da plataforma." >&2; exit 1; }
  fi
  exec 9<"$TRAVA_CELULA" || { echo "ERRO: nao li a trava da celula." >&2; exit 1; }
fi
flock --exclusive 9 || { echo "ERRO: nao obtive a trava da celula; confira a publicacao em andamento antes de repetir." >&2; exit 1; }
unset TRAVA_PUBLICACAO TRAVA_CELULA
