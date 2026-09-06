#!/usr/bin/env bash
# =============================================================================
# ABRIR A FILA DA CONFERÊNCIA DO PORTFÓLIO — o passo do mantenedor.
#
# Quem confere o portfólio do aluno é TODO ADMINISTRADOR DA ESCOLA. Foi decisão
# dele, em 06/09/2026: até ali a permissão morava numa lista de pessoas escrita
# à mão no env da VPS, que era uma segunda casa do mesmo fato — promover alguém
# pela tela de `/admin/escola/` não abria a fila, e as duas listas discordavam
# sem ninguém perceber.
#
# Para obedecer a isso, a célula `pages` PERGUNTA à célula `admin` se a pessoa é
# administradora (`contracts/admin.openapi.yaml`, operação `isAdministrator`).
# Perguntar exige credencial, e credencial não viaja por esteira (INV-P8,
# Lei 5): o `deploy-infra.yml` diz de si mesmo que JAMAIS toca `infra/env/` nem
# `/opt/plataforma/env/`. Por isso este passo é seu, e por isso este arquivo
# existe — para ele ser UMA linha, e não um texto para colar.
#
# COMO RODAR (dentro da VPS, uma linha só, SEM argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-par-do-portfolio-com-a-admin.sh -o /tmp/a.sh && bash /tmp/a.sh
#
# NÃO PERGUNTA NADA e NÃO PEDE NADA. Você não digita e-mail nenhum: esta é
# exatamente a diferença que a mudança comprou. O segredo é gerado AQUI, dentro
# da VPS, e gravado direto nos arquivos — não aparece na tela, não passa por
# agente, não entra no Git (`armadilhas/090`).
#
# É IDEMPOTENTE E NÃO ROTACIONA. Se o par já existir, ele é REUSADO, nunca
# regerado: trocar um token em uso derrubaria as chamadas até o container do
# outro lado reiniciar, e o sintoma seria 401 intermitente. Rodar de novo é
# seguro e é a cura de qualquer dúvida.
#
# O QUE ELE LIGA (e a ordem é deliberada — PROVEDOR PRIMEIRO):
#
#   1. env/admin.env   TOKENS_ACEITOS_PAGES
#   2. env/pages.env   ADMIN_API_URL, ADMIN_API_TOKEN
#
# Provedor antes de consumidor porque a ordem inversa tem janela ruim: o
# consumidor com token que o provedor ainda não aceita responde 401 para gente
# de verdade. Ao contrário, um provedor que aceita um token que ninguém usa
# ainda não faz nada — e é uma janela sem sintoma.
#
# O ENDEREÇO NÃO É ESCOLHA DESTE SCRIPT: ele sai do `servers:` do contrato
# congelado da `admin`, e termina em `/interno`. Ele NÃO leva o `/admin` do
# `SCRIPT_NAME` dela: aquele prefixo é do caminho público, cortado pelo próprio
# Django, e aqui a conversa é de container para container, direto na porta 8000
# (`armadilhas/029` e `armadilhas/186`). Mudar o endereço aqui sem mudar no
# contrato é a forma mais silenciosa de quebrar a ligação, porque os dois lados
# continuariam "certos" cada um por si.
#
# POR QUE ELE NÃO É O `provisionar-pages.sh` NEM O `provisionar-admin.sh`:
# aqueles dois reescrevem o env inteiro da célula deles e ROTACIONAM a senha do
# banco e a chave do Django no caminho. As duas células já estão no ar, e girar
# a senha do banco de uma célula viva para escrever um token seria pagar caro
# por uma linha. Este roteiro só ACRESCENTA as chaves e recarrega as duas.
#
# O QUE ACONTECE SE UM DAQUELES DOIS RODAR DEPOIS DESTE: nada se perde. Desde
# 06/09/2026 os dois CONHECEM as chaves deste par e as RELEEM do arquivo vivo
# antes de reescrever, em vez de as apagar (`armadilhas/111`).
#
# SE ALGO ESTIVER ESTRANHO, ELE PARA E NÃO MEXE EM NADA. Toda parada começa com
# "PAROU POR SEGURANÇA" e diz o que fazer.
# =============================================================================

# O modo de falha de 24/08 em pessoa: carregado com `source`/`.`, um `exit` daqui
# derrubaria a sessão do mantenedor. Com `bash /tmp/a.sh` o exit morre no filho.
# Este guarda vem ANTES de qualquer outra coisa, inclusive da checagem de bash:
# a ordem inversa deixaria a primeira recusa possível derrubar a sessão.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANÇA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessão. Rode com a palavra bash na frente: bash /tmp/a.sh"
  return 1 2>/dev/null || exit 1
