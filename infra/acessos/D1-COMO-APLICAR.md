# D1: main só pelo integrador (nada foi aplicado)

Formato do JSON conferido na documentação pública da API de rulesets (09/10/2026). Ponto a confirmar na hora: se o GitHub aceitar bypass de deploy key em repositório pessoal público (a doc diz que sim). Se recusar, parar e avisar.

## Passos (nesta ordem)
1. Chave na VPS, como deploy, sem senha:
   `ssh sitesdoreino-vps 'ssh-keygen -t ed25519 -N "" -C integrador-vps -f /home/deploy/.ssh/integrador'`
2. Cadastrar a chave pública com escrita:
   `ssh sitesdoreino-vps 'cat /home/deploy/.ssh/integrador.pub' > integrador.pub`
   `gh repo deploy-key add integrador.pub --repo abundanciabr/sitesdoreino --allow-write --title integrador-vps`
3. Remoto na VPS:
   `ssh sitesdoreino-vps 'git -C /opt/plataforma/codigo/repo.git remote add integrador git@github.com:abundanciabr/sitesdoreino.git && git -C /opt/plataforma/codigo/repo.git config core.sshCommand "ssh -i /home/deploy/.ssh/integrador -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"'`
   (o remoto origin https de leitura não muda; o cron continua lendo por ele).
4. Aplicar a regra:
   `gh api -X POST repos/abundanciabr/sitesdoreino/rulesets --input C:/Users/davia/abundanciabr/wt-entregas-20261009/infra/acessos/D1-regra-da-main.json`
   Anote o "id" devolvido.

## Provas inofensivas
- Pelo PC: `git push origin meu-ramo-de-teste:main` deve ser RECUSADO (rule violations). Depois apague o ramo de teste.
- Pelo integrador: `ssh sitesdoreino-vps 'git -C /opt/plataforma/codigo/repo.git push integrador <sha-ja-existente-na-main>:refs/heads/main'` (push sem mudança) deve ser aceito.

## Recuperação
Dona: Settings > Rules > Rulesets > "main só pelo integrador" > Enforcement: Disabled. Ou:
`gh api -X PUT repos/abundanciabr/sitesdoreino/rulesets/<id> -f enforcement=disabled`

## O que muda para Codex e Claude
Continuam fazendo push, mas só em ramos `codex/entrega/*` e `claude/entrega/*`. Nunca mais na main; quem leva à main é o integrador na VPS.
