# D2: usuário "robo" na VPS (nada foi aplicado)

## Quem é afetado
Hoje todos entram como `deploy` (grupo docker = poder de root). Os robôs (Codex, Claude, robôs locais) passariam a entrar como `robo`, que só roda entregar, consultar e estado, sem docker e sem shell.

## Chaves hoje em /home/deploy/.ssh/authorized_keys (conferido 09/10/2026)
- SHA256:0Lf5N3Voeus7tCpnqyjA8FQb9dApsCkOI5GhEQKd69g  deploy_ci@sitesdoreino
- SHA256:+eKOcjlz6oewBUEzrJcLy/jDsNI9j3aOrT0B8WyrBu0  deploy-vps-environment-20260919
- SHA256:zFrc09cWN0Ysy2X/5uj8W21wEuDW/ESxMRFiWO0dUAY  robos-locais-20261001
- A 4ª linha não apareceu no ssh-keygen (provavelmente comentário/linha vazia ou formato não lido); conferir à mão com `ssh sitesdoreino-vps 'wc -l ~/.ssh/authorized_keys'`, sem copiar a chave.
Comando: `ssh -o BatchMode=yes sitesdoreino-vps 'ssh-keygen -lf ~/.ssh/authorized_keys'`

## Continua ao robô
entregar (enviar uma entrega), consultar (ver andamento), estado (ver estado da plataforma), via /opt/plataforma/integrador/entregas.py. Nada de docker, sudo ou shell livre.

## O mantenedor mantém
A chave atual em `deploy` e o console da hospedagem como recuperação.

## Ordem
1. Gerar no PC uma chave nova só do robô (ed25519), guardar a privada.
2. Copiar D2-usuario-robo.sh para a VPS e rodar como root com a chave pública: `sudo bash D2-usuario-robo.sh "<pública>"` (o script imprime a linha de authorized_keys).
3. Testar: `ssh -i <chave-robo> robo@sitesdoreino-vps estado` funciona; `... ls` é recusado.
4. Trocar os robôs para usar a chave nova; só então tirar do deploy a linha `robos-locais-20261001`.
Requer que /opt/plataforma/integrador/entregas.py exista (vem com o integrador).

## Reversão
Apagar a linha de /home/robo/.ssh/authorized_keys; nada mais muda. (Para remover tudo: `userdel -r robo`.)
