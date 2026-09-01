#!/usr/bin/env bash
# =============================================================================
# O QUE RODA DENTRO DA VPS quando uma célula é entregue.
#
# Vive num arquivo, e não embutido no YAML do workflow, desde 28/08/2026 — por
# um motivo prático: a entrega passou a ser TENTADA MAIS DE UMA VEZ (a VPS
# recusou a conexão do runner cinco vezes em três dias, `armadilhas/127`), e
# repetir o corpo do script três vezes dentro do YAML seria a duplicação que
# esta casa proíbe. Com o script num arquivo, cada tentativa é uma chamada
# curta e existe UMA definição do que a entrega faz.
#
# De quebra: aqui ele é um `.sh` de verdade — revisável, com fim de linha
# travado em LF pelo `.gitattributes`, e sem escapar de YAML.
#
# ENTRADA: a variável CELULA, passada pelo workflow (`envs: CELULA`).
#
# IDEMPOTENTE POR CONSTRUÇÃO, e isso é requisito e não sorte: se a conexão cair
# no meio, a tentativa seguinte roda tudo de novo. `pull` e `up -d` sobre o
# estado já correto não fazem nada. A cópia de segurança acrescentada em
# 01/09/2026 mantém a propriedade: cada execução escreve um arquivo NOVO, com
# carimbo de tempo próprio, e nunca sobrescreve o de ninguém.
#
# -----------------------------------------------------------------------------
# A CÓPIA DE SEGURANÇA ANTES DA MIGRAÇÃO (TAR-003, 01/09/2026, recomendação O15
# do PLANO-MESTRE-ROBOS-SEM-COLISAO.md) — leia isto antes de mexer no bloco.
#
# POR QUE ELA MORA AQUI, E NÃO NUM SCRIPT SÓ DELA. As migrações do Django não
# rodam em lugar nenhum deste script: elas rodam no BOOT de cada contêiner
# (todo `services/*/Dockerfile` termina em `migrate --noinput && uvicorn ...`).
# Quando o `up -d` abaixo devolve, a migração JÁ ACONTECEU, e um backup depois
# dele seria um backup do estrago, valendo zero. O único instante em que ainda
# dá tempo é este, antes do `up -d`.
#
# E este arquivo é O ÚNICO TEXTO QUE CHEGA À VPS no deploy de célula: a
# `appleboy/ssh-action` recebe `script_path: infra/deploy-celula-na-vps.sh` e
# envia o CONTEÚDO deste arquivo pelo canal SSH. O `deploy-celula.yml` não tem
# nenhum passo de cópia de arquivos (medido em 01/09/2026), e o `deploy-infra`
# copia uma lista fixa que não inclui `.sh` avulso. Um
# `infra/backup-antes-da-migracao.sh` separado simplesmente NÃO EXISTIRIA em
# /opt/plataforma na hora do deploy, e como o backup é fail-closed o deploy
# pararia em toda entrega, para sempre. Por isso o bloco é daqui.
#
# COPIA SEMPRE, e não só quando há migração pendente. Descobrir se existe
# migração pendente exigiria subir a imagem NOVA para perguntar a ela, que é
# exatamente o risco que a cópia existe para cobrir. Um ramo a mais aqui é um
# ramo a mais para errar em silêncio, e copiar sempre satisfaz "antes de toda
# migração" ao pé da letra. Não "otimize" isto.
#
# SE A CÓPIA FALHAR, O DEPLOY PARA. É a funcionalidade inteira, e é a parte
# desconfortável: este bloco é um jeito NOVO de o deploy ficar vermelho. Um
# backup que "tenta e segue" é um backup que não existe no dia em que importa.
# Quando ele para, nada foi mudado (o `up -d` está depois) e o site continua
# servindo a imagem ANTIGA.
#
# NENHUM SEGREDO SAI DAQUI. O `pg_dump` roda DENTRO do contêiner do Postgres,
# pelo socket local, como o superusuário `postgres`: não há senha em linha de
# comando, nem em variável, nem no nome do arquivo. Este script nunca abre um
# `env/*.env`, e nunca imprime uma `DATABASE_URL`.
# =============================================================================
set -eu

