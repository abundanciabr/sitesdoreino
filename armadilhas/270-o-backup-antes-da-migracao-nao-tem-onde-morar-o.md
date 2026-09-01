---
schema_version: 2
armadilha: 270
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: ci/tests/test_backup_antes_da_migracao.py
sinal:
  - `backup-antes-da-migracao.sh: No such file or directory`
  - `bash: line 1: /opt/plataforma/backup-antes-da-migracao.sh`
---

# Você escreveu um script auxiliar em `infra/` e o chamou do deploy: ele não existe na VPS, e o deploy passa a falhar em TODA entrega

**Sintoma.** O `deploy-celula` fica vermelho na primeira entrega depois do merge,
em toda célula, com uma linha do tipo:

```
bash: line 42: /opt/plataforma/backup-antes-da-migracao.sh: No such file or directory
```

O script existe no repositório, o PR ficou verde, as muralhas passaram, e a VPS
está viva. O arquivo simplesmente não está lá.

**Causa: nenhum arquivo de `infra/` chega à VPS no deploy de célula.** Medido em
01/09/2026, e vale a pena saber de cor, porque a intuição diz o contrário:

- O `deploy-celula.yml` **não tem passo de cópia de arquivos**. Ele usa
  `appleboy/ssh-action` com `script_path: infra/deploy-celula-na-vps.sh`, e essa
  ação lê o arquivo no runner e manda o **CONTEÚDO** dele pelo canal SSH, como
  comando. Nada é gravado em `/opt/plataforma`. O único texto que a VPS executa
  é o corpo daquele arquivo.
- O `deploy-infra.yml` copia, sim, mas uma **lista fixa e curta**:
  `infra/docker-compose.yml`, `infra/traefik`, `infra/sites.json` e
  `infra/sincronizar_sites.py`. Um `.sh` avulso não entra por estar em `infra/`.
- Não existe clone do repositório na VPS. O `provisionamento-vps.sh` cria
  `/opt/plataforma`, `env/` e `traefik/`, e mais nada.

Ou seja: `infra/` **não é uma pasta compartilhada com a VPS**. Ela é o material
de origem de duas esteiras que copiam coisas nomeadas uma a uma.

**O que torna isto caro.** Se o auxiliar que você chamou for fail-closed (o caso
que motivou esta entrada foi a cópia de segurança do banco antes da migração,
TAR-003), o deploy não fica só ruidoso: ele **para**, e para em toda célula, até
alguém desfazer o merge. O erro só aparece DEPOIS do merge, porque o deploy roda
depois da `main`, e nenhum required check olha para ele.

**Solução — escolha uma das duas, com os olhos abertos:**

1. **O comportamento mora dentro do `deploy-celula-na-vps.sh`.** É o que a
   TAR-003 fez. Não é duplicação: continua existindo UMA definição do que a
   entrega faz, e ela viaja inteira. Custa a ilusão de um arquivo pequeno e
   separado.
2. **Você acrescenta um passo de cópia ao workflow** (`appleboy/scp-action`,
   como o `deploy-infra` faz) e só então chama o auxiliar por caminho. É o
   desenho preferível quando houver mais de um auxiliar — mas é mudança em
   `.github/workflows/**`, caminho CODEOWNERS, e precisa entrar **junto** com a
   chamada, nunca depois: o intervalo entre os dois merges é a janela em que
   toda entrega falha.

**Como testar um script de VPS sem VPS, que foi o que destravou este caso:**
troque o `cd /opt/plataforma` fixo por `cd "${PLATAFORMA_DIR:-/opt/plataforma}"`
e monte uma **plataforma de mentira** — um diretório com um `docker-compose.yml`
de teste que declara um `postgres:17` de verdade e uns `alpine` no lugar das
células. Aí o script INTEIRO roda na sua máquina, com `docker compose pull`,
`up -d --wait` e `exec` reais. Foi assim que a cópia de segurança da TAR-003 foi
provada de ida e volta (backup, apagar a tabela, restaurar, a linha de volta)
antes de o PR existir.

**A regra que generaliza:** antes de chamar um arquivo do repositório de dentro
de um script que roda na VPS, responda por medição — não por intuição — **como
aquele arquivo chegou lá**. `grep -n "scp\|source:\|script_path" .github/workflows/*.yml`
responde em dois segundos. É a mesma família da
[048](048-run-algo-coisa-sem-aspas-quebra-o-yaml.md) e da
[091](091-env-criado-por-root-o-deploy-nao-le.md): o que quebra não é a lógica, é
a suposição não medida sobre o ambiente em que ela vai rodar.

**Origem:** TAR-003, 01/09/2026 — cópia de segurança do banco antes de toda
migração (recomendação O15 do `PLANO-MESTRE-ROBOS-SEM-COLISAO.md`). O despacho
pedia um `infra/backup-antes-da-migracao.sh` separado, chamado pelo deploy; a
medição do workflow, feita antes da primeira linha de código, mostrou que ele
nunca existiria na VPS. Guarda: `test_o_workflow_ainda_envia_este_arquivo_e_nao_copia_outros`,
em `ci/tests/test_backup_antes_da_migracao.py`, reprova se o `deploy-celula`
ganhar um `scp-action` sem que alguém releia esta decisão.
