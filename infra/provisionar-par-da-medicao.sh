#!/usr/bin/env bash
# =============================================================================
# LIGAR O PAINEL NA MEDIÇÃO — o passo do mantenedor.
#
# A célula `metricas` (o livro de fatos) guarda a HISTÓRIA dos números da escola,
# e a `admin` é quem os MOSTRA. Pela Lei 3 o Admin não lê o banco da medição: ele
# PERGUNTA, pela porta de leitura, com o contrato congelado
# (`contracts/metricas.openapi.yaml`). Perguntar exige credencial, e credencial
# não viaja por esteira (INV-P8, Lei 5): o `deploy-infra.yml` diz de si mesmo que
# JAMAIS toca `infra/env/` nem `/opt/plataforma/env/`. Por isso este passo é seu,
# e por isso este arquivo existe — para ele ser UMA linha, e não um texto para
# colar.
#
# COMO RODAR (dentro da VPS, uma linha só, SEM argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-par-da-medicao.sh -o /tmp/p.sh && bash /tmp/p.sh
#
# A JANELA CERTA: rode DEPOIS de a `metricas` e a `admin` terem subido com o
# código novo (o deploy do PR #1003 já fez isso). Antes disso ele funciona igual
# — os arquivos ficam certos e a próxima entrega os relê.
#
# NÃO PERGUNTA NADA e NÃO PEDE NADA. O segredo é gerado AQUI, dentro da VPS, e
# gravado direto nos arquivos: não aparece na tela, não passa por agente, não
# entra no Git (`armadilhas/090`).
#
# É IDEMPOTENTE E NÃO ROTACIONA. Se o par já existir, ele é REUSADO — nunca
# regerado. Trocar um token em uso derrubaria as chamadas até o container do
# outro lado reiniciar, e o sintoma seria 401 intermitente. Rodar de novo é
# seguro e é a cura de qualquer dúvida.
#
# O QUE ELE LIGA (e a ordem é deliberada — PROVEDOR PRIMEIRO):
#
#   1. env/metricas.env   TOKENS_ACEITOS_ADMIN
#   2. env/admin.env      METRICAS_API_URL, METRICAS_API_TOKEN
#
# Provedor antes de consumidor porque a ordem inversa tem janela ruim: o
# consumidor com token que o provedor ainda não aceita responde 401 para gente
# de verdade. Ao contrário, um provedor que aceita um token que ninguém usa
# ainda não faz nada — e é uma janela sem sintoma.
#
# O ENDEREÇO NÃO É ESCOLHA DESTE SCRIPT: ele sai do `servers:` do contrato
# congelado da célula. Mudá-lo aqui sem mudar lá é a forma mais silenciosa de
# quebrar a ligação, porque os dois lados continuariam "certos" cada um por si.
#
# O QUE ACONTECE SE `provisionar-metricas.sh` RODAR DEPOIS DESTE: ele reescreve
# `env/metricas.env` do ZERO, a partir de um heredoc que não conhece
# `TOKENS_ACEITOS_ADMIN`. Ele NÃO vai apagá-la em silêncio — tem a trava de
# deriva (`CHAVES_QUE_EU_GERO`) e PARA com "PAROU POR SEGURANÇA" listando o que
# não sabe gerar. É o comportamento certo, e é bom saber de antemão o que a tela
# vai dizer: se isso acontecer, rode este script de novo depois dele.
#
# SE ALGO ESTIVER ESTRANHO, ELE PARA E NÃO MEXE EM NADA. Toda parada começa com
# "PAROU POR SEGURANÇA" e diz o que fazer.
# =============================================================================

# O modo de falha de 24/08 em pessoa: carregado com `source`/`.`, um `exit` daqui
# derrubaria a sessão do mantenedor. Com `bash /tmp/p.sh` o exit morre no filho.
# Este guarda vem ANTES de qualquer outra coisa, inclusive da checagem de bash:
# a ordem inversa deixaria a primeira recusa possível derrubar a sessão.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANÇA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessão. Rode com a palavra bash na frente: bash /tmp/p.sh"
  return 1 2>/dev/null || exit 1
fi

if [ -z "${BASH_VERSION:-}" ]; then
  echo "PAROU POR SEGURANÇA: rode com bash, não com sh:"
  echo "  bash /tmp/p.sh"
  exit 1
fi

set -u

parar() { echo "PAROU POR SEGURANÇA: $1"; exit 1; }

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ENV_METRICAS="env/metricas.env"
ENV_ADMIN="env/admin.env"
# A referência de dono/permissão: um env que JÁ funciona nesta máquina.
ENV_REF="$ENV_METRICAS"

