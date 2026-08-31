#!/usr/bin/env bash
# =============================================================================
# LIGAR A TELA DO MENU DO TOPO — o passo do mantenedor.
#
# A tela `/admin/menu/` (31/08/2026) lê e grava o menu do site no `catalogo`,
# que é onde dado de site mora. Falar com outra célula exige credencial, e
# credencial não viaja por esteira (INV-P8, Lei 5): o `deploy-infra.yml` diz de
# si mesmo que JAMAIS toca `infra/env/` nem `/opt/plataforma/env/`. Por isso
# este passo é seu, e por isso este arquivo existe — para ele ser UMA linha, e
# não um texto para colar.
#
# COMO RODAR (dentro da VPS, uma linha só, SEM argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-par-do-menu.sh -o /tmp/p.sh && bash /tmp/p.sh
#
# NÃO PERGUNTA NADA e NÃO PEDE NADA. O segredo que falta é gerado AQUI, dentro
# da VPS, e gravado direto nos arquivos: ele não aparece na tela, não passa por
# agente nenhum e não entra no Git (`armadilhas/090`).
#
# É IDEMPOTENTE E NÃO ROTACIONA. Se o par já existir, ele é REUSADO, nunca
# regerado — trocar um token em uso derrubaria as chamadas até o container do
# outro lado reiniciar, e o sintoma seria 401 intermitente. Rodar de novo é
# seguro, e é a cura de qualquer dúvida.
#
# O QUE ELE LIGA (três degraus, e a ordem é deliberada — PROVEDOR PRIMEIRO):
#
#   1. env/catalogo.env  TOKENS_ACEITOS_ADMIN, TOKENS_ACEITOS_FORUM
#   2. env/admin.env     CATALOGO_API_URL, TOKEN_CATALOGO   (quem ESCREVE o menu)
#   3. env/forum.env     CATALOGO_API_URL, TOKEN_CATALOGO   (quem LÊ o menu)
#
# Dois pares, e não um compartilhado: token é POR PAR consumidor→provedor. Um
# token só nos dois lados faria "trocar a credencial do fórum" e "trocar a
# credencial do Admin" serem o mesmo gesto, e no dia de rotacionar um deles o
# outro cairia junto, sem aviso.
#
# Provedor antes de consumidor porque a ordem inversa tem janela ruim: o
# consumidor com token que o provedor ainda não aceita responde 401 para gente
# de verdade. Ao contrário, um provedor que aceita um token que ninguém usa
# ainda não faz nada, e é uma janela sem sintoma.
#
# SE NADA FOR RODADO: a tela do menu abre e diz, em português, que ainda não
# consegue falar com o registro de sites, e o fórum abre exatamente como antes,
# sem menu no topo. O site em si não muda nada, e nada quebra — só não dá para
# configurar o menu pela tela, nem vê-lo no fórum.
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
ENV_CATALOGO="env/catalogo.env"
ENV_ADMIN="env/admin.env"
ENV_FORUM="env/forum.env"
# A referência de dono/permissão: um env que JÁ funciona nesta máquina.
ENV_REF="$ENV_CATALOGO"

# O endereço interno do catálogo sai do `servers:` do contrato congelado dele
# (`contracts/catalogo.openapi.yaml`), e não é escolha deste script.
CATALOGO_URL="http://catalogo:8000/api/catalogo"

# -----------------------------------------------------------------------------
# 1. ONDE — a pasta da plataforma e os dois arquivos de que dependo.
#    Tudo conferido ANTES de gerar ou escrever coisa nenhuma.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ — você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…)"
for arquivo in "$ENV_CATALOGO" "$ENV_ADMIN" "$ENV_FORUM"; do
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
T_ADMIN="$(ler_de "$ENV_CATALOGO" TOKENS_ACEITOS_ADMIN)"
T_FORUM="$(ler_de "$ENV_CATALOGO" TOKENS_ACEITOS_FORUM)"
NOVO=0
if [ -z "$T_ADMIN" ]; then
  T_ADMIN="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
  NOVO=$((NOVO + 1))
fi
if [ -z "$T_FORUM" ]; then
  T_FORUM="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
  NOVO=$((NOVO + 1))
