#!/usr/bin/env bash
# =============================================================================
# LIGAR O E-MAIL DE VERDADE — o passo do mantenedor.
#
# Até 02/09/2026 esta plataforma NUNCA mandou um e-mail: o código dizia
# "Stub: loga o envio" e voltava sem erro, e a ficha de auditoria anotava
# "enviado/ok" para cartas que nunca saíram (`armadilhas/290`). O envio virou de
# verdade no PR #879 — e agora ele é FAIL-CLOSED: sem as variáveis abaixo,
# nenhum e-mail sai E NENHUMA LINHA É MARCADA COMO ENVIADA. Nada quebra: a
# plataforma continua avisando pelo sininho, como sempre fez.
#
# ENV NÃO VIAJA POR PIPELINE (INV-P8, Lei 5). O `deploy-infra.yml` diz de si
# mesmo que JAMAIS toca `infra/env/` nem `/opt/plataforma/env/`. Por isso estas
# linhas só existem se o mantenedor as puser na VPS — e por isso este arquivo
# existe: para esse passo ser UMA linha, e não um texto para colar.
#
# O PROVEDOR É O BREVO, escolha do mantenedor em 02/09/2026 entre três opções
# com o custo de cada uma na mesa (o painel dele é em português, e quem vai
# mexer nele depois é ele). Mas o que se grava aqui é SMTP puro — se um dia ele
# trocar de empresa, é rodar esta mesma linha com outro host e outro login, sem
# tocar em código nenhum.
#
# COMO O MANTENEDOR RODA (dentro da VPS, uma linha só):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-email.sh -o /tmp/p.sh && bash /tmp/p.sh SEU_LOGIN_SMTP
#
# Ele vai PERGUNTAR a chave, com digitação invisível. Opcionalmente:
#   bash /tmp/p.sh SEU_LOGIN_SMTP escola@meshcraft.top voce@gmail.com
#                  ^login          ^remetente           ^para onde mandar o teste
#
# A CHAVE NÃO É ARGUMENTO, E ISSO É LEI DA CASA (`armadilhas/090`). Argumento
# vaza por quatro caminhos: a tela, o `~/.bash_history`, o `ps aux` de qualquer
# processo do host, e — o que mais pega — o print que a pessoa manda ao agente
# para provar que funcionou. O login SMTP e o remetente são públicos por
# desenho (o remetente vai no cabeçalho de todo e-mail que sai), então esses
# podem ser argumento: tratar tudo como segredo cansa o mantenedor, tratar tudo
# como público vaza.
#
# NÃO REESCREVE O ENV. `env/mensageria.env` está VIVO e é compartilhado pelos
# TRÊS containers da célula (web, consumer e huey). Refazê-lo rotacionaria a
# senha do banco em uso. Este script acrescenta ou atualiza CINCO linhas, e o
# resto do arquivo continua byte a byte como estava.
#
# IDEMPOTENTE: rodar de novo é seguro. Chave que já existe com o mesmo valor não
# é tocada; com valor diferente é ATUALIZADA em vez de duplicada — chave repetida
# num env_file faz o Docker Compose usar só a última, e o valor velho ficaria por
# baixo sem nada acusar.
#
# QUEM PRECISA DISTO ANTES: o domínio remetente tem de estar verificado no Brevo,
# com os registros de DNS (o TXT `brevo-code`, os dois CNAME de DKIM e o TXT
# `_dmarc`) já no provedor de DNS do domínio. Esse provedor, para o meshcraft.top,
# é a HOSTINGER, e NÃO o Cloudflare: os nameservers são pixel.dns-parking.com e
# byte.dns-parking.com, medidos em 06/09/2026. Até essa data este arquivo dizia
# Cloudflare e mandava o mantenedor procurar o domínio numa conta que nunca
# existiu. Sem os registros o Brevo aceita a conexão e o Gmail joga a carta em spam — este script
# não tem como conferir isso da VPS, e diz isso em voz alta no fim.
# =============================================================================

