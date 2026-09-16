#!/usr/bin/env bash
# =============================================================================
# LIGAR A PONTE COM A VPS — o unico passo que e seu, e ele e uma linha so.
#
# O QUE ESTA LINHA FAZ, em portugues: cria na VPS uma conta chamada `ponte`
# que nao serve para mais nada alem de deixar o SEU computador enxergar a porta
# 8443 de dentro da propria VPS. Ela nao tem shell, nao transfere arquivo, nao
# aceita senha e nao alcanca nenhum outro endereco. E o que falta para os 12.879
# alunos aparecerem no seu painel.
#
# COMO RODAR, no console root da VPS (uma linha, sem argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/instalar-provisionador-da-ponte.sh -o /tmp/ponte.sh && bash /tmp/ponte.sh || echo "PAROU. Se a linha acima disse 404, este roteiro ainda nao chegou na main: espere o PR da TAR-419 pousar e repita esta mesma linha."
#
#   O `|| echo` no fim nao e enfeite: quando o roteiro ainda nao esta na main, o
#   proprio `curl` morre com um `404` cru e NENHUMA mensagem daqui de dentro
#   chega a ser lida, porque o arquivo que as contem nao existe ainda. Medido
#   em 16/09/2026, no console da VPS, antes de o PR pousar.
#
#   O prompt tem de estar como `root@srv...`. Se comecar com `PS C:\>`, voce
#   esta no seu PC e este roteiro nao e para la.
#
# POR QUE ESTE PASSO EXISTE, e por que ele e UMA VEZ SO
# ----------------------------------------------------
# Criar conta de sistema e mexer em /etc/ssh exige root, e a esteira entra na
# VPS como `deploy`, que nao e root. Em vez de dar root a esteira, este roteiro
# instala uma copia CONGELADA do provisionador em /usr/local/sbin, pertencente
# ao root, e autoriza o `deploy` a executar exatamente aquele caminho, sem
# argumentos e sem senha. A partir daqui a esteira reconcilia a ponte sozinha
# a cada sincronizacao de infraestrutura, e um PR futuro nao consegue mudar o
# que roda como root sem que voce rode este roteiro de novo. Esse congelamento
# e a propria protecao: mexer na ponte volta a passar por voce.
#
# SE VOCE NUNCA RODAR ISTO, nada quebra: a sincronizacao de infraestrutura
# continua normal e diz, no log, que a ponte ainda nao foi ligada.
# =============================================================================
set -euo pipefail

ORIGEM=https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-usuario-ponte.sh
DESTINO=/usr/local/sbin/provisionar-usuario-ponte
SUDOERS=/etc/sudoers.d/90-deploy-provisionar-a-ponte

if [ "$(id -u)" -ne 0 ]; then
  echo "PAROU: este roteiro precisa de root, e voce nao esta como root. Nada foi alterado." >&2
  echo "       No console da VPS, rode antes:  sudo -i" >&2
  exit 1
fi
if ! command -v curl >/dev/null 2>&1; then
  echo "PAROU: o comando curl nao existe nesta maquina. Nada foi alterado." >&2
  echo "       Rode:  apt-get update && apt-get install -y curl  — e repita esta linha." >&2
  exit 1
fi

BAIXADO=$(mktemp)
REGRA_NOVA=$(mktemp)
trap 'rm -f "$BAIXADO" "$REGRA_NOVA"' EXIT

echo "1/4 baixando o provisionador da main..."
if ! curl -fsSL "$ORIGEM" -o "$BAIXADO"; then
  echo "PAROU: nao consegui baixar o provisionador. Nada foi alterado." >&2
  echo "       Isso acontece quando o PR da TAR-419 ainda nao esta na main." >&2
  echo "       Confira se a pagina abre e repita esta linha:" >&2
  echo "       $ORIGEM" >&2
  exit 1
fi
# Nunca instalar como root um arquivo que nem analisa: um download pela metade
# vira um arquivo valido no disco e um erro incompreensivel semanas depois.
if ! bash -n "$BAIXADO"; then
  echo "PAROU: o arquivo baixado nao e um roteiro valido (download pela metade?). Nada foi alterado." >&2
  echo "       Repita esta mesma linha; se insistir, avise o agente." >&2
  exit 1
fi

echo "2/4 instalando a copia congelada em $DESTINO (dono root)..."
install -o root -g root -m 755 "$BAIXADO" "$DESTINO"

echo "3/4 autorizando o deploy a executar SO esse caminho..."
# A regra e conferida ANTES de entrar em /etc/sudoers.d: um arquivo invalido la
# dentro quebra o `sudo` da maquina inteira, para todo mundo.
printf '%s\n' "deploy ALL=(root) NOPASSWD: $DESTINO" > "$REGRA_NOVA"
if ! visudo -cf "$REGRA_NOVA"; then
  echo "PAROU: a regra do sudo nao passou na conferencia e NAO foi instalada. Nada foi alterado." >&2
  exit 1
fi
install -o root -g root -m 440 "$REGRA_NOVA" "$SUDOERS"
if ! visudo -c >/dev/null; then
  rm -f "$SUDOERS"
  echo "PAROU: com a regra nova o conjunto do sudo ficou invalido; removi a regra e o sudo voltou ao que era." >&2
  exit 1
fi

echo "4/4 criando a conta ponte agora, para voce nao ter de esperar o proximo deploy..."
echo
"$DESTINO"

echo
echo "==============================================================================="
echo "PRONTO. A ponte esta ligada nesta VPS."
echo
echo "Voce nao precisa fazer mais nada aqui. Daqui para frente a esteira mantem a"
echo "ponte sozinha a cada sincronizacao de infraestrutura."
echo
echo "Se um dia quiser DESLIGAR a ponte, rode estas duas linhas neste mesmo console:"
echo "  rm -f $SUDOERS $DESTINO /etc/ssh/sshd_config.d/90-ponte.conf && systemctl reload ssh"
echo "  userdel -r ponte"
echo "==============================================================================="
