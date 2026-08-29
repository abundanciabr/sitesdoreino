#!/usr/bin/env bash
# =============================================================================
# A PORTA LATERAL DO SERVIDOR — conferir de dentro e endurecer o que falta.
#
# O QUE ESTE SCRIPT RESPONDE
# --------------------------
# O pedido `20260823-001` (H15) nasceu quando o repositório virou público em
# 23/08/2026: o IP da VPS ficou visível, e a receita escrita na época era
# "aceitar 80/443 SOMENTE das faixas do Cloudflare".
#
# ESSA RECEITA DERRUBARIA O SITE HOJE, e o próprio `infra/traefik/dynamic/
# plataforma.yml` avisa: `meshcraft.top` é servido DIRETO (Modo B, Let's
# Encrypt — está na lista `tls.domains` do router `funil`), sem Cloudflare na
# frente. Aplicar a regra fecharia 80/443 para o mundo inteiro, inclusive para
# os visitantes de verdade. Não há borda a pular porque o servidor É a borda.
#
# Medido de fora em 29/08/2026, do PC do mantenedor, contra o IP da VPS:
#   - 32 portas testadas: só 22, 80 e 443 respondem; as outras 29 ficam sem
#     resposta (DROP, a assinatura de um firewall ativo — sem firewall, porta
#     sem serviço RECUSA em vez de calar);
#   - `https://<ip>/` sem nome de site responde 404: quem chega pelo IP não
#     recebe site nenhum (é o INV-P11, a fronteira de site, funcionando).
#
# Ou seja: o firewall já está ligado desde a fundação — `infra/provisionamento-
# vps.sh` roda `ufw allow OpenSSH`, `ufw allow 80/tcp`, `ufw allow 443/tcp` e
# `ufw --force enable`. Este script existe para (a) CONFIRMAR isso por dentro,
# que é a única prova que falta, e (b) aplicar o endurecimento que ainda cabe.
#
# O QUE ELE MUDA — e por que nada disto pode derrubar o site
# -----------------------------------------------------------
# 1. `ufw default deny incoming` — reafirma a política padrão. Não fecha porta
#    nenhuma que esteja explicitamente permitida.
# 2. `ufw limit OpenSSH` — troca "permitir SSH" por "permitir SSH com freio":
#    o mesmo IP tentando mais de 6 conexões em 30s é barrado. É ganho real
#    contra força bruta, e NÃO fecha o SSH para você.
#
# Nenhuma regra de 80/443 é removida — elas são reafirmadas. Por isso não há
# reversão temporizada aqui: uma reversão que desligasse o firewall sozinha
# abriria exatamente a porta que viemos fechar. A rede de segurança é melhor
# que um relógio — ele guarda as regras ANTES, e se o autoteste final não
# encontrar 22, 80 e 443 permitidas, ele RESTAURA sozinho e avisa.
#
# COMO RODAR — UMA LINHA, na janela da VPS (o prompt começa com `deploy@srv...`
# ou `root@srv...`; se começa com `PS C:` você está no PC, e não é aqui):
#
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/conferir-firewall.sh -o /tmp/f.sh && bash /tmp/f.sh
#
# Sem argumentos, não pergunta nada. Seguro de rodar quantas vezes quiser.
# Deu certo se a última linha for `PRONTO: a porta lateral está fechada.`
# Deu errado se aparecer `PAROU POR SEGURANÇA: ...` — nada foi alterado, e a
# tela inteira serve para mandar ao agente.
# =============================================================================
set -u

parar() { echo; echo "PAROU POR SEGURANÇA: $1"; echo "NADA foi alterado."; exit 1; }

# ---------------------------------------------------------------------------
# 0) É a máquina certa, e eu posso mandar nela?
# ---------------------------------------------------------------------------
[ -d /opt/plataforma ] || parar "não achei /opt/plataforma — esta não parece ser a VPS da plataforma. O prompt precisa começar com deploy@srv... ou root@srv..., nunca com PS C:"

if [ "$(id -u)" -eq 0 ]; then
  SUDO=""
elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
  SUDO="sudo"
else
  parar "preciso de poder de administrador para ler e ajustar o firewall, e não consegui. Entre como root (o prompt vira root@srv...) e rode a mesma linha de novo."
fi

command -v ufw >/dev/null 2>&1 || parar "o ufw não está instalado nesta máquina. Isso é inesperado — o provisionamento o instala. Mande esta tela ao agente antes de instalar qualquer coisa."

echo "==============================================================="
echo " A PORTA LATERAL DO SERVIDOR — conferência e endurecimento"
echo "==============================================================="
echo

# ---------------------------------------------------------------------------
# 1) Estado ANTES — o retrato que ninguém tinha
# ---------------------------------------------------------------------------
echo "== 1/5 — como o firewall está agora =="
ANTES="$($SUDO ufw status verbose 2>/dev/null)" || parar "não consegui ler o estado do ufw."
printf '%s\n' "$ANTES" | sed 's/^/   /'
echo

case "$ANTES" in
  *"Status: active"*) echo "   OK — o firewall está LIGADO." ;;
  *) parar "o firewall está DESLIGADO. Isso muda o quadro e merece uma conversa antes de eu ligar sozinho — mande esta tela ao agente." ;;
