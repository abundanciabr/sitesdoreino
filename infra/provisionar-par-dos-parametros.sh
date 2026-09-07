#!/usr/bin/env bash
# =============================================================================
# LIGAR A TELA DOS NÚMEROS DA FILA DO PRIMEIRO DÓLAR — o passo do mantenedor.
#
# A tela `/admin/encomendas/parametros/` (07/09/2026) lê e grava os números que
# a Fila do Primeiro Dólar obedece na célula `encomendas`, que é onde eles
# moram. Falar com outra célula exige credencial, e credencial não viaja por
# esteira (INV-P8, Lei 5): o `deploy-infra.yml` diz de si mesmo que JAMAIS toca
# `infra/env/` nem `/opt/plataforma/env/`. Por isso este passo é seu, e por isso
# este arquivo existe: para ele ser UMA linha, e não um texto para colar.
#
# COMO RODAR (dentro da VPS, uma linha só, SEM argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-par-dos-parametros.sh -o /tmp/p.sh && bash /tmp/p.sh
#
# NÃO PERGUNTA NADA e NÃO PEDE NADA. O segredo que falta é gerado AQUI, dentro
# da VPS, e gravado direto nos arquivos: ele não aparece na tela, não passa por
# agente nenhum e não entra no Git (`armadilhas/090`).
#
# É IDEMPOTENTE E NÃO ROTACIONA. Se o par já existir, ele é REUSADO, nunca
# regerado: trocar um token em uso derrubaria as chamadas até o container do
# outro lado reiniciar, e o sintoma seria 401 intermitente. Rodar de novo é
# seguro, e é a cura de qualquer dúvida.
#
# O QUE ELE LIGA (quatro chaves, e a ordem é deliberada — PROVEDOR PRIMEIRO):
#
#   1. env/encomendas.env  TOKENS_ACEITOS_ADMIN   (ler os números)
#   2. env/encomendas.env  TOKENS_ESCRITA_ADMIN   (gravar um número)
#   3. env/admin.env       ENCOMENDAS_API_URL, ENCOMENDAS_API_TOKEN
#   4. env/admin.env       ENCOMENDAS_API_TOKEN_ESCRITA
#
# Provedor antes de consumidor porque a ordem inversa tem janela ruim: o
# consumidor com token que o provedor ainda não aceita responde 401 para gente
# de verdade. Ao contrário, um provedor que aceita um token que ninguém usa
# ainda não faz nada, e é uma janela sem sintoma.
#
# POR QUE DOIS GRAUS DO MESMO PAR, E O MESMO VALOR NOS DOIS (`armadilhas/318`)
# ---------------------------------------------------------------------------
# A porta da `encomendas` separa LER de GRAVAR: `setParameter`, `confirmPayment`
# e `reportAudit` exigem `TOKENS_ESCRITA_*`, e o resto se contenta com
# `TOKENS_ACEITOS_*`. O grau alto CONTÉM o baixo do lado de lá, então um valor
# só nas duas variáveis é o que dá à tela do dono os dois poderes de que ela
# precisa — e é UM par, com UMA rotação, em vez de dois segredos para manter
# alinhados.
#
# A separação continua fazendo o trabalho dela para os OUTROS pares: o dia em
# que alguém pedir um token para desenhar "em que pé está a minha fila" na home,
# esse par entra só em `TOKENS_ACEITOS_` e não ganha, junto e de graça, o poder
# de mudar a régua da fila inteira.
#
# UM TOKEN PRÓPRIO, e não o mesmo dos pares com o catálogo, a gamificação ou a
# sala de aula: token é POR PAR consumidor→provedor. Um valor só faria "trocar a
# credencial dos números da fila" e "trocar a credencial da economia" serem o
# mesmo gesto, e no dia de rotacionar um deles o outro cairia junto, sem aviso.
#
# SE NADA FOR RODADO: a tela `/admin/encomendas/parametros/` abre e diz, em
# português, que ainda não consegue falar com a Fila do Primeiro Dólar. Nada
# quebra e nada muda no site: os números continuam valendo exatamente como estão
# gravados na célula, e o motor continua obedecendo a eles. Só não dá para mudar
# nenhum pela tela.
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
ENV_ENCOMENDAS="env/encomendas.env"
ENV_ADMIN="env/admin.env"
# A referência de dono/permissão: um env que JÁ funciona nesta máquina.
ENV_REF="$ENV_ENCOMENDAS"

