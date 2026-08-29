#!/usr/bin/env bash
# =============================================================================
# LIGAR O AVISO DE LIBERAÇÃO — o passo do mantenedor.
#
# Decisão dele em 29/08/2026: quem está na fila passa a receber um aviso no
# sininho quando o acesso é liberado. Para endereçar essa carta é preciso o id
# de plataforma da pessoa, e só a `identidade` sabe traduzir e-mail em id
# (`findPersonByEmail`, Rito de Contrato do PR #524).
#
# Perguntar exige credencial, e credencial não viaja por esteira (Lei 5): o
# `deploy-infra.yml` diz de si mesmo que JAMAIS toca `infra/env/` nem
# `/opt/plataforma/env/`. Por isso este passo é seu, e por isso este arquivo
# existe — para ele ser UMA linha, e não um texto para colar.
#
# COMO RODAR (dentro da VPS, uma linha só, SEM argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-aviso-de-liberacao.sh -o /tmp/p.sh && bash /tmp/p.sh
#
# NÃO PERGUNTA NADA e NÃO PEDE NADA. O segredo que falta é gerado AQUI, dentro
# da VPS, e gravado direto nos arquivos: ele não aparece na tela, não passa por
# agente nenhum, e não entra no Git (`armadilhas/090`).
#
# É IDEMPOTENTE E NÃO ROTACIONA. Se o par já existir, ele é REUSADO — nunca
# regerado. Trocar um token em uso derrubaria as chamadas até o container do
# outro lado reiniciar, e o sintoma seria 401 intermitente. Rodar de novo é
# seguro, e é a cura de qualquer dúvida.
#
# O QUE ELE LIGA (três degraus, e a ordem é deliberada — PROVEDOR PRIMEIRO):
#
#   1. env/identidade.env  TOKENS_ACEITOS_ALUNOS  (quem pode chamar)
#   2. env/identidade.env  TOKENS_COMPLETOS_ALUNOS (o degrau a mais: quem manda
#                          um e-mail para a porta descobre se ele existe, e
#                          existência é informação sobre uma pessoa. É o MESMO
#                          valor do de cima — dois degraus sobre o mesmo token;
#                          valores diferentes dariam 403 silencioso)
#   3. env/alunos.env      IDENTIDADE_API_URL, IDENTIDADE_API_TOKEN
#
# Provedor antes de consumidor porque a ordem inversa tem janela ruim: o
# consumidor com token que o provedor ainda não aceita responde 401. Ao
# contrário, um provedor que aceita um token que ninguém usa ainda não faz nada
# — e é uma janela sem sintoma.
#
# SE ALGO AQUI FALHAR, NADA QUEBRA. A célula que guarda os alunos é fail-ABERTO
# nesta consulta: sem as chaves, ela libera do mesmo jeito e simplesmente não
# manda a carta. O único efeito de não rodar este script é o aviso não chegar.
# =============================================================================

# O modo de falha de 24/08 em pessoa: carregado com `source`/`.`, um `exit` daqui
# derrubaria a sessão do mantenedor. Com `bash /tmp/p.sh` o exit morre no filho.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANÇA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessão. Rode com a palavra bash na frente: bash /tmp/p.sh"
  return 1 2>/dev/null || exit 1
fi

set -u

parar() { echo "PAROU POR SEGURANÇA: $1"; exit 1; }

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ENV_ALUNOS="env/alunos.env"
ENV_IDENTIDADE="env/identidade.env"
# A referência de dono/permissão: um env que JÁ funciona nesta máquina.
ENV_REF="$ENV_ALUNOS"

# O endereço interno da `identidade` sai do `servers:` do contrato congelado
# dela (`contracts/identidade.openapi.yaml`), e não é escolha deste script.
IDENTIDADE_URL="http://identidade:8000/interno"

# -----------------------------------------------------------------------------
# 1. ONDE — a pasta da plataforma e os dois arquivos de que dependo.
#    Tudo conferido ANTES de gerar ou escrever coisa nenhuma.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ — você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…)"
for arquivo in "$ENV_ALUNOS" "$ENV_IDENTIDADE"; do
  [ -f "$arquivo" ] || parar "não achei $RAIZ/$arquivo — alguma das células não está provisionada nesta máquina. Nada foi criado, nada foi alterado."
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
TOKEN="$(ler_de "$ENV_IDENTIDADE" TOKENS_ACEITOS_ALUNOS)"
NOVO=0
if [ -z "$TOKEN" ]; then
  TOKEN="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
  NOVO=1
