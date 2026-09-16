#!/usr/bin/env bash
# =============================================================================
# O USUARIO `ponte` NA VPS — a metade da Fase 2 que faltava (TAR-419).
#
# O QUE ELE E: uma conta de sistema cuja unica capacidade e abrir um caminho
# para 127.0.0.1:8443 de dentro da propria maquina. Sem shell, sem SFTP, sem
# TTY, sem agente, sem X11, sem tunel, sem senha, e sem nenhum outro destino.
# E a ponta da VPS do cano que a Fase 3 abre deste PC.
#
# O PERIGO DESTE ARQUIVO, e ele nao se disfarca: configuracao errada de sshd
# tranca todo mundo para fora da VPS, inclusive a esteira de deploy, e nao ha
# desfazer pela rede. As quatro travas, nesta ordem:
#
#   1. ACRESCIMO, nunca edicao. Escreve so um arquivo novo em
#      /etc/ssh/sshd_config.d/ e nunca toca o sshd_config principal.
#   2. `sshd -t` ANTES do reload. Sintaxe ruim restaura e sai, sem recarregar.
#   3. A PROVA QUE DECIDE: `sshd -T -C user=deploy` renderizado ANTES e DEPOIS
#      da escrita tem de sair byte a byte igual. Isso mede a configuracao
#      EFETIVA do usuario da esteira contra o arquivo novo, ainda sem recarregar
#      nada. Diferenca de um caractere restaura e sai. E o que transforma "o
#      Match nao deve alcancar o deploy" de esperanca em medicao.
#   4. `systemctl reload`, NUNCA `restart`: reload nao derruba as sessoes
#      abertas, e a sessao viva da esteira e o que permite desfazer. Depois do
#      reload o sshd tem de continuar atendendo na 22; se nao continuar,
#      restaura e recarrega de volta, ali mesmo.
#
# POR QUE NAO TEM `Match all` FECHANDO O BLOCO: medido em 16/09/2026 num
# Ubuntu 24.04 com as MESMAS diretivas ativas que `infra/provisionamento-vps.sh`
# deixa na VPS (PermitRootLogin, PasswordAuthentication, KbdInteractive,
# X11Forwarding e Subsystem sftp). O escopo de um `Match` acaba no fim do
# arquivo que o abriu: `sshd -T -C user=deploy` saiu identico ao estado sem o
# drop-in, e o `Subsystem sftp` do arquivo principal continuou valendo para o
# deploy. Uma linha que nao muda nada nao entra — e a trava 3 mede isso a cada
# execucao, em vez de confiar nesta medicao para sempre.
#
# E IDEMPOTENTE E CONVERGENTE: rodado com tudo no lugar, ele nao escreve, nao
# recarrega e diz isso. So mexe no sshd quando ha diferenca de verdade — por
# isso pode rodar em toda sincronizacao de infraestrutura sem recarregar o sshd
# da VPS por causa de uma mudanca de Traefik.
# =============================================================================
set -euo pipefail

USUARIO=ponte
CHAVE_AUTORIZADA='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDFmhu8QkiIPwN0gqmYSmSrN9E2Wr8PdAk2N3qglquu6 davi@DESKTOP-V8F32JA'
DESTINO_UNICO='127.0.0.1:8443'
CONFIG=/etc/ssh/sshd_config.d/90-ponte.conf
LAR=/home/ponte
CHAVES=$LAR/.ssh/authorized_keys

if [ "$(id -u)" -ne 0 ]; then
  echo "ERRO: este provisionador mexe em /etc/ssh e em conta de sistema, entao precisa de root. Nada foi alterado." >&2
  echo "      Quem o executa e a esteira de infraestrutura; nao o rode a mao." >&2
  exit 1
fi