# O endereço interno sai do `servers:` da porta de máquina da célula
# (`services/encomendas/config/api.py`), e não é escolha deste script.
ENCOMENDAS_URL="http://encomendas:8000/api/encomendas"

# -----------------------------------------------------------------------------
# 1. ONDE — a pasta da plataforma e os dois arquivos de que dependo.
#    Tudo conferido ANTES de gerar ou escrever coisa nenhuma.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ — você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…, nunca PS C:\\>)"
for arquivo in "$ENV_ENCOMENDAS" "$ENV_ADMIN"; do
  [ -f "$arquivo" ] || parar "não achei $RAIZ/$arquivo — alguma das duas células não está provisionada nesta máquina. Nada foi criado, nada foi alterado."
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
#    A LEITURA VEM PRIMEIRO na busca: se só o grau de leitura já estiver lá (uma
#    execução antiga, ou uma metade escrita à mão), reusamos aquele valor e o
#    promovemos ao grau de escrita, em vez de gerar um terceiro segredo e deixar
#    a instalação com dois tokens vivos para o mesmo par.
# -----------------------------------------------------------------------------
T_PAR="$(ler_de "$ENV_ENCOMENDAS" TOKENS_ACEITOS_ADMIN)"
[ -n "$T_PAR" ] || T_PAR="$(ler_de "$ENV_ENCOMENDAS" TOKENS_ESCRITA_ADMIN)"
[ -n "$T_PAR" ] || T_PAR="$(ler_de "$ENV_ADMIN" ENCOMENDAS_API_TOKEN)"
NOVO=0
if [ -z "$T_PAR" ]; then
  T_PAR="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
  NOVO=1
