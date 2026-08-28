#!/usr/bin/env bash
# =============================================================================
# LIGAR AS CINCO CATEGORIAS DE USUÁRIO — o passo do mantenedor.
#
# `docs/decisoes/DECISAO-categorias-de-usuario.md` (28/08/2026) manda a home e a
# área administrativa pararem de adivinhar o que uma pessoa é e passarem a
# PERGUNTAR à célula `alunos`. Perguntar exige credencial, e credencial não
# viaja por esteira (INV-P8, Lei 5): o `deploy-infra.yml` diz de si mesmo que
# JAMAIS toca `infra/env/` nem `/opt/plataforma/env/`. Por isso este passo é
# seu, e por isso este arquivo existe — para ele ser UMA linha, e não um texto
# para colar.
#
# COMO RODAR (dentro da VPS, uma linha só, SEM argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-pares-de-categorias.sh -o /tmp/p.sh && bash /tmp/p.sh
#
# NÃO PERGUNTA NADA e NÃO PEDE NADA. Os dois segredos que faltam são gerados
# AQUI, dentro da VPS, e gravados direto nos arquivos: nenhum aparece na tela,
# nenhum passa por agente, nenhum entra no Git (`armadilhas/090`).
#
# É IDEMPOTENTE E NÃO ROTACIONA. Se um par já existir, ele é REUSADO — nunca
# regerado. Trocar um token em uso derrubaria as chamadas até o container do
# outro lado reiniciar, e o sintoma seria 401 intermitente em duas células ao
# mesmo tempo. Rodar de novo é seguro e é a cura de qualquer dúvida.
#
# O QUE ELE LIGA (três degraus, e a ordem é deliberada — PROVEDOR PRIMEIRO):
#
#   1. env/alunos.env      TOKENS_ACEITOS_ADMIN, TOKENS_ACEITOS_FUNIL
#   2. env/identidade.env  TOKENS_COMPLETOS_FUNIL  (COPIADO do TOKENS_ACEITOS_FUNIL
#                          que já existe lá — nunca um valor novo: são dois
#                          degraus sobre o MESMO token, e valores diferentes dão
#                          403 silencioso em toda página da home)
#   3. env/admin.env       ALUNOS_API_URL, ALUNOS_API_TOKEN
#      env/funil.env       ALUNOS_API_URL, ALUNOS_API_TOKEN
#
# Provedor antes de consumidor porque a ordem inversa tem janela ruim: o
# consumidor com token que o provedor ainda não aceita responde 401 para gente
# de verdade. Ao contrário, um provedor que aceita um token que ninguém usa
# ainda não faz nada — e é uma janela sem sintoma.
#
# POR QUE O `funil` PRECISA DO DEGRAU DE E-MAIL: a categoria de uma pessoa é
# calculada por e-mail (é por e-mail que a `alunos` guarda matrícula), e o
# `funil` hoje só recebe "entrou ou não entrou". O registro por escrito que a
# `DECISAO-celula-de-identidade` §6.3 exige está no §4 daquela decisão.
#
# O QUE ACONTECE SE OUTRO SCRIPT DE PROVISIONAMENTO RODAR DEPOIS DESTE:
# `provisionar-admin.sh` e `provisionar-identidade.sh` reescrevem o env deles do
# ZERO, a partir de heredocs que não conhecem estas chaves. Eles NÃO vão apagá-las
# em silêncio — os dois têm a trava de deriva (`CHAVES_QUE_EU_GERO`) e PARAM com
# "PAROU POR SEGURANÇA" ao encontrar chave que não sabem gerar, listando quais.
# É o comportamento certo, e é bom saber de antemão o que a tela vai dizer: se
# isso acontecer, o caminho é rodar aquele script sabendo que ele apaga, e este
# aqui logo depois para repor. Este é idempotente e custa uma linha.
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
ENV_ADMIN="env/admin.env"
ENV_FUNIL="env/funil.env"
# A referência de dono/permissão: um env que JÁ funciona nesta máquina.
ENV_REF="$ENV_ALUNOS"