set -u

parar() { echo "PAROU POR SEGURANÇA: $1"; exit 1; }

# Só para os testes fora da VPS. O mantenedor nunca define isto: o valor de
# verdade é /opt/plataforma, e é o que vale quando ele cola a linha.
RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ENV_ALVO="env/mensageria.env"
ENV_REF="env/alunos.env"

# O host do Brevo. Fica aqui e não em argumento porque é consequência da escolha
# do provedor, não uma decisão nova a cada execução — e um host digitado errado
# falharia só na hora de mandar, longe daqui.
HOST_PADRAO="smtp-relay.brevo.com"
PORTA_PADRAO="587"

SMTP_HOST="${SMTP_HOST_ESCOLHIDO:-$HOST_PADRAO}"
SMTP_PORT="${SMTP_PORT_ESCOLHIDA:-$PORTA_PADRAO}"
SMTP_USER="${1:-}"
SMTP_FROM="${2:-escola@meshcraft.top}"
TESTE_PARA="${3:-}"

# -----------------------------------------------------------------------------
# 1. OS VALORES PÚBLICOS — validados ANTES de tocar em arquivo nenhum.
# -----------------------------------------------------------------------------
FORMATO_EMAIL='^[a-z0-9]([a-z0-9._%+-]*[a-z0-9])?@[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*\.[a-z][a-z]+$'

limpar() { printf '%s' "$1" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//'; }

SMTP_USER="$(limpar "$SMTP_USER")"
SMTP_FROM="$(limpar "$(printf '%s' "$SMTP_FROM" | tr 'A-Z' 'a-z')")"
TESTE_PARA="$(limpar "$(printf '%s' "$TESTE_PARA" | tr 'A-Z' 'a-z')")"

[ -n "$SMTP_USER" ] || parar "você não me disse o login SMTP. No Brevo ele fica na seção 'SMTP & API' e parece um e-mail ou um número. Rode de novo assim:  bash /tmp/p.sh SEU_LOGIN_SMTP"

case "$SMTP_USER" in
  *SEU_LOGIN*|*seu_login*|*COLE_*|*cole_*)
    parar "'$SMTP_USER' ainda é o texto de exemplo, não o seu login de verdade. Nada foi alterado." ;;
esac

printf '%s' "$SMTP_FROM" | LC_ALL=C grep -qE "$FORMATO_EMAIL" \
  || parar "'$SMTP_FROM' não tem cara de e-mail. O remetente é o endereço que aparece para quem recebe, no formato nome@meshcraft.top. Nada foi alterado."

case "$SMTP_FROM" in
  *@meshcraft.top) : ;;
  *) echo "AVISO: o remetente '$SMTP_FROM' não é do domínio meshcraft.top."
     echo "       Se ele não estiver verificado no Brevo, as cartas vão para spam."
     echo ;;
esac

if [ -n "$TESTE_PARA" ]; then
  printf '%s' "$TESTE_PARA" | LC_ALL=C grep -qE "$FORMATO_EMAIL" \
    || parar "'$TESTE_PARA' não tem cara de e-mail. É para onde eu mandaria a carta de teste. Nada foi alterado."
fi

# -----------------------------------------------------------------------------
# 2. A CHAVE — perguntada, nunca argumento, nunca impressa (`armadilhas/090`).
# -----------------------------------------------------------------------------
printf 'Cole a chave SMTP do Brevo e aperte Enter (NADA vai aparecer na tela): '
read -r -s SMTP_PASSWORD
echo
SMTP_PASSWORD="$(limpar "$SMTP_PASSWORD")"

[ -n "$SMTP_PASSWORD" ] || parar "a chave veio vazia. Nada foi alterado — rode a mesma linha de novo e cole a chave quando eu perguntar."