# `pipefail` faz um pipe devolver o veredito do primeiro comando que falhou, e
# não o do último, que é a §5.10 desta casa: a mesma confusão que fez os greens
# do deploy-celula mentirem até 21/08/2026 (H13). A forma tolerante existe
# porque este texto é executado pelo shell de login do usuário `deploy` na VPS,
# e não pelo shebang do topo: num shell sem `pipefail`, `set -o pipefail` cru é
# erro, e com `set -e` ele derrubaria toda entrega. Cinto e suspensório: além
# disto, NENHUM veredito deste script vem de um pipe. A saída é guardada em
# variável e o estado é lido do COMANDO, sempre.
if (set -o pipefail) 2>/dev/null; then set -o pipefail; fi

# `/opt/plataforma` é a pasta da plataforma na VPS, e continua sendo o padrão.
# A variável existe para que este script inteiro possa ser exercido contra uma
# plataforma de mentira (um `docker-compose.yml` de teste, num diretório de
# teste) sem VPS nenhuma: foi assim que a cópia de segurança abaixo foi provada
# de ida e volta antes de entrar. Guarda: ci/tests/test_backup_antes_da_migracao.py
RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
cd "$RAIZ"

if [ -z "${CELULA:-}" ]; then
  echo "PAROU POR SEGURANÇA: a variável CELULA chegou vazia."
  echo "Sem ela, os comandos abaixo agiriam sobre a plataforma inteira."
  exit 1
fi

# A célula não é mais UM container: os consumers de evento e o worker Huey vivem
# em serviços "<celula>-<papel>" (infra/docker-compose.yml). Subir só "<celula>"
# deixaria o auxiliar rodando a IMAGEM ANTIGA, em silêncio — duas versões do
# mesmo código no ar, sem alarme nenhum. A lista sai do PRÓPRIO compose, não de
# uma lista fixa aqui: a célula que ganhar um auxiliar amanhã já entra sozinha,
# sem editar este arquivo.
SERVICOS=$(docker compose config --services | grep -E "^${CELULA}(-|\$)" || true)
if [ -z "$SERVICOS" ]; then
  echo "ERRO: '$CELULA' não tem serviço algum em $RAIZ/docker-compose.yml."
  echo "Abortado de propósito: 'up -d' sem argumento subiria a plataforma inteira."
  exit 1
fi
echo "Serviços desta célula: $SERVICOS"

docker compose pull $SERVICOS

# =============================================================================
# CÓPIA DE SEGURANÇA DO BANCO, ANTES DO `up -d`, porque depois é tarde.
# Vem depois do `pull` de propósito: o `pull` não muda nada em produção, e uma
# imagem que nem baixou não chega a migrar coisa alguma.
# =============================================================================
parar_o_deploy() {
  echo
  echo "PAROU POR SEGURANÇA: $1"
  echo
  echo "O QUE ESTA NO AR AGORA: nada mudou. A imagem nova NAO subiu e nenhuma"
  echo "migracao rodou, porque este passo vem antes de tudo isso. E por isso que"
  echo "ele para em vez de seguir. O site continua servindo a versao anterior."
  echo "O QUE FAZER: conserte o que a linha acima aponta e peca um run novo."
  echo "Sem copia de seguranca do banco, esta casa nao migra."
  exit 1
}

# A pasta dos dumps. Nasce sozinha, e o dono e o modo são COPIADOS de `env/`,
# que já funciona nesta máquina e é o vizinho de sensibilidade certa
# (`armadilhas/091`: quem escolhe permissão à mão acerta na sua máquina e erra
# na do pipeline). Um dump é dado pessoal de aluno em texto puro, e ele não pode
# nascer mais aberto que os segredos ao lado dele.
PASTA_DOS_DUMPS="$RAIZ/backups-de-banco"
REFERENCIA_DE_PERMISSAO="${BACKUP_REFERENCIA:-$RAIZ/env}"