fi

if [ -z "${BASH_VERSION:-}" ]; then
  echo "PAROU POR SEGURANÇA: rode com bash, não com sh:"
  echo "  bash /tmp/a.sh"
  exit 1
fi

set -u

parar() { echo "PAROU POR SEGURANÇA: $1"; exit 1; }

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ENV_ADMIN="env/admin.env"
ENV_PAGES="env/pages.env"
# A referência de dono/permissão: um env que JÁ funciona nesta máquina.
ENV_REF="$ENV_ADMIN"

# O endereço interno da área administrativa sai do `servers:` do contrato
# congelado dela (`contracts/admin.openapi.yaml`), e não é escolha deste script.
ADMIN_URL="http://admin:8000/interno"

LINHA_DO_BANCO="curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-pages.sh -o /tmp/p.sh && bash /tmp/p.sh"

# -----------------------------------------------------------------------------
# 1. ONDE — a pasta da plataforma e os dois arquivos de que dependo.
#    Tudo conferido ANTES de gerar ou escrever coisa nenhuma.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ. Você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…, nunca PS C:\\>)"

if [ ! -f "$ENV_PAGES" ]; then
  echo "PAROU POR SEGURANÇA: não achei $RAIZ/$ENV_PAGES."
  echo
  echo "O env das Páginas do aluno nasce junto com o banco delas, e essa linha"
  echo "ainda não rodou nesta máquina. Eu NÃO crio esse arquivo: quem o cria é a"
  echo "linha do banco."
  echo
  echo "Cole PRIMEIRO esta linha, aqui mesmo, e depois a minha de novo:"
  echo
  echo "  $LINHA_DO_BANCO"
  echo
  echo "Nada foi criado, nada foi alterado."
  exit 1
fi
[ -f "$ENV_ADMIN" ] || parar "não achei $RAIZ/$ENV_ADMIN. A área administrativa não está provisionada nesta máquina, e é ela quem responde quem é administrador. Rode antes o infra/provisionar-admin.sh. Nada foi alterado."
for arquivo in "$ENV_ADMIN" "$ENV_PAGES"; do
  [ -w "$arquivo" ] || parar "não consigo escrever em $RAIZ/$arquivo. Rode como root ou como o dono dos env. Nada foi alterado."
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
#    Quem manda é o PROVEDOR: o valor vem da lista de aceitos da `admin`, e o
#    consumidor é realinhado a ela. A direção importa: alinhar pelo consumidor
#    deixaria uma célula qualquer mudar o que o provedor aceita.
# -----------------------------------------------------------------------------
T_PAGES="$(ler_de "$ENV_ADMIN" TOKENS_ACEITOS_PAGES)"
NOVO=0
if [ -z "$T_PAGES" ]; then
  T_PAGES="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
  NOVO=1
fi
[ ${#T_PAGES} -ge 32 ] || parar "o token do par pages->admin ficou curto demais. Nada foi alterado."

# TOKEN É POR PAR. Se este valor já estiver servindo a OUTRO par no env da
# `admin`, a fronteira que os pares existem para criar deixa de existir: girar
# um derrubaria o outro, sem aviso. Conferido ANTES de escrever.
for OUTRA in $(grep -oE '^TOKENS_ACEITOS_[A-Z0-9_]+=' "$ENV_ADMIN" 2>/dev/null | tr -d '=' ); do
  [ "$OUTRA" = "TOKENS_ACEITOS_PAGES" ] && continue
  [ "$(ler_de "$ENV_ADMIN" "$OUTRA")" = "$T_PAGES" ] \
    && parar "o token deste par é IGUAL ao de $OUTRA em $ENV_ADMIN. Token é por par, e um só faria a rotação de um derrubar o outro sem aviso. Nada foi alterado. Me mande esta tela inteira."
done

echo "== estado ANTES =="
printf '  %-24s %s\n' "$ENV_ADMIN" "encontrado ($(wc -l < "$ENV_ADMIN") linhas)"
printf '  %-24s %s\n' "$ENV_PAGES" "encontrado ($(wc -l < "$ENV_PAGES") linhas)"
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
    grep -q "^# $cabecalho" "$arq" || printf '\n# %s\n# Escrito por infra/provisionar-par-do-portfolio-com-a-admin.sh (CS-PAGES-0001, AC-11).\n' "$cabecalho" >> "$arq"
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
      || parar "não consegui ajustar o dono de $arq. Rode como root ou como o dono dos env. As cópias intactas estão em $RAIZ ($BACKUPS)."
    chmod --reference="$ENV_REF" "$arq" 2>/dev/null \
      || parar "não consegui ajustar as permissões de $arq. Rode como root. As cópias intactas estão em $RAIZ ($BACKUPS)."
  fi

  case "$MEXIDOS" in *" $arq"*) : ;; *) MEXIDOS="$MEXIDOS $arq" ;; esac
}

