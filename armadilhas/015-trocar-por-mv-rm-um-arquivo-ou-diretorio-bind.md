<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §3 — Ambiente (Windows, esta máquina)
     ID historico: §3.15  ·  referencias antigas "ARMADILHAS §3.15" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 3.15 Trocar por `mv`/`rm` um arquivo ou diretório bind-mounted não muda nada no container que já roda

**Sintoma:** você substitui, no servidor, um arquivo ou diretório que o compose
monta por bind (`./traefik/traefik.yml:...:ro`), roda `docker compose up -d`, nada
é recriado — e o container continua servindo a configuração **antiga**, sem erro
nenhum em lugar nenhum.
**Causa:** bind mount prende o **inode** resolvido na criação do container, não o
caminho. `mv novo antigo` e `rm -rf dir && mv dir.new dir` criam inodes novos; o
container em execução segue lendo o inode velho (que sobrevive enquanto montado,
mesmo "apagado" do disco). E `up -d` só recria serviço cuja **definição** no
compose mudou — conteúdo de arquivo montado não conta como mudança.
**Solução:** depois de trocar arquivo/diretório montado, force o recreate de quem
o monta: `docker compose up -d --force-recreate <servico>`. É o que
`.github/workflows/deploy-infra.yml` faz com o traefik, condicionado a um
`diff -r` entre o backup e o material novo — recriar sem necessidade seria um
blip de edge gratuito a cada sync de compose.
**Origem:** despacho 04 (deploy-infra), ao desenhar a troca fail-closed de
`/opt/plataforma/traefik/`.
