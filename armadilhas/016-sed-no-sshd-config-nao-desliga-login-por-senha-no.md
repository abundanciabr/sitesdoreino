<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §3 — Ambiente (Windows, esta máquina)
     ID historico: §3.16  ·  referencias antigas "ARMADILHAS §3.16" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 3.16 `sed` no `sshd_config` não desliga login por senha no Ubuntu 24.04 — o cloud-init religa por baixo

**Sintoma:** o provisionamento rodou
`sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config`
e mesmo assim `ssh usuario@vps` **pede senha** (medido em 21/08/2026 nesta VPS).
**Causa:** o Ubuntu 24.04 entrega `/etc/ssh/sshd_config.d/50-cloud-init.conf` com
`PasswordAuthentication yes`, e o `Include` dos drop-ins vem **no topo** do
`sshd_config` — no sshd, **o primeiro valor lido vence**. O sed edita a linha do
arquivo principal, que é lida tarde demais para valer.
**Solução:** um drop-in que vença na ordem lexicográfica
(`printf 'PasswordAuthentication no\n' > /etc/ssh/sshd_config.d/00-endurecimento.conf`),
mais `rm -f` do `50-cloud-init.conf` e `systemctl reload ssh`. Nesta VPS foi aplicado
à mão em 22/08/2026; `infra/provisionamento-vps.sh` agora faz as duas coisas. O risco
real era limitado (deploy sem senha utilizável, root em `prohibit-password`), mas a
"impossibilidade" prometida não estava valendo.
**Como conferir:** `ssh conta-inexistente@vps` deve recusar com
`Permission denied (publickey)` **sem** oferecer campo de senha.
**Origem:** sessão deploy-infra (22/08/2026), ao notar o prompt de senha num teste
de SSH do mantenedor.
