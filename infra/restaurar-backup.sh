#!/usr/bin/env bash
# =============================================================================
# O CAMINHO DE VOLTA: devolver o banco de uma célula ao estado de uma cópia de
# segurança feita antes de uma migração.
#
# Um backup sem caminho de volta não é um backup. O `deploy-celula-na-vps.sh`
# grava uma cópia da base da célula antes de toda entrega (TAR-003, 01/09/2026);
# este arquivo é o que faz essa cópia valer alguma coisa. É o irmão de banco do
# `rollback.yml`, que esta casa já tem para o código.
#
# LEIA ISTO ANTES DE RODAR, e leia devagar:
#
#   * ELE SOBRESCREVE O BANCO INTEIRO DAQUELA CÉLULA. Tudo o que entrou no
#     banco DEPOIS da hora do arquivo (aluno novo, mensagem nova, pedido novo)
#     desaparece. Não é "junta o que falta": é "volta no tempo".
#   * NÃO DÁ PARA DESFAZER. Não existe um "voltar atrás do voltar atrás".
#     Se você tem dúvida, faça uma cópia do estado de agora primeiro: rode este
#     script com --copia-de-agora, que grava um dump do estado ATUAL na mesma
#     pasta e não muda nada.
#   * O SITE DA CÉLULA FICA FORA DO AR durante a restauração (segundos a poucos
#     minutos, conforme o tamanho). Isso é de propósito: restaurar com a célula
#     escrevendo no banco ao mesmo tempo deixaria o resultado misturado.
#   * ELE NÃO PERGUNTA NADA E NÃO MUDA NADA sem a palavra mágica no fim. Rodar
#     sem ela é ENSAIO: ele confere tudo, mostra o que faria e sai.
#
# COMO RODAR (dentro da VPS, no prompt que começa com deploy@srv ou root@srv):
#
#   1. Ver quais cópias existem:
#      ls -lh /opt/plataforma/backups-de-banco/
#
#   2. Baixar este script e ensaiar (NÃO muda nada):
#      curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/restaurar-backup.sh -o /tmp/r.sh && bash /tmp/r.sh /opt/plataforma/backups-de-banco/<arquivo>.dump
#
#   3. Se o ensaio mostrar o que você espera, rode de novo com a palavra no fim:
#      bash /tmp/r.sh /opt/plataforma/backups-de-banco/<arquivo>.dump --sim-eu-quero-sobrescrever
#
# QUEM É A BASE E QUEM É A CÉLULA: sai do NOME DO ARQUIVO, não de um parâmetro
# que você digita. O nome é `<base>-AAAAMMDD-HHMMSSZ.dump`, e o carimbo é UTC (em
# Brasília, três horas a menos). Derivar do nome fecha por construção a porta de
# restaurar o dump de uma célula em cima do banco de outra, que é o erro caro que
# um parâmetro digitado à mão permitiria.
#
# NENHUM SEGREDO SAI DAQUI: o `pg_restore` roda DENTRO do contêiner do Postgres,
# pelo socket local, como o superusuário `postgres`. Nenhuma senha em linha de
# comando, nenhuma `DATABASE_URL` lida, nada de segredo na tela.
# =============================================================================

# O modo de falha de 24/08 em pessoa: carregado com `source`/`.`, um `exit` daqui
# derrubaria a sessão do mantenedor. Com `bash /tmp/r.sh` o exit morre no filho.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANCA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessao. Rode com a palavra bash na frente: bash /tmp/r.sh <arquivo>"
  return 1 2>/dev/null || exit 1
fi

set -eu
# Ver a explicação longa no cabeçalho do `deploy-celula-na-vps.sh`: nenhum
# veredito deste script vem de um pipe, e o `pipefail` é o cinto por cima disso.
if (set -o pipefail) 2>/dev/null; then set -o pipefail; fi

parar() {
  echo
  echo "PAROU POR SEGURANCA: $1"
  echo
  echo "NADA FOI RESTAURADO. O banco continua exatamente como estava."
  exit 1
}

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
COMPOSE="${BACKUP_COMPOSE:-docker compose}"