fi
[ ${#T_PAR} -ge 32 ] || parar "o token do par admin→encomendas ficou curto demais. Nada foi alterado."

# Os outros pares do admin não podem ser reusados aqui, e esta conferência
# existe para o caso de alguém "consertar" isso um dia copiando o valor de lá.
for OUTRO in TOKEN_CATALOGO TOKEN_GAMIFICACAO CURSOS_API_TOKEN; do
  V="$(ler_de "$ENV_ADMIN" "$OUTRO")"
  if [ -n "$V" ] && [ "$T_PAR" = "$V" ]; then
    parar "o token deste par é IGUAL ao de $OUTRO. Token é por par: um valor só faria a rotação de um derrubar o outro, sem aviso. Nada foi alterado."
  fi
done

echo "== estado ANTES =="
printf '  %-24s %s\n' "$ENV_ENCOMENDAS" "encontrado ($(wc -l < "$ENV_ENCOMENDAS") linhas)"
printf '  %-24s %s\n' "$ENV_ADMIN" "encontrado ($(wc -l < "$ENV_ADMIN") linhas)"
if [ "$NOVO" -eq 0 ]; then
  echo "  segredo ................. o par JÁ existia; vou reusar, não regerar"
else
  echo "  segredo ................. vou gerar um novo, aqui dentro da VPS"
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
    grep -q "^# $cabecalho" "$arq" || printf '\n# %s\n# Escrito por infra/provisionar-par-dos-parametros.sh (a tela /admin/encomendas/parametros/).\n' "$cabecalho" >> "$arq"
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
garantir "$ENV_ENCOMENDAS" TOKENS_ACEITOS_ADMIN "$T_PAR" "par admin→encomendas: a tela lê os números da fila"
garantir "$ENV_ENCOMENDAS" TOKENS_ESCRITA_ADMIN "$T_PAR" "par admin→encomendas: a tela grava um número novo"
garantir "$ENV_ADMIN" ENCOMENDAS_API_URL "$ENCOMENDAS_URL" "par admin→encomendas"
garantir "$ENV_ADMIN" ENCOMENDAS_API_TOKEN "$T_PAR" "par admin→encomendas"
garantir "$ENV_ADMIN" ENCOMENDAS_API_TOKEN_ESCRITA "$T_PAR" "par admin→encomendas"

# -----------------------------------------------------------------------------
# 4. ESTADO DEPOIS — a conferência que fecha o assunto. Compara SEM imprimir
#    segredo: o que vai para a tela é "confere / não confere", nunca o valor.
# -----------------------------------------------------------------------------
echo "== estado DEPOIS =="
A="$(ler_de "$ENV_ENCOMENDAS" TOKENS_ACEITOS_ADMIN)"
B="$(ler_de "$ENV_ENCOMENDAS" TOKENS_ESCRITA_ADMIN)"
C="$(ler_de "$ENV_ADMIN" ENCOMENDAS_API_TOKEN)"
D="$(ler_de "$ENV_ADMIN" ENCOMENDAS_API_TOKEN_ESCRITA)"
U="$(ler_de "$ENV_ADMIN" ENCOMENDAS_API_URL)"
[ -n "$A" ] || parar "TOKENS_ACEITOS_ADMIN não ficou gravado em $ENV_ENCOMENDAS. As cópias intactas estão em $RAIZ ($BACKUPS)."
[ "$A" = "$C" ] || parar "os dois lados do grau de LEITURA ficaram com valores DIFERENTES — isso daria 401 ao abrir a tela dos números. As cópias intactas estão em $RAIZ ($BACKUPS)."
[ "$B" = "$D" ] || parar "os dois lados do grau de ESCRITA ficaram com valores DIFERENTES — a tela abriria e o botão de gravar daria 403. As cópias intactas estão em $RAIZ ($BACKUPS)."
[ "$U" = "$ENCOMENDAS_URL" ] || parar "ENCOMENDAS_API_URL não ficou como esperado em $ENV_ADMIN. As cópias intactas estão em $RAIZ ($BACKUPS)."
echo "  par admin→encomendas .... confere nos dois lados"
echo "  grau de leitura ......... ligado (a tela mostra os números)"
echo "  grau de escrita ......... ligado (o botão de gravar funciona)"
echo "  endereco das encomendas . $ENCOMENDAS_URL"
echo

# -----------------------------------------------------------------------------
# 5. REINICIAR quem precisa ler o env novo.
# -----------------------------------------------------------------------------
if [ -n "$MEXIDOS" ]; then
  echo "== reiniciando as celulas para que leiam o env novo =="
  # O VEREDITO VEM DO COMANDO, NUNCA DO PIPE. `if docker compose … | tail -5`
  # pergunta o estado do `tail`, que dá 0 quase sempre — e o ramo de erro abaixo
  # viraria código morto: o script diria PRONTO com as células paradas, e ele
  # abriria uma tela que não funciona sem nada na saída explicando por quê. É o
  # falso-verde do ARMADILHAS §5.10.
  saida_do_reinicio="$(docker compose up -d --force-recreate encomendas admin 2>&1)"
  estado_do_reinicio=$?
  printf '%s\n' "$saida_do_reinicio" | tail -5
  if [ "$estado_do_reinicio" -eq 0 ]; then
    echo
    echo "PRONTO. Abra https://meshcraft.top/admin/encomendas/parametros/ para ver os numeros."
    echo "Tres deles nascem VAZIOS de proposito (o piso de preco de cada nivel):"
    echo "o numero sai do seu piloto de papel, e enquanto nao houver um, o site"
    echo "nao avisa nada sobre preco e nao impede proposta nenhuma."
  else
    echo
    echo "Os arquivos ficaram certos, mas o reinicio das celulas FALHOU."
    echo "Nada foi perdido: os dois lados do par estao gravados e conferidos."
    echo "Rode a linha abaixo e me mande a saida:"
    echo "  cd $RAIZ && docker compose up -d --force-recreate encomendas admin"
  fi
else
  echo "Nada a fazer: os dois lados ja estavam ligados."
  echo "PRONTO. Abra https://meshcraft.top/admin/encomendas/parametros/ para ver os numeros."
fi