# O endereço interno da `alunos` sai do `servers:` do contrato congelado dela
# (`contracts/alunos.openapi.yaml`), e não é escolha deste script.
ALUNOS_URL="http://alunos:8000/api/alunos"

# -----------------------------------------------------------------------------
# 1. ONDE — a pasta da plataforma e os quatro arquivos de que dependo.
#    Tudo conferido ANTES de gerar ou escrever coisa nenhuma.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ — você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…)"
for arquivo in "$ENV_ALUNOS" "$ENV_IDENTIDADE" "$ENV_ADMIN" "$ENV_FUNIL"; do
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
# 2. OS VALORES — reusados se já existem, gerados só se faltam.
# -----------------------------------------------------------------------------
T_ADMIN="$(ler_de "$ENV_ALUNOS" TOKENS_ACEITOS_ADMIN)"
T_FUNIL="$(ler_de "$ENV_ALUNOS" TOKENS_ACEITOS_FUNIL)"
NOVOS=0
if [ -z "$T_ADMIN" ]; then
  T_ADMIN="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
  NOVOS=$((NOVOS + 1))
fi
if [ -z "$T_FUNIL" ]; then
  T_FUNIL="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
  NOVOS=$((NOVOS + 1))
fi
[ ${#T_ADMIN} -ge 32 ] || parar "o token do par admin→alunos ficou curto demais. Nada foi alterado."
[ ${#T_FUNIL} -ge 32 ] || parar "o token do par funil→alunos ficou curto demais. Nada foi alterado."

# O degrau de e-mail do funil é o MESMO token que a identidade já aceita dele.
T_FUNIL_IDENTIDADE="$(ler_de "$ENV_IDENTIDADE" TOKENS_ACEITOS_FUNIL)"
[ -n "$T_FUNIL_IDENTIDADE" ] || parar "não achei TOKENS_ACEITOS_FUNIL em $RAIZ/$ENV_IDENTIDADE — sem ele o funil nem conversa com a identidade hoje, e este script não teria o que copiar. Nada foi alterado."

echo "== estado ANTES =="
printf '  %-22s %s\n' "$ENV_ALUNOS" "encontrado ($(wc -l < "$ENV_ALUNOS") linhas)"
printf '  %-22s %s\n' "$ENV_IDENTIDADE" "encontrado ($(wc -l < "$ENV_IDENTIDADE") linhas)"
printf '  %-22s %s\n' "$ENV_ADMIN" "encontrado ($(wc -l < "$ENV_ADMIN") linhas)"
printf '  %-22s %s\n' "$ENV_FUNIL" "encontrado ($(wc -l < "$ENV_FUNIL") linhas)"
if [ "$NOVOS" -eq 0 ]; then
  echo "  segredos ............... os dois pares JÁ existiam; vou reusar, não regerar"
else
  echo "  segredos ............... vou gerar $NOVOS (o outro, se houver, é reusado)"
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
    grep -q "^# $cabecalho" "$arq" || printf '\n# %s\n# Escrito por infra/provisionar-pares-de-categorias.sh (DECISAO-categorias-de-usuario).\n' "$cabecalho" >> "$arq"
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
garantir "$ENV_ALUNOS" TOKENS_ACEITOS_ADMIN "$T_ADMIN" "par admin→alunos: a area administrativa pergunta pela fila e libera"
garantir "$ENV_ALUNOS" TOKENS_ACEITOS_FUNIL "$T_FUNIL" "par funil→alunos: a home pergunta em que categoria a pessoa esta"
garantir "$ENV_IDENTIDADE" TOKENS_COMPLETOS_FUNIL "$T_FUNIL_IDENTIDADE" "degrau de e-mail do funil (DECISAO-categorias-de-usuario §4)"
garantir "$ENV_ADMIN" ALUNOS_API_URL "$ALUNOS_URL" "par admin→alunos"
garantir "$ENV_ADMIN" ALUNOS_API_TOKEN "$T_ADMIN" "par admin→alunos"
garantir "$ENV_FUNIL" ALUNOS_API_URL "$ALUNOS_URL" "par funil→alunos"
garantir "$ENV_FUNIL" ALUNOS_API_TOKEN "$T_FUNIL" "par funil→alunos"

# -----------------------------------------------------------------------------
# 4. ESTADO DEPOIS — a conferência que fecha o assunto. Compara SEM imprimir
#    segredo: o que vai para a tela é "confere / não confere", nunca o valor.
# -----------------------------------------------------------------------------
echo "== estado DEPOIS =="
if [ -z "$MEXIDOS" ]; then
  echo "  o que eu fiz ........... nada: já estava tudo ligado"
else
  echo "  arquivos alterados .....$MEXIDOS"
  echo "  cópias de segurança ....$BACKUPS"
fi

conferir_par() {  # nome, valor-esperado, arquivo-a, chave-a, arquivo-b, chave-b
  a="$(ler_de "$3" "$4")"; b="$(ler_de "$5" "$6")"
  if [ -n "$a" ] && [ "$a" = "$b" ] && [ "$a" = "$2" ]; then
    printf '  %-22s %s\n' "$1" "confere dos dois lados"
  else
    parar "o par '$1' NÃO ficou igual nos dois lados ($3/$4 e $5/$6). Isso daria 401 silencioso. As cópias intactas estão em $RAIZ ($BACKUPS) — me mande esta tela inteira."
  fi
}
conferir_par "par admin→alunos" "$T_ADMIN" "$ENV_ALUNOS" TOKENS_ACEITOS_ADMIN "$ENV_ADMIN" ALUNOS_API_TOKEN
conferir_par "par funil→alunos" "$T_FUNIL" "$ENV_ALUNOS" TOKENS_ACEITOS_FUNIL "$ENV_FUNIL" ALUNOS_API_TOKEN
conferir_par "e-mail para o funil" "$T_FUNIL_IDENTIDADE" "$ENV_IDENTIDADE" TOKENS_ACEITOS_FUNIL "$ENV_IDENTIDADE" TOKENS_COMPLETOS_FUNIL

# Chave repetida é o modo de falha mais traiçoeiro de um env: o Docker Compose
# usa a ÚLTIMA, e um valor velho ficaria por baixo sem nada acusar.
for par in "$ENV_ALUNOS:TOKENS_ACEITOS_ADMIN" "$ENV_ALUNOS:TOKENS_ACEITOS_FUNIL" \
           "$ENV_IDENTIDADE:TOKENS_COMPLETOS_FUNIL" "$ENV_ADMIN:ALUNOS_API_TOKEN" \
           "$ENV_ADMIN:ALUNOS_API_URL" "$ENV_FUNIL:ALUNOS_API_TOKEN" "$ENV_FUNIL:ALUNOS_API_URL"; do
  arq="${par%%:*}"; chave="${par##*:}"
  n="$(grep -c "^$chave=" "$arq")"
  [ "$n" -eq 1 ] || parar "a chave $chave aparece $n vezes em $arq, e o Docker Compose usaria só a última. As cópias intactas estão em $RAIZ ($BACKUPS) — me mande esta tela inteira."
done
echo "  chaves repetidas ....... nenhuma (conferido nas 7)"
echo

# -----------------------------------------------------------------------------
# 5. RECARREGAR — as células precisam reler o env para as chaves valerem.
#    JAMAIS `docker compose up -d` sem argumento: isso devolveria TODAS as
#    células à tag :main do compose (RITOS §4). Só estes serviços, pelo nome.
# -----------------------------------------------------------------------------
echo "== recarregando as células para elas relerem o env =="
if command -v docker >/dev/null 2>&1; then
  ALVOS=""
  # Ordem: provedor, depois quem pergunta.
  for servico in alunos identidade admin funil; do
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

echo "A partir de agora a home e a área administrativa conseguem PERGUNTAR em que"
echo "categoria cada pessoa está, em vez de adivinhar. Rodar esta mesma linha de"
echo "novo é seguro: os segredos que já existem são reusados, nunca trocados."
echo
echo "PRONTO: as cinco categorias de usuário estão ligadas."