esac
echo

# ---------------------------------------------------------------------------
# 2) Guardar as regras atuais antes de encostar em qualquer coisa
# ---------------------------------------------------------------------------
echo "== 2/5 — guardando as regras atuais (para poder voltar atrás) =="
COPIA="/tmp/firewall-antes-$(date +%Y%m%d-%H%M%S).tar.gz"
$SUDO tar czf "$COPIA" -C /etc ufw 2>/dev/null || parar "não consegui guardar uma cópia das regras. Sem cópia de segurança eu não mexo em firewall."
echo "   cópia guardada em: $COPIA"
echo

# ---------------------------------------------------------------------------
# 3) O que o Docker publica — o furo conhecido, que aqui é só AVISO
# ---------------------------------------------------------------------------
# O Docker escreve direto no iptables e passa POR CIMA do ufw: um `ports:` no
# compose fica visível na internet mesmo com o ufw negando. Hoje só o Traefik
# publica (80 e 443), e é assim que tem de ser. Se um dia isso mudar, esta
# seção é o lugar onde se vê primeiro. Ela AVISA e não conserta: mexer em
# publicação de porta é mudança de compose, que viaja por PR.
echo "== 3/5 — o que os containers publicam para fora =="
if command -v docker >/dev/null 2>&1; then
  PUB="$(cd /opt/plataforma 2>/dev/null && $SUDO docker compose ps --format "{{.Service}} {{.Publishers}}" 2>/dev/null || true)"
  if [ -z "$PUB" ]; then
    echo "   (não consegui listar — seguindo; isto é informação, não trava)"
  else
    printf '%s\n' "$PUB" | sed 's/^/   /'
  fi
  INESPERADO="$(printf '%s' "$PUB" | grep -oE "0\.0\.0\.0:[0-9]+" | cut -d: -f2 | grep -vxE "80|443" | sort -u || true)"
  if [ -n "$INESPERADO" ]; then
    echo
    echo "   ATENÇÃO: há container publicando porta além de 80/443:"
    printf '%s\n' "$INESPERADO" | sed 's/^/      porta /'
    echo "   O Docker passa POR CIMA do ufw, então essa porta está na internet."
    echo "   Não vou mexer nisso sozinho — mande esta tela ao agente."
  else
    echo "   OK — só 80 e 443 são publicados, que é o desenho correto."
  fi
else
  echo "   (docker não encontrado — seguindo)"
fi
echo

# ---------------------------------------------------------------------------
# 4) Endurecer o que cabe, sem fechar nada que esteja aberto
# ---------------------------------------------------------------------------
echo "== 4/5 — endurecendo (sem fechar 22, 80 nem 443) =="
$SUDO ufw --force default deny incoming >/dev/null 2>&1 || parar "não consegui reafirmar a política padrão de entrada."
echo "   OK — padrão de entrada: negar (o que não está liberado, não entra)"

# `limit` sobrescreve o `allow` do OpenSSH: mesma porta, com freio.
$SUDO ufw limit OpenSSH >/dev/null 2>&1 || parar "não consegui pôr o freio no SSH. As regras seguem como estavam."
echo "   OK — SSH com freio: mais de 6 tentativas em 30s do mesmo lugar são barradas"
echo

# ---------------------------------------------------------------------------
# 5) O AUTOTESTE — e a volta atrás automática se ele não passar
# ---------------------------------------------------------------------------
# Ausência de erro não é sucesso (INV-CI01): o veredito vem de LER as regras de
# novo e encontrar as três portas que o site precisa. Se qualquer uma sumiu, a
# cópia do passo 2 volta na hora, sem esperar ninguém confirmar nada.
echo "== 5/5 — conferindo que as três portas do site continuam de pé =="
DEPOIS="$($SUDO ufw status 2>/dev/null)"
FALTOU=""
printf '%s' "$DEPOIS" | grep -qE "(^|[^0-9])22[/ ]" || FALTOU="$FALTOU 22"
printf '%s' "$DEPOIS" | grep -qE "(^|[^0-9])80[/ ]" || FALTOU="$FALTOU 80"
printf '%s' "$DEPOIS" | grep -qE "(^|[^0-9])443[/ ]" || FALTOU="$FALTOU 443"

if [ -n "$FALTOU" ]; then
  echo "   FALHOU — sumiu do firewall:$FALTOU. VOLTANDO ATRÁS AGORA."
  $SUDO tar xzf "$COPIA" -C /etc && $SUDO ufw --force reload >/dev/null 2>&1
  echo
  echo "PAROU POR SEGURANÇA: as regras foram RESTAURADAS ao estado anterior."
  echo "O site não corre risco. Mande esta tela inteira ao agente."
  exit 1
fi

printf '%s\n' "$DEPOIS" | sed 's/^/   /'
echo
echo "   OK — 22 (você entrar), 80 e 443 (os visitantes) continuam permitidas."
echo
echo "PRONTO: a porta lateral está fechada."
echo
echo "O que isto quer dizer, em português: o servidor só atende em três portas"
echo "— a sua entrada e as duas do site. Tudo o mais está mudo para a internet."
echo "Quem chegar pelo endereço numérico, sem o nome do site, recebe 'não"
echo "encontrado' e mais nada."