# O endereço interno da medição sai do `servers:` do contrato congelado dela
# (`contracts/metricas.openapi.yaml`), e não é escolha deste script.
MEDICAO_URL="http://metricas:8000/api/metricas"

# -----------------------------------------------------------------------------
# 1. ONDE — a pasta da plataforma e os dois arquivos de que dependo.
#    Tudo conferido ANTES de gerar ou escrever coisa nenhuma.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ — você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…)"
for arquivo in "$ENV_METRICAS" "$ENV_ADMIN"; do
  [ -f "$arquivo" ] || parar "não achei $RAIZ/$arquivo — alguma das duas células não está provisionada nesta máquina. Se faltar o da medição, rode antes o provisionar-metricas.sh. Nada foi criado, nada foi alterado."
  [ -w "$arquivo" ] || parar "não consigo escrever em $RAIZ/$arquivo — rode como root ou como o dono dos env. Nada foi alterado."
done

ler_de() {  # arquivo, chave — devolve o valor limpo, sem comentário nem espaços
  grep "^$2=" "$1" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | tr -d '[:space:]'
}

gerar_segredo() {
  # `openssl` primeiro; `/dev/urandom` como caminho alternativo MEDIDO, nunca
  # silencioso — se nenhum dos dois existir, o script para em vez de gravar um
  # valor fraco.
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  elif [ -r /dev/urandom ]; then
    head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'
  else
    return 1
  fi
}

# -----------------------------------------------------------------------------
# 2. O VALOR — reusado se já existe, gerado só se falta.
# -----------------------------------------------------------------------------
T_ADMIN="$(ler_de "$ENV_METRICAS" TOKENS_ACEITOS_ADMIN)"
NOVO=0
if [ -z "$T_ADMIN" ]; then
  T_ADMIN="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
  NOVO=1
fi
[ ${#T_ADMIN} -ge 32 ] || parar "o token do par admin→metricas ficou curto demais. Nada foi alterado."

echo "== estado ANTES =="
printf '  %-24s %s\n' "$ENV_METRICAS" "encontrado ($(wc -l < "$ENV_METRICAS") linhas)"
printf '  %-24s %s\n' "$ENV_ADMIN" "encontrado ($(wc -l < "$ENV_ADMIN") linhas)"
if [ "$NOVO" -eq 0 ]; then
  echo "  segredo ................. o par JÁ existia; vou reusar, não regerar"
else
  echo "  segredo ................. vou gerar um novo (é a primeira vez)"
fi
echo

# -----------------------------------------------------------------------------
# 3. ESCRITA — uma chave por vez, com cópia de segurança por arquivo.
# -----------------------------------------------------------------------------
MEXIDOS=""
BACKUPS=""

garantir() {  # arquivo, chave, valor, cabeçalho-do-bloco
  arq="$1"; chave="$2"; valor="$3"; cabecalho="$4"
  atual="$(ler_de "$arq" "$chave")"
  [ "$atual" = "$valor" ] && return 0

  case "$BACKUPS" in
    *"$arq:"*) : ;;  # já tem cópia deste arquivo nesta execução
    *)
      b="$arq.bak-$(date +%s)"
      cp -a "$arq" "$b" 2>/dev/null || parar "não consegui guardar a cópia de segurança de $arq. Não mexi em nada."
      BACKUPS="$BACKUPS $arq:$b"
      ;;
  esac

  if grep -q "^$chave=" "$arq"; then
    sed -i "s|^$chave=.*|$chave=$valor|" "$arq" \
      || parar "a edição de $arq falhou. As cópias intactas estão em $RAIZ ($BACKUPS)."
  else
    # Sem esta guarda, um arquivo que não termina em quebra de linha grudaria a
    # chave nova no fim da última linha — e a última linha de um env é um valor.
    if [ -s "$arq" ] && [ "$(tail -c 1 "$arq" | wc -l)" -eq 0 ]; then
      printf '\n' >> "$arq" || parar "não consegui escrever em $arq. As cópias intactas estão em $RAIZ ($BACKUPS)."
    fi
    grep -q "^# $cabecalho" "$arq" || printf '\n# %s\n# Escrito por infra/provisionar-par-da-medicao.sh (PLANO-PAINEL-DE-GESTAO §6.2).\n' "$cabecalho" >> "$arq"
    printf '%s=%s\n' "$chave" "$valor" >> "$arq" \
      || parar "não consegui escrever em $arq. As cópias intactas estão em $RAIZ ($BACKUPS)."
  fi

  # DONO E MODO copiados de um env que JÁ FUNCIONA, nunca escolhidos por mim
  # (`armadilhas/091`): rodando como root, o `sed -i` recria o arquivo e pode
  # deixá-lo root:root — e o usuário `deploy`, que é quem o pipeline usa, não lê
  # um 600 de root. O `deploy-infra` reprova com "permission denied" na
  # validação do compose, e a mensagem não diz quem não conseguiu ler.
  if [ "$(stat -c '%U:%G %a' "$arq" 2>/dev/null)" != "$(stat -c '%U:%G %a' "$ENV_REF" 2>/dev/null)" ]; then
    chown --reference="$ENV_REF" "$arq" 2>/dev/null \
      || parar "não consegui ajustar o dono de $arq — rode como root ou como o dono dos env. As cópias intactas estão em $RAIZ ($BACKUPS)."
    chmod --reference="$ENV_REF" "$arq" 2>/dev/null \
      || parar "não consegui ajustar as permissões de $arq — rode como root. As cópias intactas estão em $RAIZ ($BACKUPS)."
  fi

  case "$MEXIDOS" in *" $arq"*) : ;; *) MEXIDOS="$MEXIDOS $arq" ;; esac
}

