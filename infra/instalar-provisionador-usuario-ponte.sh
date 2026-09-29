#!/usr/bin/env bash
# =============================================================================
# LIGAR A PONTE COM A VPS — o unico passo que e do mantenedor, e ele e uma
# linha so, colada UMA VEZ no console root da VPS:
#
#   bash /opt/plataforma/instalar-provisionador-usuario-ponte.sh /opt/plataforma/provisionar-usuario-ponte.sh
#
# O prompt tem de estar como `root@srv...`. Se comecar com `PS C:\>`, voce esta
# no seu PC e este roteiro nao e para la. Os dois arquivos chegam sozinhos a
# /opt/plataforma na sincronizacao de infraestrutura; se o primeiro deles nao
# estiver la, a mensagem abaixo diz isso com o caminho na mao.
#
# O QUE ELE FAZ, em portugues: cria na VPS uma conta chamada `ponte` que nao
# serve para mais nada alem de deixar o PC do mantenedor enxergar a porta 8443
# de dentro da propria VPS. E o que falta para os 12.879 alunos aparecerem no
# painel dele.
#
# POR QUE ESTE PASSO EXISTE, E POR QUE E UMA VEZ SO
# ------------------------------------------------
# Criar conta de sistema e mexer em /etc/ssh exige root, e a esteira entra na
# VPS como `deploy`, que nao e root. Em vez de dar root a esteira, este roteiro
# CONGELA uma copia do provisionador em /usr/local/sbin, pertencente ao root, e
# autoriza o `deploy` a executar exatamente aquele caminho, sem argumentos e sem
# senha. Dai em diante a esteira reconcilia a ponte sozinha a cada
# sincronizacao, e um PR futuro nao muda o que roda como root sem que o
# mantenedor rode este roteiro de novo. O congelamento e a protecao.
#
# A ORDEM DAS DUAS ESCRITAS NAO E DETALHE. A regra de sudo e conferida ANTES de
# entrar em /etc/sudoers.d: um arquivo invalido la dentro quebra o `sudo` da
# maquina inteira, para todo mundo, e conferir depois de escrever seria
# descobrir o estrago com ele ja feito.
# =============================================================================
set -euo pipefail

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ORIGEM=${1:-$RAIZ/provisionar-usuario-ponte.sh}
DESTINO=/usr/local/sbin/provisionar-usuario-ponte
SUDOERS=/etc/sudoers.d/90-deploy-provisionar-ponte

if [ "$(id -u)" -ne 0 ]; then
  echo "PAROU: este roteiro precisa de root, e voce nao esta como root. Nada foi alterado." >&2
  echo "       No console da VPS, rode antes: sudo -i" >&2
  exit 1
fi
case "$ORIGEM" in
  "$RAIZ/provisionar-usuario-ponte.sh"|"$RAIZ/infra.new/provisionar-usuario-ponte.sh") ;;
  *) echo "PAROU: a fonte deve ser a copia oficial em $RAIZ ou $RAIZ/infra.new; nada foi alterado." >&2; exit 1 ;;
esac
if [ ! -f "$ORIGEM" ] || [ -L "$ORIGEM" ]; then
  echo "PAROU: a fonte oficial $ORIGEM esta ausente ou e link; nada foi alterado." >&2
  echo "       Reenvie a infraestrutura pelo deploy-infra e repita o mesmo comando." >&2
  exit 1
fi
if ! bash -n "$ORIGEM" || ! grep -Fq 'flock --exclusive 8' "$ORIGEM"; then
  echo "PAROU: $ORIGEM nao contem o provisionador valido e protegido; nada foi alterado." >&2
  echo "       Corrija o PR, reenvie a infraestrutura e repita o mesmo comando." >&2
  exit 1
fi
cd "$RAIZ"

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