case "$SMTP_PASSWORD" in
  *COLE_*|*cole_*|*SUA_CHAVE*|*sua_chave*)
    parar "o que você colou ainda é o texto de exemplo, não a chave de verdade. Nada foi alterado." ;;
  *\ *)
    parar "a chave tem espaço no meio, o que costuma ser pedaço de outra coisa colado junto. Nada foi alterado — copie de novo, do começo ao fim, e rode a mesma linha." ;;
esac

# O `=` fecharia o valor no meio se aparecesse cru; `#` viraria comentário. Os
# dois quebrariam o arquivo em silêncio, e o container leria metade da chave.
case "$SMTP_PASSWORD" in
  *'#'*) parar "a chave tem um '#', que num arquivo de configuração vira começo de comentário e cortaria o valor pela metade. Me avise: eu troco a forma de gravar. Nada foi alterado." ;;
esac

# -----------------------------------------------------------------------------
# 3. ONDE — a pasta da plataforma e os arquivos de que dependo.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ — você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…; se começar com PS C: é a janela do seu computador)"
[ -f "$ENV_ALVO" ] || parar "não achei $RAIZ/$ENV_ALVO — a mensageria não parece provisionada nesta máquina. Nada foi criado."
[ -f "$ENV_REF" ] || parar "não achei $RAIZ/$ENV_REF — é dele que eu copio dono e permissões, e sem essa referência eu não escrevo (o env nasceria ilegível para o pipeline)."
[ -w "$ENV_ALVO" ] || parar "não consigo escrever em $RAIZ/$ENV_ALVO — rode como root ou como o dono dos outros env. Nada foi alterado."

ler_de() { grep "^$2=" "$1" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | tr -d '[:space:]'; }

# -----------------------------------------------------------------------------
# 4. ESTADO ANTES — a chave NUNCA é impressa, só o fato de existir.
# -----------------------------------------------------------------------------
echo "== estado ANTES =="
echo "  $ENV_ALVO ....... encontrado ($(wc -l < "$ENV_ALVO") linhas)"
for chave in SMTP_HOST SMTP_PORT SMTP_USER SMTP_FROM; do
  atual="$(ler_de "$ENV_ALVO" "$chave")"
  if [ -n "$atual" ]; then echo "  $chave ............ $atual"
  else echo "  $chave ............ (não existe)"; fi
done
if [ -n "$(ler_de "$ENV_ALVO" SMTP_PASSWORD)" ]; then
  echo "  SMTP_PASSWORD ........ já existe (não mostro, e vou substituir)"
else
  echo "  SMTP_PASSWORD ........ (não existe)"
fi
echo
echo "== o que vou gravar =="
echo "  servidor ............. $SMTP_HOST porta $SMTP_PORT"
echo "  login ................ $SMTP_USER"
echo "  remetente ............ $SMTP_FROM"
echo "  chave ................ (recebida, $(printf '%s' "$SMTP_PASSWORD" | wc -c) caracteres — não mostro o valor)"
echo

# -----------------------------------------------------------------------------
# 5. ESCRITA — cinco linhas, e só elas.
# -----------------------------------------------------------------------------
BACKUP="$ENV_ALVO.bak-$(date +%s)"
cp -a "$ENV_ALVO" "$BACKUP" 2>/dev/null \
  || parar "não consegui guardar a cópia de segurança de $ENV_ALVO. Não mexi em nada."

# Se o arquivo não terminar em quebra de linha, o `>>` grudaria a chave nova no
# fim da última linha — e a última linha de um env é um valor.
if [ -s "$ENV_ALVO" ] && [ "$(tail -c 1 "$ENV_ALVO" | wc -l)" -eq 0 ]; then
  printf '\n' >> "$ENV_ALVO" || parar "não consegui escrever em $ENV_ALVO. A cópia intacta está em $RAIZ/$BACKUP."
fi

grep -q "^# e-mail de verdade" "$ENV_ALVO" \
  || printf '\n# e-mail de verdade (SMTP). Escrito pelo infra/provisionar-email.sh.\n# Ausente ou vazio => nenhum e-mail sai E nenhuma linha e marcada como enviada.\n' >> "$ENV_ALVO"