# PROVEDOR PRIMEIRO — ver o cabeçalho deste arquivo.
garantir "$ENV_METRICAS" TOKENS_ACEITOS_ADMIN "$T_ADMIN" "par admin→metricas: o painel le a historia dos numeros"
garantir "$ENV_ADMIN" METRICAS_API_URL "$MEDICAO_URL" "par admin→metricas"
garantir "$ENV_ADMIN" METRICAS_API_TOKEN "$T_ADMIN" "par admin→metricas"

# -----------------------------------------------------------------------------
# 4. ESTADO DEPOIS — a conferência que fecha o assunto. Compara SEM imprimir
#    segredo: o que vai para a tela é "confere / não confere", nunca o valor.
# -----------------------------------------------------------------------------
echo "== estado DEPOIS =="
if [ -z "$MEXIDOS" ]; then
  echo "  o que eu fiz ............ nada: já estava tudo ligado"
else
  echo "  arquivos alterados ......$MEXIDOS"
  echo "  cópias de segurança .....$BACKUPS"
fi

A="$(ler_de "$ENV_METRICAS" TOKENS_ACEITOS_ADMIN)"
B="$(ler_de "$ENV_ADMIN" METRICAS_API_TOKEN)"
if [ -n "$A" ] && [ "$A" = "$B" ] && [ "$A" = "$T_ADMIN" ]; then
  printf '  %-24s %s\n' "par admin→metricas" "confere dos dois lados"
else
  parar "o par NÃO ficou igual nos dois lados ($ENV_METRICAS/TOKENS_ACEITOS_ADMIN e $ENV_ADMIN/METRICAS_API_TOKEN). Isso daria 401 silencioso. As cópias intactas estão em $RAIZ ($BACKUPS) — me mande esta tela inteira."
fi
echo

# -----------------------------------------------------------------------------
# 5. RECARREGAR — para não depender da próxima entrega. Aviso, nunca parada:
#    os arquivos JÁ estão certos, e o env é lido no start de cada container.
# -----------------------------------------------------------------------------
echo "== recarregando as duas células =="
if command -v docker >/dev/null 2>&1; then
  ALVOS=""
  for servico in metricas admin; do
    if docker compose ps --services 2>/dev/null | grep -qx "$servico"; then
      ALVOS="$ALVOS $servico"
    fi
  done
  if [ -n "$ALVOS" ]; then
    if docker compose up -d $ALVOS >/dev/null 2>&1; then
      echo "  recarreguei:$ALVOS"
    else
      echo "  (aviso: não consegui recarregar$ALVOS — os arquivos JÁ estão certos; a próxima entrega de cada célula relê o env. Avise o agente.)"
    fi
  else
    echo "  (aviso: não achei estes serviços no compose desta máquina — a próxima entrega relê o env.)"
  fi
else
  echo "  (aviso: não achei o docker aqui — os arquivos JÁ estão certos; a próxima entrega relê o env.)"
fi
echo

echo "A partir de agora o painel consegue perguntar à medição o que aconteceu no"
echo "passado, em vez de só saber o presente. Rodar esta mesma linha de novo é"
echo "seguro: o segredo que já existe é reusado, nunca trocado."
echo
echo "PRONTO: o painel está ligado na medição."