fi
[ ${#T_ADMIN} -ge 32 ] || parar "o token do par admin→catalogo ficou curto demais. Nada foi alterado."
[ ${#T_FORUM} -ge 32 ] || parar "o token do par forum→catalogo ficou curto demais. Nada foi alterado."

echo "== estado ANTES =="
printf '  %-22s %s\n' "$ENV_CATALOGO" "encontrado ($(wc -l < "$ENV_CATALOGO") linhas)"
printf '  %-22s %s\n' "$ENV_ADMIN" "encontrado ($(wc -l < "$ENV_ADMIN") linhas)"
printf '  %-22s %s\n' "$ENV_FORUM" "encontrado ($(wc -l < "$ENV_FORUM") linhas)"
if [ "$NOVO" -eq 0 ]; then
  echo "  segredos ............... os dois pares JÁ existiam; vou reusar, não regerar"
else
  echo "  segredos ............... vou gerar $NOVO (o outro, se houver, é reusado)"
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
    grep -q "^# $cabecalho" "$arq" || printf '\n# %s\n# Escrito por infra/provisionar-par-do-menu.sh (a tela /admin/menu/).\n' "$cabecalho" >> "$arq"
    printf '%s=%s\n' "$chave" "$valor" >> "$arq" \
      || parar "não consegui escrever em $arq. As cópias intactas estão em $RAIZ ($BACKUPS)."
  fi

  # DONO E MODO copiados de um env que JÁ FUNCIONA, nunca escolhidos por mim
  # (`armadilhas/091`): rodando como root, o `sed -i` recria o arquivo e pode
  # deixá-lo root:root — e o usuário `deploy`, que é quem o pipeline usa, não lê
  # um 600 de root.
  if [ "$(stat -c '%U:%G %a' "$arq" 2>/dev/null)" != "$(stat -c '%U:%G %a' "$ENV_REF" 2>/dev/null)" ]; then
    chown --reference="$ENV_REF" "$arq" 2>/dev/null \
      || parar "não consegui ajustar o dono de $arq — rode como root ou como o dono dos env. As cópias intactas estão em $RAIZ ($BACKUPS)."
    chmod --reference="$ENV_REF" "$arq" 2>/dev/null \
      || parar "não consegui ajustar as permissões de $arq — rode como root. As cópias intactas estão em $RAIZ ($BACKUPS)."
  fi

  case "$MEXIDOS" in *" $arq"*) : ;; *) MEXIDOS="$MEXIDOS $arq" ;; esac
}

# PROVEDOR PRIMEIRO — ver o cabeçalho deste arquivo.
garantir "$ENV_CATALOGO" TOKENS_ACEITOS_ADMIN "$T_ADMIN" "par admin→catalogo: a tela do menu le e grava o menu do topo do site"
garantir "$ENV_CATALOGO" TOKENS_ACEITOS_FORUM "$T_FORUM" "par forum→catalogo: o forum mostra o mesmo menu do site"
garantir "$ENV_ADMIN" CATALOGO_API_URL "$CATALOGO_URL" "par admin→catalogo"
garantir "$ENV_ADMIN" TOKEN_CATALOGO "$T_ADMIN" "par admin→catalogo"
garantir "$ENV_FORUM" CATALOGO_API_URL "$CATALOGO_URL" "par forum→catalogo"
garantir "$ENV_FORUM" TOKEN_CATALOGO "$T_FORUM" "par forum→catalogo"

# -----------------------------------------------------------------------------
# 4. ESTADO DEPOIS — a conferência que fecha o assunto. Compara SEM imprimir
#    segredo: o que vai para a tela é "confere / não confere", nunca o valor.
# -----------------------------------------------------------------------------
echo "== estado DEPOIS =="
A="$(ler_de "$ENV_CATALOGO" TOKENS_ACEITOS_ADMIN)"
B="$(ler_de "$ENV_ADMIN" TOKEN_CATALOGO)"
U="$(ler_de "$ENV_ADMIN" CATALOGO_API_URL)"
F="$(ler_de "$ENV_CATALOGO" TOKENS_ACEITOS_FORUM)"
G="$(ler_de "$ENV_FORUM" TOKEN_CATALOGO)"
V="$(ler_de "$ENV_FORUM" CATALOGO_API_URL)"
[ -n "$A" ] || parar "TOKENS_ACEITOS_ADMIN não ficou gravado em $ENV_CATALOGO. As cópias intactas estão em $RAIZ ($BACKUPS)."
[ -n "$F" ] || parar "TOKENS_ACEITOS_FORUM não ficou gravado em $ENV_CATALOGO. As cópias intactas estão em $RAIZ ($BACKUPS)."
[ "$A" = "$B" ] || parar "os dois lados do par do Admin ficaram com valores DIFERENTES — isso daria 401 em toda gravação do menu. As cópias intactas estão em $RAIZ ($BACKUPS)."
[ "$F" = "$G" ] || parar "os dois lados do par do fórum ficaram com valores DIFERENTES — o fórum abriria sem menu, em silêncio. As cópias intactas estão em $RAIZ ($BACKUPS)."
[ "$A" != "$F" ] || parar "o Admin e o fórum ficaram com o MESMO token — token é por par, e um só faria a rotação de um derrubar o outro. As cópias intactas estão em $RAIZ ($BACKUPS)."
[ "$U" = "$CATALOGO_URL" ] || parar "CATALOGO_API_URL não ficou como esperado em $ENV_ADMIN. As cópias intactas estão em $RAIZ ($BACKUPS)."
[ "$V" = "$CATALOGO_URL" ] || parar "CATALOGO_API_URL não ficou como esperado em $ENV_FORUM. As cópias intactas estão em $RAIZ ($BACKUPS)."
echo "  par admin→catalogo ..... confere nos dois lados"
echo "  par forum→catalogo ..... confere nos dois lados"
echo "  os dois pares .......... sao tokens DIFERENTES, como devem ser"
echo "  endereco do catalogo ... $CATALOGO_URL"
echo

# -----------------------------------------------------------------------------
# 5. REINICIAR quem precisa ler o env novo.
# -----------------------------------------------------------------------------
if [ -n "$MEXIDOS" ]; then
  echo "== reiniciando as celulas para que leiam o env novo =="
  if docker compose up -d --force-recreate catalogo admin forum 2>&1 | tail -5; then
    echo
    echo "PRONTO. Abra https://meshcraft.top/admin/menu/ e monte o menu do site."
  else
    echo
    echo "Os arquivos ficaram certos, mas o reinicio das celulas falhou."
    echo "Rode a linha abaixo e me mande a saida:"
    echo "  cd $RAIZ && docker compose up -d --force-recreate catalogo admin forum"
  fi
else
  echo "Nada a fazer: os dois lados ja estavam ligados."
  echo "PRONTO. Abra https://meshcraft.top/admin/menu/ e monte o menu do site."
fi
