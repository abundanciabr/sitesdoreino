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

ORIGEM=${1:-/opt/plataforma/provisionar-usuario-ponte.sh}
DESTINO=/usr/local/sbin/provisionar-usuario-ponte
SUDOERS=/etc/sudoers.d/90-deploy-provisionar-ponte

if [ "$(id -u)" -ne 0 ]; then
  echo "PAROU: este roteiro precisa de root, e voce nao esta como root. Nada foi alterado." >&2
  echo "       No console da VPS, rode antes:  sudo -i" >&2
  exit 1
fi
if [ ! -f "$ORIGEM" ]; then
  echo "PAROU: nao encontrei o provisionador em $ORIGEM. Nada foi alterado." >&2
  echo "       Ele chega sozinho a /opt/plataforma na sincronizacao de infraestrutura." >&2
  echo "       Espere o proximo deploy de infra terminar e repita esta mesma linha." >&2
  exit 1
fi
# Nunca instalar como root um arquivo que nem analisa: uma copia pela metade
# vira um arquivo valido no disco e um erro incompreensivel semanas depois.
if ! bash -n "$ORIGEM"; then
  echo "PAROU: $ORIGEM nao e um roteiro valido (copia pela metade?). Nada foi alterado." >&2
  echo "       Espere o proximo deploy de infra reescrever o arquivo e repita esta linha." >&2
  exit 1
fi

REGRA_NOVA=$(mktemp)
trap 'rm -f "$REGRA_NOVA"' EXIT

echo "1/3 congelando o provisionador em $DESTINO (dono root)..."
install -o root -g root -m 755 "$ORIGEM" "$DESTINO"

echo "2/3 autorizando o deploy a executar SO esse caminho..."
printf '%s\n' "deploy ALL=(root) NOPASSWD: $DESTINO" > "$REGRA_NOVA"
if ! visudo -cf "$REGRA_NOVA"; then
  echo "PAROU: a regra do sudo nao passou na conferencia e NAO foi instalada." >&2
  echo "       O sudo desta maquina continua exatamente como estava." >&2
  exit 1
fi
install -o root -g root -m 440 "$REGRA_NOVA" "$SUDOERS"
if ! visudo -c >/dev/null; then
  rm -f "$SUDOERS"
  echo "PAROU: com a regra nova o conjunto do sudo ficou invalido; removi a regra e o sudo voltou ao que era." >&2
  exit 1
fi

echo "3/3 criando a conta ponte agora, para nao ter de esperar o proximo deploy..."
echo
"$DESTINO"

echo
echo "==============================================================================="
echo "PRONTO. A ponte esta ligada nesta VPS."
echo
echo "Nao ha mais nada a fazer aqui: daqui para frente a esteira mantem a ponte"
echo "sozinha a cada sincronizacao de infraestrutura."
echo
echo "Para DESLIGAR a ponte um dia, neste mesmo console:"
echo "  rm -f $SUDOERS $DESTINO /etc/ssh/sshd_config.d/90-ponte.conf"
echo "  systemctl reload ssh && userdel -r ponte"
echo "==============================================================================="