# QUANTOS FICAM GUARDADOS, e por que 20. A retenção é POR BASE, não pela
# plataforma toda. O deploy roda muitas vezes por dia nesta casa (25
# aterrissagens em 31/08/2026, e a célula `admin` recebe uma entrega a cada
# registro novo no livro do painel), e a janela em que alguém DESCOBRE que uma
# migração estragou algo é medida em horas, não em minutos. Com menos que isso,
# um dia agitado apagaria justamente o dump anterior à migração ruim antes de
# alguém olhar. Com muito mais, o disco vira o modo de falha, e aqui disco cheio
# para o deploy inteiro. 20 cobre o dia mais movimentado já medido, na célula
# mais movimentada, e os dumps são comprimidos (formato `-Fc`).
RETENCAO=20

BASE="${CELULA}_db"
case "$BASE" in
  *[!A-Za-z0-9_]*) parar_o_deploy "o nome de base '$BASE' tem caractere que nao e letra, numero ou sublinhado. Nada foi tocado." ;;
esac

# A célula TEM banco? A pergunta é feita ao PRÓPRIO Postgres, e não a um
# `env/*.env`, e assim este script nunca chega perto de uma senha. O `funil` é a
# única célula sem banco hoje (é stateless), e para ela a resposta legítima é
# "nada a copiar".
#
# "Não consegui perguntar" NUNCA vira "não existe" ([INV-CI01]): o exit != 0 do
# comando para o deploy, e só a resposta VAZIA de uma pergunta bem-sucedida
# significa ausência de base.
EXISTE_A_BASE=$(docker compose exec -T postgres psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$BASE'") \
  || parar_o_deploy "nao consegui perguntar ao Postgres se a base '$BASE' existe. O banco pode estar fora do ar, e se ele estiver a migracao no boot da imagem nova falharia do mesmo jeito. Nada foi tocado."

if [ -z "$EXISTE_A_BASE" ]; then
  echo "BACKUP-ANTES-DA-MIGRACAO: dispensado, a celula '$CELULA' nao tem a base '$BASE' neste Postgres (celula sem banco)."
else
  mkdir -p "$PASTA_DOS_DUMPS"
  if [ -d "$REFERENCIA_DE_PERMISSAO" ]; then
    # O dono pode já estar certo (a pasta nasce do usuário do pipeline), e num
    # sistema onde `chown` exige root ele falharia sem nada estar errado. O modo
    # é o que guarda o segredo, e esse é exigido.
    chown --reference="$REFERENCIA_DE_PERMISSAO" "$PASTA_DOS_DUMPS" 2>/dev/null || true
    chmod --reference="$REFERENCIA_DE_PERMISSAO" "$PASTA_DOS_DUMPS" \
      || parar_o_deploy "nao consegui copiar as permissoes de $REFERENCIA_DE_PERMISSAO para $PASTA_DOS_DUMPS. Um dump e dado pessoal, e eu nao o gravo numa pasta com permissao que eu mesmo escolhi. Nada foi tocado."
  else
    parar_o_deploy "nao achei $REFERENCIA_DE_PERMISSAO para copiar dono e modo da pasta de dumps. Nada foi tocado."
  fi

  # Restos de uma execução que morreu no meio. São lixo por definição (um
  # `.parcial` nunca é um backup), e apagá-los aqui é o que mantém este bloco
  # re-executável quando a entrega é repetida (`armadilhas/127`).
  rm -f "$PASTA_DOS_DUMPS/$BASE"-*.dump.parcial

  # 1) LIMPEZA PRIMEIRO, CONFERÊNCIA DE ESPAÇO DEPOIS. A ordem importa: medir o
  #    disco antes de apagar os antigos faria o script recusar um deploy que
  #    caberia perfeitamente.
  EXISTENTES=$(ls -1 "$PASTA_DOS_DUMPS/$BASE"-*.dump 2>/dev/null || true)
  if [ -n "$EXISTENTES" ]; then
    # O nome carrega AAAAMMDD-HHMMSSZ, então ordem alfabética É ordem de tempo.
    # `sort -r` põe o mais novo em cima, e guardamos RETENCAO-1 das
    # antigas: a vaga que falta e a da copia que estamos prestes a gravar, e assim
    # o total DEPOIS desta execucao e exatamente RETENCAO, nunca RETENCAO+1.
    A_APAGAR=$(printf '%s\n' "$EXISTENTES" | sort -r | tail -n +"$RETENCAO")
    if [ -n "$A_APAGAR" ]; then
      QUANTOS=$(printf '%s\n' "$A_APAGAR" | wc -l)
      echo "Retencao: a pasta fica com no maximo $RETENCAO copias de $BASE (as mais recentes, mais a desta entrega); apagando $QUANTOS antiga(s)."
      printf '%s\n' "$A_APAGAR" | while IFS= read -r velho; do
        if [ -n "$velho" ]; then rm -f "$velho"; fi
      done
    fi
  fi

  # 2) ESPAÇO EM DISCO, o modo de falha mais provável e o único previsível.
  #    Disco cheio tem de virar uma frase clara, nunca um dump truncado: um
  #    arquivo pela metade é PIOR que arquivo nenhum, porque ele mente no dia do
  #    desespero. A régua é o tamanho da base INTEIRA mais uma folga, o que é
  #    generoso de propósito, já que o dump comprimido é uma fração dela.
  TAMANHO_DA_BASE=$(docker compose exec -T postgres psql -U postgres -tAc "SELECT pg_database_size('$BASE')") \
    || parar_o_deploy "nao consegui medir o tamanho da base '$BASE'. Nada foi tocado."
  TAMANHO_DA_BASE=$(printf '%s' "$TAMANHO_DA_BASE" | tr -d '[:space:]')
  case "$TAMANHO_DA_BASE" in
    ''|*[!0-9]*) parar_o_deploy "o Postgres respondeu algo que nao e um numero ao tamanho da base '$BASE'. 'Nao consegui medir' nunca vira 'pode seguir'. Nada foi tocado." ;;
  esac

  SAIDA_DO_DF=$(df -Pk "$PASTA_DOS_DUMPS") \
    || parar_o_deploy "nao consegui medir o espaco livre em $PASTA_DOS_DUMPS. Nada foi tocado."
  LIVRE_KB=$(printf '%s\n' "$SAIDA_DO_DF" | awk 'NR==2 {print $4}')
  case "$LIVRE_KB" in
    ''|*[!0-9]*) parar_o_deploy "nao consegui ler o espaco livre em $PASTA_DOS_DUMPS a partir do df. Nada foi tocado." ;;
  esac

  # 256 MB de folga: o dump comprimido cabe MUITO abaixo disso, e um disco com
  # menos folga que isto já é um problema por si só, que o dono precisa ver.
  FOLGA_KB=262144
  PRECISO_KB=$(( TAMANHO_DA_BASE / 1024 + FOLGA_KB ))
  if [ "$LIVRE_KB" -lt "$PRECISO_KB" ]; then
    parar_o_deploy "nao ha espaco em disco para a copia de seguranca de '$BASE'. Livre: $((LIVRE_KB / 1024)) MB. Necessario com folga: $((PRECISO_KB / 1024)) MB. A pasta dos dumps e $PASTA_DOS_DUMPS e ela ja foi limpa ate as $RETENCAO copias mais recentes por base, entao o disco da VPS esta cheio por outro motivo, e isso e para o dono olhar. Nada foi tocado."
  fi

  # 3) O DUMP. Formato `-Fc` (custom, já comprimido) e SEM PIPE NENHUM: o
  #    caminho clássico `pg_dump ... | gzip > arquivo` devolve o veredito do
  #    `gzip`, e um `pg_dump` que morreu no meio passa despercebido (§5.10).
  #    Aqui o estado lido é o do próprio `pg_dump`, propagado pelo `exec`.
  #    Escreve num `.parcial` e só renomeia depois de provado: assim o nome
  #    final NUNCA existe apontando para um arquivo pela metade, e o `mv` de um
  #    arquivo para outro dentro da mesma pasta é atômico.
  CARIMBO=$(date -u +%Y%m%d-%H%M%SZ)
  ARQUIVO_FINAL="$PASTA_DOS_DUMPS/$BASE-$CARIMBO.dump"
  ARQUIVO_PARCIAL="$ARQUIVO_FINAL.parcial"

  docker compose exec -T postgres pg_dump -U postgres -Fc -d "$BASE" > "$ARQUIVO_PARCIAL" \
    || { rm -f "$ARQUIVO_PARCIAL"; parar_o_deploy "o pg_dump da base '$BASE' falhou. O arquivo incompleto foi descartado e nada mudou em producao."; }

  TAMANHO_DO_DUMP=$(wc -c < "$ARQUIVO_PARCIAL")
  if [ "$TAMANHO_DO_DUMP" -le 0 ]; then
    rm -f "$ARQUIVO_PARCIAL"
    parar_o_deploy "o dump de '$BASE' saiu VAZIO. Arquivo vazio que se chama backup e a pior coisa que existe aqui, e por isso ele foi descartado."
  fi

  # A prova de que o arquivo é um dump inteiro, e não um pedaço: `pg_restore -l`
  # lê o índice interno do formato custom e falha em "end of file" se ele estiver
  # truncado. Medido em 01/09/2026 contra um dump cortado de propósito.
  docker compose exec -T postgres pg_restore -l < "$ARQUIVO_PARCIAL" > /dev/null \
    || { rm -f "$ARQUIVO_PARCIAL"; parar_o_deploy "o dump de '$BASE' foi escrito mas NAO ABRE: esta truncado ou corrompido. Ele foi descartado de proposito, porque um arquivo pela metade que se chama backup mente no dia em que alguem precisar dele."; }

  mv "$ARQUIVO_PARCIAL" "$ARQUIVO_FINAL" \
    || parar_o_deploy "nao consegui renomear a copia de seguranca para o nome final. Nada foi tocado."

  # A SENTINELA DA CÓPIA. É esta linha que o log do run mostra ANTES da subida
  # dos contêineres, e é ela a evidência que a fila pediu para a TAR-003.
  # ASCII de propósito, pelo mesmo motivo da ENTREGA-CONCLUIDA lá embaixo: acento
  # numa sentinela é um jeito barato de o grep falhar por codificação.
  # O carimbo sai em UTC (ordena certo e não tem ambiguidade) e a linha seguinte
  # traduz para o horário de Brasília, porque quem procura um dump às 3 da manhã
  # não deve ter de converter fuso de cabeça.
  echo "BACKUP-ANTES-DA-MIGRACAO: $BASE-$CARIMBO.dump ($((TAMANHO_DO_DUMP / 1024)) KB) em $PASTA_DOS_DUMPS"
  echo "BACKUP-ANTES-DA-MIGRACAO: o carimbo do nome e UTC; em Brasilia sao tres horas a menos."
  echo "BACKUP-ANTES-DA-MIGRACAO: o caminho de volta e infra/restaurar-backup.sh"
