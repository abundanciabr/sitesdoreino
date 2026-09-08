#!/usr/bin/env bash
# Publica painel ou fila da area admin sem rebuild nem restart da celula.
set -eu

if (set -o pipefail) 2>/dev/null; then set -o pipefail; fi

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
cd "$RAIZ"

parar() {
  echo
  echo "PAROU POR SEGURANCA: $1"
  echo
  echo "O QUE ESTA NO AR AGORA: o ponteiro ativo nao foi trocado. A versao"
  echo "anterior dos dados continua sendo lida pela admin."
  echo "O QUE FAZER: corrija o payload indicado acima e rode a publicacao de novo."
  exit 1
}

TIPO="${ADMIN_DADOS_TIPO:-}"
SHA="${ADMIN_DADOS_SHA:-}"
RUN_NUMBER="${ADMIN_DADOS_RUN_NUMBER:-}"

case "$TIPO" in
  painel|fila) ;;
  *) parar "ADMIN_DADOS_TIPO precisa ser 'painel' ou 'fila'." ;;
esac
case "$SHA" in
  ?????*) ;;
  *) parar "ADMIN_DADOS_SHA chegou vazio ou curto demais." ;;
esac
case "$RUN_NUMBER" in
  ''|*[!0-9]*) parar "ADMIN_DADOS_RUN_NUMBER precisa ser numero." ;;
esac

ORIGEM="$RAIZ/admin-dados.new/$SHA/$TIPO"
VALIDADOR="$RAIZ/admin-dados.new/$SHA/publicador_dados_admin.py"
RAIZ_DADOS="$RAIZ/admin-dados"
ATIVO="$RAIZ_DADOS/${TIPO}_ativo"
DESTINO="$RAIZ_DADOS/${TIPO}_${RUN_NUMBER}_${SHA}"

test -d "$ORIGEM" || parar "o payload $TIPO nao chegou em $ORIGEM."
test -f "$ORIGEM/admin-dados.json" || parar "o manifesto admin-dados.json nao veio em $ORIGEM."
test -f "$VALIDADOR" || parar "o validador da publicacao nao veio em $VALIDADOR."

mkdir -p "$RAIZ_DADOS"
command -v flock >/dev/null 2>&1 || parar "flock nao esta disponivel na VPS."
exec 9>"$RAIZ_DADOS/.${TIPO}.lock"
flock 9 || parar "nao consegui obter a trava de publicacao $TIPO."

ACAO=$(python3 "$VALIDADOR" \
  --tipo "$TIPO" \
  --origem "$ORIGEM" \
  --ativo "$ATIVO" \
  --sha "$SHA" \
  --run-number "$RUN_NUMBER") || parar "validacao do payload $TIPO falhou."

if [ "$ACAO" = "ignorar" ]; then
  echo "ADMIN-DADOS-ANTIGO-IGNORADO: tipo=$TIPO sha=$SHA run=$RUN_NUMBER"
  exit 0
fi

PARCIAL="$DESTINO.parcial"
LINK_NOVO="$RAIZ_DADOS/.${TIPO}_ativo.novo"

if [ -L "$ATIVO" ] && [ "$(readlink "$ATIVO")" = "$DESTINO" ]; then
  echo "ADMIN-DADOS-PUBLICADOS: tipo=$TIPO sha=$SHA run=$RUN_NUMBER ativo=$DESTINO"
  exit 0
fi

rm -rf "$PARCIAL"
cp -R "$ORIGEM" "$PARCIAL" || parar "nao consegui copiar $ORIGEM para $PARCIAL."
find "$PARCIAL" -type d -exec chmod 755 {} +
find "$PARCIAL" -type f -exec chmod 644 {} +
rm -rf "$DESTINO"
mv "$PARCIAL" "$DESTINO" || parar "nao consegui promover $PARCIAL para $DESTINO."

rm -f "$LINK_NOVO"
ln -s "$DESTINO" "$LINK_NOVO" || parar "nao consegui criar o ponteiro novo $LINK_NOVO."
mv -Tf "$LINK_NOVO" "$ATIVO" || parar "nao consegui ativar $ATIVO."

echo "ADMIN-DADOS-PUBLICADOS: tipo=$TIPO sha=$SHA run=$RUN_NUMBER ativo=$(readlink "$ATIVO")"