gravar() {  # chave, valor — atualiza se existe, acrescenta se não
  if grep -q "^$1=" "$ENV_ALVO"; then
    # `|` como separador do sed, e o valor já foi validado contra espaço e `#`.
    # A chave pode conter `/`, que quebraria o separador tradicional.
    sed -i "s|^$1=.*|$1=$2|" "$ENV_ALVO" \
      || parar "a edição de $1 em $ENV_ALVO falhou. A cópia intacta está em $RAIZ/$BACKUP."
  else
    printf '%s=%s\n' "$1" "$2" >> "$ENV_ALVO" \
      || parar "não consegui escrever $1 em $ENV_ALVO. A cópia intacta está em $RAIZ/$BACKUP."
  fi
}

gravar SMTP_HOST "$SMTP_HOST"
gravar SMTP_PORT "$SMTP_PORT"
gravar SMTP_USER "$SMTP_USER"
gravar SMTP_PASSWORD "$SMTP_PASSWORD"
gravar SMTP_FROM "$SMTP_FROM"

# DONO E MODO copiados de um env que JÁ FUNCIONA, nunca escolhidos por mim
# (`armadilhas/091`): rodando como root, o `sed -i` recria o arquivo e pode
# deixá-lo root:root — e o usuário `deploy`, que é quem o pipeline usa, não lê um
# 600 de root. O deploy reprova com "permission denied" numa mensagem que não diz
# quem não conseguiu ler.
if [ "$(stat -c '%U:%G %a' "$ENV_ALVO" 2>/dev/null)" != "$(stat -c '%U:%G %a' "$ENV_REF" 2>/dev/null)" ]; then
  chown --reference="$ENV_REF" "$ENV_ALVO" 2>/dev/null \
    || parar "não consegui ajustar o dono de $ENV_ALVO — rode como root. A cópia intacta está em $RAIZ/$BACKUP."
  chmod --reference="$ENV_REF" "$ENV_ALVO" 2>/dev/null \
    || parar "não consegui ajustar as permissões de $ENV_ALVO — rode como root. A cópia intacta está em $RAIZ/$BACKUP."
fi

# -----------------------------------------------------------------------------
# 6. ESTADO DEPOIS — a conferência que fecha o assunto.
# -----------------------------------------------------------------------------
echo "== estado DEPOIS =="
falhou=0
for chave in SMTP_HOST SMTP_PORT SMTP_USER SMTP_FROM; do
  gravado="$(ler_de "$ENV_ALVO" "$chave")"
  repetida="$(grep -c "^$chave=" "$ENV_ALVO")"
  echo "  $chave ............ $gravado  (aparece $repetida vez(es))"
  [ "$repetida" -eq 1 ] || falhou=1
done
repetida_senha="$(grep -c '^SMTP_PASSWORD=' "$ENV_ALVO")"
tamanho_gravado="$(ler_de "$ENV_ALVO" SMTP_PASSWORD | wc -c)"
echo "  SMTP_PASSWORD ........ gravada, $tamanho_gravado caracteres  (aparece $repetida_senha vez(es))"
echo "  dono/modo do env ..... $(stat -c '%U:%G %a' "$ENV_ALVO" 2>/dev/null) (igual ao $ENV_REF: $(stat -c '%U:%G %a' "$ENV_REF" 2>/dev/null))"
echo "  cópia de segurança ... $BACKUP"
echo