# PROVEDOR PRIMEIRO — ver o cabeçalho deste arquivo.
garantir "$ENV_ADMIN" TOKENS_ACEITOS_PAGES "$T_PAGES" "par pages->admin: a fila do portfolio pergunta quem e administrador da escola"
garantir "$ENV_PAGES" ADMIN_API_URL "$ADMIN_URL" "par pages->admin"
garantir "$ENV_PAGES" ADMIN_API_TOKEN "$T_PAGES" "par pages->admin"

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

A="$(ler_de "$ENV_ADMIN" TOKENS_ACEITOS_PAGES)"
B="$(ler_de "$ENV_PAGES" ADMIN_API_TOKEN)"
if [ -n "$A" ] && [ "$A" = "$B" ] && [ "$A" = "$T_PAGES" ]; then
  printf '  %-24s %s\n' "par pages->admin" "confere dos dois lados"
else
  parar "o par NÃO ficou igual nos dois lados ($ENV_ADMIN/TOKENS_ACEITOS_PAGES e $ENV_PAGES/ADMIN_API_TOKEN). Isso daria 401 silencioso. As cópias intactas estão em $RAIZ ($BACKUPS). Me mande esta tela inteira."
fi

[ "$(ler_de "$ENV_PAGES" ADMIN_API_URL)" = "$ADMIN_URL" ] \
  || parar "ADMIN_API_URL não ficou como o contrato congelado manda em $ENV_PAGES. As cópias intactas estão em $RAIZ ($BACKUPS). Me mande esta tela inteira."
printf '  %-24s %s\n' "endereço" "o do contrato congelado da admin"

# Chave repetida é o modo de falha mais traiçoeiro de um env: o Docker Compose
# usa a ÚLTIMA, e um valor velho ficaria por baixo sem nada acusar.
for par in "$ENV_ADMIN:TOKENS_ACEITOS_PAGES" "$ENV_PAGES:ADMIN_API_URL" "$ENV_PAGES:ADMIN_API_TOKEN"; do
  arq="${par%%:*}"; chave="${par##*:}"
  n="$(grep -c "^$chave=" "$arq")"
  [ "$n" -eq 1 ] || parar "a chave $chave aparece $n vezes em $arq, e o Docker Compose usaria só a última. As cópias intactas estão em $RAIZ ($BACKUPS). Me mande esta tela inteira."
done
echo "  chaves repetidas ........ nenhuma (conferido nas 3)"
echo

# -----------------------------------------------------------------------------
# 5. RECARREGAR — para não depender da próxima entrega. Aviso, nunca parada:
#    os arquivos JÁ estão certos, e o env é lido no start de cada container.
#    JAMAIS `docker compose up -d` sem argumento: isso devolveria TODAS as
#    células à tag :main do compose (RITOS §4). Só estes serviços, pelo nome.
# -----------------------------------------------------------------------------
echo "== recarregando as duas células =="
if command -v docker >/dev/null 2>&1; then
  ALVOS=""
  # Ordem: provedor, depois quem pergunta.
  for servico in admin pages; do
    if docker compose ps --services 2>/dev/null | grep -qx "$servico"; then
      ALVOS="$ALVOS $servico"
    fi
  done
  if [ -n "$ALVOS" ]; then
    if docker compose up -d $ALVOS >/dev/null 2>&1; then
      echo "  recarreguei:$ALVOS"
    else
      echo "  (aviso: não consegui recarregar$ALVOS. Os arquivos JÁ estão certos; a próxima entrega de cada célula relê o env. Avise o agente.)"
    fi
  else
    echo "  (aviso: não achei estes serviços no compose desta máquina. A próxima entrega relê o env.)"
  fi
else
  echo "  (aviso: não achei o docker aqui. Os arquivos JÁ estão certos; a próxima entrega relê o env.)"
fi
echo

echo "A partir de agora, quem confere o portfólio dos alunos é todo administrador"
echo "da escola: promover alguém pela tela de administradores abre a fila para"
echo "essa pessoa sozinho, e não há mais lista nenhuma para alguém esquecer de"
echo "atualizar. Rodar esta mesma linha de novo é seguro: o segredo que já existe"
echo "é reusado, nunca trocado."
echo
echo "COMO CONFERIR: entre no site como administrador e abra"
echo "meshcraft.top/pages/equipe — a fila dos portfólios à espera aparece."
echo
echo "PRONTO: a fila da conferência do portfólio está aberta."