# ── 1) O QUE SE QUER TER. Escrito uma vez, comparado com o que existe. ──
#
# A restricao vive em DOIS lugares de proposito, e cada um sozinho ja bastaria:
# o `Match` do sshd (abaixo) e as opcoes da propria chave (mais adiante). Um
# erro de digitacao em um dos dois nao abre a porta, porque o outro fica de pe.
#
# `ForceCommand /usr/bin/false` e o que recusa o SFTP: o `Subsystem sftp` e
# executado pelo proprio sshd, e nao pelo shell do usuario, entao o
# `/usr/sbin/nologin` sozinho NAO o impediria. Com `-N` ou `-W` nao existe canal
# de sessao, entao o encaminhamento nao passa por ele.
CONFIG_DESEJADA="Match User $USUARIO
    AuthenticationMethods publickey
    PubkeyAuthentication yes
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    AllowTcpForwarding local
    PermitOpen $DESTINO_UNICO
    PermitTTY no
    X11Forwarding no
    AllowAgentForwarding no
    PermitTunnel no
    ForceCommand /usr/bin/false"
CHAVES_DESEJADAS="restrict,port-forwarding,permitopen=\"$DESTINO_UNICO\",command=\"/usr/bin/false\" $CHAVE_AUTORIZADA"

mostrar_o_que_a_ponte_recebeu() {
  sshd -T -C "user=$USUARIO" | grep -E '^(allowtcpforwarding|permitopen|permittty|forcecommand|x11forwarding|allowagentforwarding|permittunnel|passwordauthentication|authenticationmethods) ' | sort
}

# ── 2) JA CONVERGE? Entao nao escreve e nao recarrega. ──
ja_converge() {
  id "$USUARIO" >/dev/null 2>&1 || return 1
  [ -f "$CONFIG" ] || return 1
  [ "$(cat "$CONFIG")" = "$CONFIG_DESEJADA" ] || return 1
  [ -f "$CHAVES" ] || return 1
  [ "$(cat "$CHAVES")" = "$CHAVES_DESEJADAS" ] || return 1
  return 0
}
if ja_converge; then
  echo "PONTE: ja esta como se quer — nada escrito, sshd nao recarregado."
  mostrar_o_que_a_ponte_recebeu
  echo "PONTE-PROVISIONADA: $(date -u +%Y%m%dT%H%M%SZ)"
  exit 0
fi

# ── 3) A FOTOGRAFIA DO DEPLOY, ANTES DE ESCREVER QUALQUER COISA. ──
DEPLOY_ANTES=$(sshd -T -C user=deploy | sort)

GUARDADOS=$(mktemp -d /var/backups/ponte-XXXXXX)
if [ -f "$CONFIG" ]; then cp -a "$CONFIG" "$GUARDADOS/90-ponte.conf"; fi
if [ -f "$CHAVES" ]; then cp -a "$CHAVES" "$GUARDADOS/authorized_keys"; fi

devolver_o_que_estava() {
  if [ -f "$GUARDADOS/90-ponte.conf" ]; then cp -a "$GUARDADOS/90-ponte.conf" "$CONFIG"; else rm -f "$CONFIG"; fi
  if [ -f "$GUARDADOS/authorized_keys" ]; then cp -a "$GUARDADOS/authorized_keys" "$CHAVES"; else rm -f "$CHAVES"; fi
}

# ── 4) A CONTA. Sem shell e sem senha, desde o nascimento. ──
if id "$USUARIO" >/dev/null 2>&1; then
  echo "PONTE: a conta $USUARIO ja existe; so a configuracao sera reconciliada."
else
  useradd --system --create-home --home-dir "$LAR" --shell /usr/sbin/nologin "$USUARIO"
  passwd --lock "$USUARIO" >/dev/null
  echo "PONTE: conta $USUARIO criada, shell /usr/sbin/nologin, senha travada."
fi
install -d -m 700 -o "$USUARIO" -g "$USUARIO" "$LAR/.ssh"

# ── 5) ESCREVER, e so entao medir. ──
printf '%s\n' "$CONFIG_DESEJADA" > "$CONFIG"
chmod 644 "$CONFIG"
printf '%s\n' "$CHAVES_DESEJADAS" > "$CHAVES"
chmod 600 "$CHAVES"
chown "$USUARIO:$USUARIO" "$CHAVES"