fi

# --wait reprova o deploy se algum container não ficar de pé (ou não ficar
# HEALTHY — os healthchecks do compose, entregues pelo PR #45, são a sonda
# pós-deploy F5 do PROJETO-PORTAO-DEPLOY). Sem ele, 'ps' devolve sucesso com
# container em crash-loop (ARMADILHAS §3.13).
#
# É AQUI QUE A MIGRAÇÃO ACONTECE: cada Dockerfile de célula termina em
# `migrate --noinput && uvicorn ...`, então o `migrate` roda no boot do
# container. Quando esta linha devolve, o banco já mudou, e é por isso que a
# cópia de segurança está acima dela e nunca abaixo.
docker compose up -d --wait --wait-timeout 180 $SERVICOS
docker compose ps $SERVICOS

# A PROVA DE QUE ESTE SCRIPT RODOU ATE O FIM. Sem ela, um passo que nao executa
# nada devolve 0 e o deploy fica VERDE sem ter subido imagem nenhuma — foi
# exatamente o que aconteceu em 28/08/2026, quando o parametro do workflow
# estava com o nome errado (script_file em vez de script_path): a acao avisou
# "Unexpected input", ignorou o script, conectou, nao rodou nada e saiu com
# sucesso. O workflow EXIGE esta linha na saida; sem ela, reprova.
# ASCII de proposito: acento numa sentinela e um jeito barato de o grep falhar
# por codificacao e a trava virar decoracao.
echo "ENTREGA-CONCLUIDA: $CELULA"