fi
[ ${#TOKEN} -ge 32 ] || parar "o token do par alunos→identidade ficou curto demais. Nada foi alterado."

echo "== estado ANTES =="
printf '  %-24s %s\n' "$ENV_ALUNOS" "encontrado ($(wc -l < "$ENV_ALUNOS") linhas)"
printf '  %-24s %s\n' "$ENV_IDENTIDADE" "encontrado ($(wc -l < "$ENV_IDENTIDADE") linhas)"
if [ "$NOVO" -eq 0 ]; then
  echo "  segredo ................. o par JÁ existia; vou reusar, não regerar"
else
  echo "  segredo ................. vou gerar um novo"
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
    grep -q "^# $cabecalho" "$arq" || printf '\n# %s\n# Escrito por infra/provisionar-aviso-de-liberacao.sh (o aviso de liberacao, 29/08/2026).\n' "$cabecalho" >> "$arq"
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
garantir "$ENV_IDENTIDADE" TOKENS_ACEITOS_ALUNOS "$TOKEN" "par alunos->identidade: quem guarda os alunos pergunta o id de quem vai receber a carta"
garantir "$ENV_IDENTIDADE" TOKENS_COMPLETOS_ALUNOS "$TOKEN" "degrau a mais do par alunos->identidade: a porta que procura por e-mail"
garantir "$ENV_ALUNOS" IDENTIDADE_API_URL "$IDENTIDADE_URL" "par alunos->identidade"
garantir "$ENV_ALUNOS" IDENTIDADE_API_TOKEN "$TOKEN" "par alunos->identidade"

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

conferir_par() {  # nome, arquivo-a, chave-a, arquivo-b, chave-b
  a="$(ler_de "$2" "$3")"; b="$(ler_de "$4" "$5")"
  if [ -n "$a" ] && [ "$a" = "$b" ] && [ "$a" = "$TOKEN" ]; then
    printf '  %-24s %s\n' "$1" "confere dos dois lados"
  else
    parar "o par '$1' NÃO ficou igual nos dois lados ($2/$3 e $4/$5). Isso daria 401 ou 403 silencioso. As cópias intactas estão em $RAIZ ($BACKUPS) — me mande esta tela inteira."
  fi
}
conferir_par "quem pode chamar" "$ENV_IDENTIDADE" TOKENS_ACEITOS_ALUNOS "$ENV_ALUNOS" IDENTIDADE_API_TOKEN
conferir_par "o degrau a mais" "$ENV_IDENTIDADE" TOKENS_COMPLETOS_ALUNOS "$ENV_ALUNOS" IDENTIDADE_API_TOKEN

# Chave repetida é o modo de falha mais traiçoeiro de um env: o Docker Compose
# usa a ÚLTIMA, e um valor velho ficaria por baixo sem nada acusar.
for par in "$ENV_IDENTIDADE:TOKENS_ACEITOS_ALUNOS" "$ENV_IDENTIDADE:TOKENS_COMPLETOS_ALUNOS" \
           "$ENV_ALUNOS:IDENTIDADE_API_URL" "$ENV_ALUNOS:IDENTIDADE_API_TOKEN"; do
  arq="${par%%:*}"; chave="${par##*:}"
  n="$(grep -c "^$chave=" "$arq")"
  [ "$n" -eq 1 ] || parar "a chave $chave aparece $n vezes em $arq, e o Docker Compose usaria só a última. As cópias intactas estão em $RAIZ ($BACKUPS) — me mande esta tela inteira."
done
echo "  chaves repetidas ........ nenhuma (conferido nas 4)"
echo

# -----------------------------------------------------------------------------
# 5. RECARREGAR — as células precisam reler o env para as chaves valerem.
#    JAMAIS `docker compose up -d` sem argumento: isso devolveria TODAS as
#    células à tag :main do compose (RITOS §4). Só estes serviços, pelo nome.
# -----------------------------------------------------------------------------
echo "== recarregando as células para elas relerem o env =="
if command -v docker >/dev/null 2>&1; then
  ALVOS=""
  # Ordem: provedor, depois quem pergunta. O `alunos-relay` entra porque é ele
  # que republica a carta que o processo web não conseguiu publicar na hora.
  for servico in identidade alunos alunos-relay; do
    docker compose config --services 2>/dev/null | grep -qx "$servico" && ALVOS="$ALVOS $servico"
  done
  if [ -n "$ALVOS" ]; then
    if docker compose up -d $ALVOS >/dev/null 2>&1; then
      echo "  recarreguei:$ALVOS"
    else
      echo "  (aviso: não consegui recarregar$ALVOS — os arquivos JÁ estão certos; o próximo deploy de cada célula relê o env. Avise o agente.)"
    fi
  else
    echo "  (aviso: não achei estes serviços no compose desta máquina — o próximo deploy relê o env.)"
  fi
else
  echo "  (aviso: não achei o docker aqui — os arquivos JÁ estão certos; o próximo deploy relê o env.)"
fi
echo

echo "A partir de agora, quando você liberar alguém da fila, essa pessoa recebe um"
echo "aviso no sininho do site. Rodar esta mesma linha de novo é seguro: o segredo"
echo "que já existe é reusado, nunca trocado."
echo
echo "PRONTO: o aviso de liberação está ligado."
