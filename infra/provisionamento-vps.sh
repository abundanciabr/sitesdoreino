#!/usr/bin/env bash
# =============================================================================
# ETAPA A — PROVISIONAMENTO DE IMPOSSIBILIDADES (VPS NOVA)
# Rode VOCÊ MESMO, como root, uma única vez. Agentes de IA NUNCA executam este
# arquivo e NUNCA recebem chave SSH desta máquina — não é proibição, é inexistência.
# =============================================================================
set -euo pipefail

DEPLOY_CI_PUBKEY="${DEPLOY_CI_PUBKEY:?Exporte DEPLOY_CI_PUBKEY com a chave pública ed25519 do CI antes de rodar}"

echo "▶ 1) Usuário 'deploy' — a única porta de entrada, e ela pertence ao pipeline"
id deploy &>/dev/null || adduser --disabled-password --gecos "" deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
printf '%s\n' "$DEPLOY_CI_PUBKEY" > /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys
chown deploy:deploy /home/deploy/.ssh/authorized_keys

echo "▶ 2) SSH endurecido — sem senha, sem root por senha"
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
# Ubuntu 24.04: o cloud-init entrega /etc/ssh/sshd_config.d/50-cloud-init.conf com
# PasswordAuthentication yes, e o Include dos drop-ins roda ANTES do arquivo
# principal — no sshd o PRIMEIRO valor vence, então os sed acima sozinhos NÃO
# desligam a senha (medido em 21-22/08/2026; ARMADILHAS.md §3.16). O drop-in
# 00-* vence qualquer 50-*.
printf '%s\n' 'PasswordAuthentication no' > /etc/ssh/sshd_config.d/00-endurecimento.conf
rm -f /etc/ssh/sshd_config.d/50-cloud-init.conf
systemctl reload ssh 2>/dev/null || systemctl reload sshd

echo "▶ 3) Firewall"
apt-get update -y && apt-get install -y ufw
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "▶ 4) Docker"
command -v docker &>/dev/null || curl -fsSL https://get.docker.com | sh
usermod -aG docker deploy

echo "▶ 5) /opt/plataforma — dono deploy, modo 750. NUNCA 777."
install -d -m 750 -o deploy -g deploy /opt/plataforma
install -d -m 750 -o deploy -g deploy /opt/plataforma/env
install -d -m 750 -o deploy -g deploy /opt/plataforma/traefik
install -d -m 750 -o deploy -g deploy /opt/plataforma/traefik/dynamic

echo "▶ 6) Redes Docker"
docker network inspect edge    &>/dev/null || docker network create edge
docker network inspect interna &>/dev/null || docker network create interna

cat <<'FIM'
===============================================================================
✅ Impossibilidades provisionadas. PRÓXIMOS PASSOS MANUAIS (você, não agente):

 1. Copiar infra/docker-compose.yml e infra/traefik/* para /opt/plataforma/
    (só na primeira vez — depois o workflow deploy-infra sincroniza sozinho)
 2. Criar /opt/plataforma/env/*.env a partir de infra/env/*.exemplo
    ⚠ INV-P8: MP_ACCESS_TOKEN de PRODUÇÃO (APP_USR-...) entra SOMENTE em
      /opt/plataforma/env/pagamentos.env. Nunca no repo. Nunca em dev.
 3. Logar o Docker da VPS no ghcr, como o usuário deploy:
      docker login ghcr.io -u <dono-do-repo>
    senha = PAT (classic) com escopo read:packages. As imagens são privadas:
    sem este passo NENHUM deploy consegue puxar imagem — todo pull morre em
    "unauthorized" (medido em 21/08/2026; ARMADILHAS.md §1, H13).
 4. Rodar infra/provisionamento-postgres.sql no Postgres (senhas: openssl rand -hex 24)
 5. GitHub → Secrets do repo: VPS_HOST e DEPLOY_SSH_KEY (a chave PRIVADA do par do CI)
 6. GitHub → Branch protection de main: checklist no 00-LEIA-PRIMEIRO.md
 7. Apontar o DNS do domínio novo para esta VPS (ou configurar o Cloudflare na frente)
===============================================================================
FIM