ARQUIVO=""
CONFIRMADO=0
SO_COPIA_DE_AGORA=0
for argumento in "$@"; do
  case "$argumento" in
    --sim-eu-quero-sobrescrever) CONFIRMADO=1 ;;
    --copia-de-agora) SO_COPIA_DE_AGORA=1 ;;
    -*) parar "nao conheco a opcao '$argumento'. As unicas sao --sim-eu-quero-sobrescrever e --copia-de-agora." ;;
    *)
      if [ -n "$ARQUIVO" ]; then parar "voce passou mais de um arquivo. Restauro um de cada vez, de proposito."; fi
      ARQUIVO="$argumento"
      ;;
  esac
done

if [ -z "$ARQUIVO" ]; then
  echo "COMO USAR:"
  echo "  bash $0 <caminho do arquivo .dump>"
  echo
  echo "As copias de seguranca ficam em $RAIZ/backups-de-banco/."
  echo "Para ver quais existem:  ls -lh $RAIZ/backups-de-banco/"
  exit 1
fi

cd "$RAIZ" 2>/dev/null || parar "nao achei $RAIZ. Voce esta na VPS certa? O prompt tem de comecar com deploy@srv ou root@srv."

[ -f "$ARQUIVO" ] || parar "nao achei o arquivo '$ARQUIVO'. Confira o caminho com: ls -lh $RAIZ/backups-de-banco/"
[ -r "$ARQUIVO" ] || parar "nao consigo LER o arquivo '$ARQUIVO'. Rode como root ou como o dono da pasta de backups."

# --- Quem é a base, e quem é a célula: derivado do NOME, nunca digitado. -----
NOME_DO_ARQUIVO=$(basename "$ARQUIVO")
case "$NOME_DO_ARQUIVO" in
  *.dump) : ;;
  *) parar "'$NOME_DO_ARQUIVO' nao termina em .dump. Um arquivo .parcial e uma copia que ficou pela metade, e ela nunca e um backup." ;;
esac

# `<base>-AAAAMMDD-HHMMSSZ.dump` — tira o carimbo e o sufixo, sobra a base.
BASE=$(printf '%s' "$NOME_DO_ARQUIVO" | sed -E 's/-[0-9]{8}-[0-9]{6}Z\.dump$//')
if [ "$BASE" = "$NOME_DO_ARQUIVO" ] || [ -z "$BASE" ]; then
  parar "o nome '$NOME_DO_ARQUIVO' nao esta no formato que o deploy gera (<base>-AAAAMMDD-HHMMSSZ.dump), entao eu nao consigo dizer com certeza a qual banco ele pertence. Restaurar no banco errado e o pior erro possivel aqui, e por isso eu paro em vez de adivinhar."
fi
case "$BASE" in
  *[!A-Za-z0-9_]*) parar "o nome de base '$BASE', lido do arquivo, tem caractere que nao e letra, numero ou sublinhado." ;;
esac
CELULA=$(printf '%s' "$BASE" | sed -E 's/_db$//')

# --- A copia existe DE VERDADE, e abre? -------------------------------------
TAMANHO=$(wc -c < "$ARQUIVO")
case "$TAMANHO" in ''|*[!0-9]*) parar "nao consegui medir o tamanho de '$ARQUIVO'." ;; esac
[ "$TAMANHO" -gt 0 ] || parar "o arquivo '$NOME_DO_ARQUIVO' esta VAZIO. Ele nao e um backup."

$COMPOSE exec -T postgres pg_restore -l < "$ARQUIVO" > /dev/null \
  || parar "o arquivo '$NOME_DO_ARQUIVO' NAO ABRE: esta truncado ou corrompido, ou o Postgres nao esta de pe. Se o Postgres estiver rodando, escolha outra copia da pasta: esta nao serve para nada."