if ! sshd -t; then
  devolver_o_que_estava
  echo "ERRO: sshd -t reprovou a configuracao nova. NADA foi recarregado e os arquivos anteriores voltaram." >&2
  echo "      Conserto: corrija o bloco Match em infra/provisionar-usuario-ponte.sh e mande outro PR." >&2
  exit 1
fi
echo "PROVA 1 — sshd -t antes do reload: verde."

DEPLOY_DEPOIS=$(sshd -T -C user=deploy | sort)
if [ "$DEPLOY_ANTES" != "$DEPLOY_DEPOIS" ]; then
  devolver_o_que_estava
  echo "ERRO: a configuracao efetiva do usuario deploy MUDOU com o arquivo novo. NADA foi recarregado." >&2
  echo "      O que mudaria:" >&2
  diff <(printf '%s\n' "$DEPLOY_ANTES") <(printf '%s\n' "$DEPLOY_DEPOIS") >&2 || true
  echo "      Conserto: tudo tem de ficar dentro de Match User $USUARIO e nao valer para mais ninguem." >&2
  exit 1
fi
echo "PROVA 7a — sshd -T -C user=deploy identico antes e depois: a esteira nao perde a entrada."

# ── 6) RECARREGAR. Nunca `restart`: a sessao viva da esteira e o desfazer. ──
if ! systemctl reload ssh 2>/dev/null && ! systemctl reload sshd 2>/dev/null; then
  devolver_o_que_estava
  echo "ERRO: o reload do SSH falhou. Os arquivos anteriores voltaram e o sshd continua com a configuracao que ja estava no ar." >&2
  exit 1
fi
echo "PONTE: systemctl reload concluido (reload, nunca restart)."

# ── 7) O SSHD CONTINUA ATENDENDO? Se nao, desfaz sozinho, aqui e agora. ──
# O reload RE-EXECUTA o sshd, e existe uma janela de instantes em que a porta 22
# recusa conexao. Medido em 16/09/2026 no ensaio em container: sem repetir, a
# medicao pega essa janela, conclui que o sshd morreu e desfaz uma mudanca que
# estava certa. Por isso insiste antes de acusar.
o_sshd_atende() {
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if { exec 3<>/dev/tcp/127.0.0.1/22; } 2>/dev/null; then
      if read -r -t 5 BANNER <&3; then
        exec 3<&- 3>&-
        case "$BANNER" in SSH-2.0-*) return 0 ;; esac
      else
        exec 3<&- 3>&-
      fi
    fi
    sleep 2
  done
  return 1
}
if ! o_sshd_atende; then
  devolver_o_que_estava
  systemctl reload ssh 2>/dev/null || systemctl reload sshd
  echo "ERRO: depois do reload o sshd parou de atender na porta 22. Desfiz e recarreguei de volta." >&2
  if o_sshd_atende; then
    echo "      O sshd voltou a atender com a configuracao anterior; a VPS continua alcancavel." >&2
  else
    echo "      O sshd CONTINUA sem atender. Abra o console da VPS pelo painel do provedor e rode: rm -f $CONFIG && systemctl restart ssh" >&2
  fi
  exit 1
fi
echo "PROVA 7b — depois do reload o sshd atende na porta 22: $BANNER"

# ── 8) AS PROVAS QUE ESTE LADO SABE DAR, impressas no log do run. ──
echo "PROVA 4 — o que o sshd concede a $USUARIO, e so isso:"
mostrar_o_que_a_ponte_recebeu
echo "PROVA 2/3 — conta sem shell e chave com as opcoes restritivas:"
getent passwd "$USUARIO"
cat "$CHAVES"
echo "PROVA 6 — quem escuta na 8443 desta VPS (tem de ser so 127.0.0.1):"
ss -lnt 'sport = :8443' || true
echo "PONTE-PROVISIONADA: $(date -u +%Y%m%dT%H%M%SZ)"