[ "$falhou" -eq 0 ] || parar "alguma linha ficou repetida em $ENV_ALVO, e o Docker Compose usaria só a última. A cópia intacta está em $RAIZ/$BACKUP — me mande esta tela inteira."
[ "$repetida_senha" -eq 1 ] || parar "a linha SMTP_PASSWORD aparece $repetida_senha vezes em $ENV_ALVO. A cópia intacta está em $RAIZ/$BACKUP — me mande esta tela inteira."
# `wc -c` conta o \n que o `ler_de` já removeu; comparo pelo tamanho para provar
# que a chave chegou inteira, SEM imprimir o valor.
[ "$tamanho_gravado" -gt 1 ] || parar "a chave não ficou gravada em $ENV_ALVO. A cópia intacta está em $RAIZ/$BACKUP — me mande esta tela inteira."
if [ "$(stat -c '%U:%G %a' "$ENV_ALVO" 2>/dev/null)" != "$(stat -c '%U:%G %a' "$ENV_REF" 2>/dev/null)" ]; then
  parar "o dono/permissão de $ENV_ALVO ficou diferente do $ENV_REF, e assim o deploy reprovaria com 'permission denied'. A cópia intacta está em $RAIZ/$BACKUP."
fi

# -----------------------------------------------------------------------------
# 7. RECARREGAR — os três containers da célula leem o MESMO env.
#    JAMAIS `docker compose up -d` sem argumento: devolveria TODAS as células à
#    tag :main do compose (RITOS §4). Só os serviços da mensageria, pelo nome.
# -----------------------------------------------------------------------------
echo "== recarregando a mensageria para ela reler o env =="
RECARREGOU="nao"
if command -v docker >/dev/null 2>&1; then
  ALVOS=""
  for servico in mensageria mensageria-consumer mensageria-huey; do
    if docker compose config --services 2>/dev/null | grep -qx "$servico"; then
      ALVOS="$ALVOS $servico"
    fi
  done
  if [ -n "$ALVOS" ]; then
    if docker compose up -d $ALVOS >/dev/null 2>&1; then
      echo "  recarreguei:$ALVOS"
      RECARREGOU="sim"
    else
      echo "  (aviso: não consegui recarregar$ALVOS — o arquivo JÁ está certo; o próximo deploy da célula relê o env. Avise o agente.)"
    fi
  else
    echo "  (aviso: não achei os serviços da mensageria no compose desta máquina.)"
  fi
else
  echo "  (aviso: não achei o docker aqui — o arquivo JÁ está certo.)"
fi
echo

# -----------------------------------------------------------------------------
# 8. A CARTA DE TESTE — a única prova que vale, e ela é opcional.
# -----------------------------------------------------------------------------
if [ -n "$TESTE_PARA" ] && [ "$RECARREGOU" = "sim" ]; then
  echo "== mandando uma carta de teste para $TESTE_PARA =="
  if docker compose exec -T mensageria-huey python -c "
from django.core.mail import send_mail
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
n = send_mail(
    subject='Teste do e-mail da Meshcraft',
    message='Se voce esta lendo isto, o e-mail da plataforma esta funcionando.',
    from_email=os.environ['SMTP_FROM'],
    recipient_list=['$TESTE_PARA'],
    fail_silently=False,
)
print('cartas enviadas:', n)
" 2>&1 | tail -5; then
    echo
    echo "  Se a linha acima disser 'cartas enviadas: 1', o Brevo aceitou."
    echo "  AGORA CONFIRA NA CAIXA DE ENTRADA de $TESTE_PARA (e no spam)."
  else
    echo "  (a carta de teste não saiu — me mande esta tela inteira; o env JÁ está gravado.)"
  fi
  echo
fi

echo "O que este script NÃO consegue conferir, e por isso digo em voz alta:"
echo "  - se o domínio $SMTP_FROM está verificado no Brevo;"
echo "  - se os registros de DNS (brevo-code, DKIM e _dmarc) estão no provedor de"
echo "    DNS do domínio, que para o meshcraft.top é a HOSTINGER, não o Cloudflare."
echo "Sem eles o Brevo aceita a carta e o Gmail a joga em spam. A prova final é"
echo "abrir o e-mail recebido e ver SPF e DKIM com 'pass' no cabeçalho."
echo
echo "PRONTO: e-mail da plataforma ligado."