CANDIDATO=$(mktemp "$DESTINO.new.XXXXXX")
REGRA_NOVA=$(mktemp)
SUDOERS_NOVO=$(mktemp "$SUDOERS.new.XXXXXX")
ANTERIOR_PROVISIONADOR=
ANTERIOR_SUDOERS=
PUBLICADO=0
limpar_ou_restaurar() {
  local CODIGO=$?
  local RESTAURACAO_INCERTA=0
  local TEMP_RESTAURACAO
  trap - EXIT
  set +e
  if [ "$CODIGO" -ne 0 ] && [ "$PUBLICADO" = 1 ]; then
    if [ -n "$ANTERIOR_PROVISIONADOR" ]; then
      TEMP_RESTAURACAO=$(mktemp "$DESTINO.restore.XXXXXX")
      if ! cp -a "$ANTERIOR_PROVISIONADOR" "$TEMP_RESTAURACAO" || ! cmp -s "$ANTERIOR_PROVISIONADOR" "$TEMP_RESTAURACAO" || ! mv -Tf "$TEMP_RESTAURACAO" "$DESTINO" || ! cmp -s "$ANTERIOR_PROVISIONADOR" "$DESTINO"; then
        RESTAURACAO_INCERTA=1
      fi
      rm -f "$TEMP_RESTAURACAO"
    else
      if ! rm -f "$DESTINO" || [ -e "$DESTINO" ]; then RESTAURACAO_INCERTA=1; fi
    fi
    if [ -n "$ANTERIOR_SUDOERS" ]; then
      TEMP_RESTAURACAO=$(mktemp "$SUDOERS.restore.XXXXXX")
      if ! cp -a "$ANTERIOR_SUDOERS" "$TEMP_RESTAURACAO" || ! cmp -s "$ANTERIOR_SUDOERS" "$TEMP_RESTAURACAO" || ! mv -Tf "$TEMP_RESTAURACAO" "$SUDOERS" || ! cmp -s "$ANTERIOR_SUDOERS" "$SUDOERS"; then
        RESTAURACAO_INCERTA=1
      fi
      rm -f "$TEMP_RESTAURACAO"
    else
      if ! rm -f "$SUDOERS" || [ -e "$SUDOERS" ]; then RESTAURACAO_INCERTA=1; fi
    fi
    if ! visudo -c >/dev/null; then RESTAURACAO_INCERTA=1; fi
    if [ "$RESTAURACAO_INCERTA" = 0 ]; then
      echo "PONTE: copia root e regra sudo anteriores restauradas apos a falha." >&2
    else
      echo "ERRO: recuperacao incerta; no console root, confira $DESTINO e $SUDOERS com visudo -c antes de repetir." >&2
      echo "      Copias anteriores preservadas: ${ANTERIOR_PROVISIONADOR:-nenhuma} ${ANTERIOR_SUDOERS:-nenhuma}" >&2
    fi
  fi
  rm -f "$CANDIDATO" "$REGRA_NOVA" "$SUDOERS_NOVO"
  if [ "$RESTAURACAO_INCERTA" = 0 ]; then
    [ -z "$ANTERIOR_PROVISIONADOR" ] || rm -f "$ANTERIOR_PROVISIONADOR"
    [ -z "$ANTERIOR_SUDOERS" ] || rm -f "$ANTERIOR_SUDOERS"
  fi
  exit "$CODIGO"
}
trap limpar_ou_restaurar EXIT

install -o root -g root -m 755 "$ORIGEM" "$CANDIDATO"
if [ ! -f "$ORIGEM" ] || [ -L "$ORIGEM" ] || ! cmp -s "$ORIGEM" "$CANDIDATO" || ! bash -n "$CANDIDATO" || ! grep -Fq 'flock --exclusive 8' "$CANDIDATO"; then
  echo "PAROU: a fonte mudou durante a copia ou o candidato falhou; a instalacao anterior continua." >&2
  exit 1
fi
printf '%s\n' "deploy ALL=(root) NOPASSWD: $DESTINO" > "$REGRA_NOVA"
if ! visudo -cf "$REGRA_NOVA"; then
  echo "PAROU: a regra sudo nova reprovou antes de ser publicada; a anterior continua." >&2
  exit 1
fi
install -o root -g root -m 440 "$REGRA_NOVA" "$SUDOERS_NOVO"
visudo -c >/dev/null || {
  echo "PAROU: o sudoers existente ja e invalido; nenhuma copia ou regra nova foi publicada." >&2; exit 1;
}
if [ -e "$DESTINO" ]; then
  ANTERIOR_PROVISIONADOR=$(mktemp "$DESTINO.old.XXXXXX")
  cp -a "$DESTINO" "$ANTERIOR_PROVISIONADOR"
fi
if [ -e "$SUDOERS" ]; then
  ANTERIOR_SUDOERS=$(mktemp "$SUDOERS.old.XXXXXX")
  cp -a "$SUDOERS" "$ANTERIOR_SUDOERS"
fi

PUBLICADO=1
mv -Tf "$CANDIDATO" "$DESTINO"
mv -Tf "$SUDOERS_NOVO" "$SUDOERS"
visudo -c >/dev/null || {
  echo "PAROU: o conjunto sudoers reprovou; copia e regra anteriores serao restauradas." >&2; exit 1;
}
"$DESTINO"
PUBLICADO=0

echo "PRONTO: a copia root e a regra sudo foram instaladas e a ponte foi conferida."
echo "A esteira podera reconciliar a ponte no proximo deploy-infra."
