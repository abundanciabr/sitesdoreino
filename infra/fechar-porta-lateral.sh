#!/usr/bin/env bash
# =============================================================================
# FECHAR A PORTA LATERAL DO SERVIDOR — item H15 do livro de ocorrencias.
#
# O QUE ISTO RESOLVE, E O QUE NAO RESOLVE (leia antes de rodar)
# ------------------------------------------------------------
# Desde 23/08/2026 o repositorio e publico, entao o IP da VPS esta visivel.
# Esconde-lo de novo nao e opcao real: scanners tipo Shodan/Censys acham origem
# de qualquer jeito, e reescrever o historico do git quebraria todos os PRs.
#
# A saida "obvia" foi DESCARTADA em 23/08/2026, e continua descartada:
# firewall aceitando 80/443 so das faixas do Cloudflare mataria o site na hora.
# Medido de fora em 28/08/2026: `curl -I https://meshcraft.top/` responde
# `Server: uvicorn` (SEM cf-ray) — o site principal e servido DIRETO, no Modo B
# do infra/traefik/traefik.yml. Uma regra so-Cloudflare o derrubaria inteiro.
#
# O que este script faz e o que RESTA de defesa real: garantir que, alem de 22
# (SSH, ja so por chave), 80 e 443, NENHUMA outra porta responde da internet.
# O docker-compose.yml desta plataforma publica exatamente essas duas (o
# Traefik: ports 80:80 e 443:443) e mais nenhuma — banco, Redis e as 13
# celulas vivem so na rede interna do Docker. Este script torna isso uma
# GARANTIA imposta pela maquina, em vez de uma propriedade que se perde no dia
# em que alguem publicar uma porta sem perceber.
#
# HONESTIDADE SOBRE O ALCANCE: o Docker manipula o iptables por fora do ufw, e
# porta publicada por container atravessa o ufw de qualquer forma. Ou seja:
# este firewall protege o que roda no HOST, nao o que o Docker publica. Ele nao
# fecha, e nao tem como fechar, o acesso direto a 80/443 — isso e decisao de
# arquitetura (por o meshcraft.top atras do Cloudflare), nao de firewall.
#
# SEGURO DE RODAR MAIS DE UMA VEZ: idempotente. O provisionamento original da
# VPS (infra/provisionamento-vps.sh, linhas 31-35) ja fazia isto; se estiver
# tudo certo, o script confirma e nao muda nada.
#
# NAO REINICIA NADA, nao toca env, nao escreve segredo, nao toca no Docker.
#
# COMO O MANTENEDOR RODA (DENTRO da VPS, uma linha so):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/fechar-porta-lateral.sh -o /tmp/f.sh && sudo bash /tmp/f.sh
#
# A linha comeca com `curl`, e o prompt tem de estar como `deploy@srv...` ou
# `root@srv...` — se o seu prompt comeca com `PS C:\>`, voce esta no PC e este
# script nao e para la.
# =============================================================================
set -u

parar() {
  echo
  echo "PAROU POR SEGURANCA: $1"
  echo "NADA foi alterado."
  exit 1
}

[ "$(id -u)" -eq 0 ] || parar "rode com sudo (regra de firewall exige root): sudo bash /tmp/f.sh"
command -v ufw > /dev/null 2>&1 || parar "ufw nao esta instalado — isto nao parece a VPS certa (o provisionamento original a instala)."
[ -d /opt/plataforma ] || parar "nao achei /opt/plataforma — voce esta na VPS certa? O prompt precisa comecar com deploy@srv... ou root@srv..., nunca PS C:\>"

echo "== 1/4 — como o firewall esta HOJE =="
ufw status verbose || parar "nao consegui ler o estado do ufw."

echo
echo "== 2/4 — declarando as tres portas que podem responder =="
# `ufw allow` e idempotente: repetir regra existente nao duplica nada.
ufw allow 22/tcp  > /dev/null 2>&1 || parar "nao consegui declarar a regra de SSH (22). Nada foi ligado."
ufw allow 80/tcp  > /dev/null 2>&1 || parar "nao consegui declarar a regra de HTTP (80). Nada foi ligado."
ufw allow 443/tcp > /dev/null 2>&1 || parar "nao consegui declarar a regra de HTTPS (443). Nada foi ligado."
ufw default deny incoming  > /dev/null 2>&1 || parar "nao consegui definir a politica de entrada."
ufw default allow outgoing > /dev/null 2>&1 || parar "nao consegui definir a politica de saida."
echo "  22, 80 e 443 declaradas; tudo o mais passa a ser recusado."

echo
echo "== 3/4 — ligando =="
ufw --force enable > /dev/null 2>&1 || parar "o ufw recusou ligar."

echo
echo "== 4/4 — conferindo o resultado REAL (nao o exit do comando) =="
RESULTADO="$(ufw status verbose)"
echo "$RESULTADO"
echo

# INV-CI01: ausencia de erro nao e evidencia de sucesso. Cada linha abaixo le o
# estado publicado pelo ufw; qualquer uma faltando derrubaria algo de verdade.
echo "$RESULTADO" | grep -q "Status: active"                  || parar "o ufw nao reportou 'active'. Mande esta tela ao agente."
echo "$RESULTADO" | grep -qE "^22(/tcp)?[[:space:]]+ALLOW"    || parar "a regra de SSH (22) NAO aparece no estado final. Se voce sair desta sessao pode perder o acesso. Rode agora: sudo ufw allow 22/tcp — e mande esta tela ao agente."
echo "$RESULTADO" | grep -qE "^80/tcp[[:space:]]+ALLOW"       || parar "a regra de HTTP (80) NAO aparece no estado final. Rode agora: sudo ufw allow 80/tcp"
echo "$RESULTADO" | grep -qE "^443/tcp[[:space:]]+ALLOW"      || parar "a regra de HTTPS (443) NAO aparece no estado final. Rode agora: sudo ufw allow 443/tcp"

echo "== conferindo que o site continua respondendo de dentro da VPS =="
CODIGO="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 https://meshcraft.top/ || echo 000)"
echo "  https://meshcraft.top/ respondeu $CODIGO"
[ "$CODIGO" = "200" ] || parar "o site NAO respondeu 200 (respondeu $CODIGO). Para desfazer AGORA: sudo ufw disable — e mande esta tela ao agente."

echo
echo "PRONTO: porta lateral fechada. So 22 (chave), 80 e 443 respondem da internet, e o site segue no ar."