EXISTE_A_BASE=$($COMPOSE exec -T postgres psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$BASE'") \
  || parar "nao consegui falar com o Postgres. Ele esta de pe? Veja com: $COMPOSE ps postgres"
[ -n "$EXISTE_A_BASE" ] || parar "a base '$BASE' nao existe neste Postgres. Este arquivo nao pertence a esta maquina."

SERVICOS=$($COMPOSE config --services | grep -E "^${CELULA}(-|\$)" || true)

# --- O ENSAIO: o que vai acontecer, em portugues, antes de acontecer. --------
echo "== O QUE EU VOU FAZER =="
echo "  arquivo ............. $NOME_DO_ARQUIVO ($((TAMANHO / 1024)) KB)"
echo "  banco de destino .... $BASE (a celula '$CELULA')"
echo "  servicos a parar .... $(printf '%s' "${SERVICOS:-nenhum encontrado no compose}" | tr '
' ' ')"
echo "  o arquivo abre ...... sim, conferido agora"
echo
echo "  ATENCAO: tudo o que entrou no banco '$BASE' DEPOIS da hora deste arquivo"
echo "  vai desaparecer. Isso NAO da para desfazer. O site da celula '$CELULA'"
echo "  fica fora do ar durante a troca."
echo

if [ "$SO_COPIA_DE_AGORA" -eq 1 ]; then
  DESTINO="$RAIZ/backups-de-banco"
  mkdir -p "$DESTINO"
  CARIMBO=$(date -u +%Y%m%d-%H%M%SZ)
  ANTES="$DESTINO/$BASE-$CARIMBO.dump"
  $COMPOSE exec -T postgres pg_dump -U postgres -Fc -d "$BASE" > "$ANTES.parcial" \
    || { rm -f "$ANTES.parcial"; parar "nao consegui copiar o estado de AGORA de '$BASE'."; }
  $COMPOSE exec -T postgres pg_restore -l < "$ANTES.parcial" > /dev/null \
    || { rm -f "$ANTES.parcial"; parar "a copia do estado de agora saiu truncada, e por isso foi descartada."; }
  mv "$ANTES.parcial" "$ANTES"
  echo "COPIA DO ESTADO DE AGORA GRAVADA: $ANTES"
  echo "Nada foi restaurado. Rode de novo sem --copia-de-agora quando quiser voltar no tempo."
  exit 0
fi

if [ "$CONFIRMADO" -ne 1 ]; then
  echo "ISTO FOI SO UM ENSAIO. Nada foi mudado."
  echo
  echo "Se e isso mesmo que voce quer, rode a MESMA linha com a palavra no fim:"
  echo
  echo "  bash $0 $ARQUIVO --sim-eu-quero-sobrescrever"
  echo
  echo "Se quiser guardar o estado de AGORA antes (recomendado):"
  echo
  echo "  bash $0 $ARQUIVO --copia-de-agora"
  exit 0
fi

# --- A RESTAURACAO DE VERDADE. ----------------------------------------------
echo "== RESTAURANDO =="
if [ -n "$SERVICOS" ]; then
  echo "1) parando a celula '$CELULA' para o banco nao mudar no meio da troca"
  $COMPOSE stop $SERVICOS || parar "nao consegui parar os servicos da celula '$CELULA'. Como o banco continuaria mudando durante a troca, eu nao restauro."
fi

echo "2) devolvendo o banco '$BASE' ao estado do arquivo"
# `--clean --if-exists` derruba o que existe antes de recriar; `--exit-on-error`
# faz o primeiro erro parar tudo, em vez de deixar um banco meio restaurado
# parecendo pronto. O veredito vem do COMANDO, e nao de um pipe.
ESTADO_DO_RESTORE=0
$COMPOSE exec -T postgres pg_restore -U postgres -d "$BASE" --clean --if-exists --exit-on-error --no-owner < "$ARQUIVO" \
  || ESTADO_DO_RESTORE=$?

if [ -n "$SERVICOS" ]; then
  echo "3) subindo a celula '$CELULA' de novo"
  $COMPOSE up -d $SERVICOS || echo "AVISO: nao consegui subir '$CELULA' automaticamente. Suba a mao com: cd $RAIZ && $COMPOSE up -d $SERVICOS"
fi

if [ "$ESTADO_DO_RESTORE" -ne 0 ]; then
  echo
  echo "PAROU POR SEGURANCA: a restauracao do banco '$BASE' FALHOU no meio (codigo $ESTADO_DO_RESTORE)."
  echo "O banco pode ter ficado num estado misto. NAO tente de novo as cegas:"
  echo "  - a lista de copias esta em $RAIZ/backups-de-banco/"
  echo "  - a mensagem de erro do Postgres esta logo acima desta linha"
  echo "Mande essa mensagem para quem estiver ajudando antes de mexer mais."
  exit 1
fi

echo
echo "PRONTO. O banco '$BASE' voltou ao estado de $NOME_DO_ARQUIVO."
echo "A celula '$CELULA' esta subindo de novo. Confira o site em alguns segundos."
echo "RESTAURACAO-CONCLUIDA: $BASE de $NOME_DO_ARQUIVO"
