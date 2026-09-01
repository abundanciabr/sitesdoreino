#!/usr/bin/env bash
# =============================================================================
# LIGAR O QUADRINHO DE PROGRESSO NA HOME — o passo do mantenedor.
#
# A home de meshcraft.top passou a mostrar, para quem entrou, o degrau da pessoa
# na trilha da escola e o quanto falta para o próximo (degrau 20 do
# PLANO-CELULA-GAMIFICACAO). O progresso é DADO DA GAMIFICAÇÃO e mora lá: o
# `funil` pergunta pela porta de máquina (`getMyStatus`), sem guardar cópia
# nenhuma deste lado. Falar com outra célula exige credencial, e credencial não
# viaja por esteira (INV-P8, Lei 5): o `deploy-infra.yml` diz de si mesmo que
# JAMAIS toca `infra/env/` nem `/opt/plataforma/env/`. Por isso este passo é
# seu, e por isso este arquivo existe: para ele ser UMA linha, e não um texto
# para colar.
#
# COMO RODAR (dentro da VPS, uma linha só, SEM argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-par-do-funil-com-a-gamificacao.sh -o /tmp/p.sh && bash /tmp/p.sh
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
# O QUE ELE LIGA (dois degraus, e a ordem é deliberada — PROVEDOR PRIMEIRO):
#
#   1. env/gamificacao.env  TOKENS_ACEITOS_FUNIL
#   2. env/funil.env        GAMIFICACAO_API_URL, GAMIFICACAO_API_TOKEN
#
# Provedor antes de consumidor porque a ordem inversa tem janela ruim: o
# consumidor com token que o provedor ainda não aceita responde 401 para gente
# de verdade. Ao contrário, um provedor que aceita um token que ninguém usa
# ainda não faz nada, e é uma janela sem sintoma.
#
# UM TOKEN PRÓPRIO, e não o mesmo dos outros pares do funil: token é POR PAR
# consumidor→provedor. Um valor só faria "trocar a credencial do progresso" e
# "trocar a credencial da sessão" serem o mesmo gesto, e no dia de rotacionar um
# deles o outro cairia junto, sem aviso.
#
# SE NADA FOR RODADO: a home abre exatamente como abre hoje, sem o quadrinho de
# progresso, e nada quebra. O site inteiro continua igual — quem entra vê o
# aviso de novidade e o que a categoria dele permite, como sempre viu. O funil
# percebe as duas variáveis ausentes, escreve isso no log e simplesmente não
# desenha o quadrinho. Não há tela de erro, não há página lenta e não há nada
# pela metade: é uma coisa a menos, não uma coisa quebrada.
#
# E MESMO DEPOIS DE RODAR, no primeiro dia o quadrinho ainda não aparece para
# ninguém — e isso é o esperado, não defeito deste script. A economia da escola
# nasceu inteira DESLIGADA (`semear_economia` cria toda regra com `ativa=False`)
# e ninguém tem ponto nenhum ainda. Enquanto for assim, a gamificação responde
# "entrou, e ainda não jogou", e a home trata isso como o que é: não há progresso
# para mostrar. O quadrinho começa a aparecer sozinho, por pessoa, assim que
# você ligar a primeira regra em https://meshcraft.top/admin/economia/ e ela
# render o primeiro ponto a alguém.
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
ENV_GAMIFICACAO="env/gamificacao.env"
ENV_FUNIL="env/funil.env"
# A referência de dono/permissão: um env que JÁ funciona nesta máquina.
ENV_REF="$ENV_GAMIFICACAO"

# O endereço interno sai do `servers:` do contrato congelado da gamificação
# (`contracts/gamificacao.openapi.yaml`), e não é escolha deste script.
GAMIFICACAO_URL="http://gamificacao:8000/api/gamificacao"

# -----------------------------------------------------------------------------
# 1. ONDE — a pasta da plataforma e os dois arquivos de que dependo.
#    Tudo conferido ANTES de gerar ou escrever coisa nenhuma.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ — você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…)"
for arquivo in "$ENV_GAMIFICACAO" "$ENV_FUNIL"; do
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
T_FUNIL="$(ler_de "$ENV_GAMIFICACAO" TOKENS_ACEITOS_FUNIL)"
NOVO=0
if [ -z "$T_FUNIL" ]; then
  T_FUNIL="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
  NOVO=1
fi
[ ${#T_FUNIL} -ge 32 ] || parar "o token do par funil→gamificacao ficou curto demais. Nada foi alterado."

# Os pares que o funil JÁ tem não podem ser reusados aqui, e esta conferência
# existe para o caso de alguém "consertar" isso um dia copiando um valor de lá.
for chave_vizinha in IDENTIDADE_API_TOKEN NOTIFICACOES_API_TOKEN ALUNOS_API_TOKEN; do
  vizinho="$(ler_de "$ENV_FUNIL" "$chave_vizinha")"
  if [ -n "$vizinho" ] && [ "$T_FUNIL" = "$vizinho" ]; then
    parar "o token deste par é IGUAL ao de $chave_vizinha. Token é por par: um valor só faria a rotação de um derrubar o outro, sem aviso. Nada foi alterado."
  fi
done

echo "== estado ANTES =="
printf '  %-24s %s\n' "$ENV_GAMIFICACAO" "encontrado ($(wc -l < "$ENV_GAMIFICACAO") linhas)"
printf '  %-24s %s\n' "$ENV_FUNIL" "encontrado ($(wc -l < "$ENV_FUNIL") linhas)"
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
    grep -q "^# $cabecalho" "$arq" || printf '\n# %s\n# Escrito por infra/provisionar-par-do-funil-com-a-gamificacao.sh (o quadrinho de progresso da home).\n' "$cabecalho" >> "$arq"
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
garantir "$ENV_GAMIFICACAO" TOKENS_ACEITOS_FUNIL "$T_FUNIL" "par funil→gamificacao: a home mostra o degrau de quem entrou"
garantir "$ENV_FUNIL" GAMIFICACAO_API_URL "$GAMIFICACAO_URL" "par funil→gamificacao"
garantir "$ENV_FUNIL" GAMIFICACAO_API_TOKEN "$T_FUNIL" "par funil→gamificacao"

# -----------------------------------------------------------------------------
# 4. ESTADO DEPOIS — a conferência que fecha o assunto. Compara SEM imprimir
#    segredo: o que vai para a tela é "confere / não confere", nunca o valor.
# -----------------------------------------------------------------------------
echo "== estado DEPOIS =="
A="$(ler_de "$ENV_GAMIFICACAO" TOKENS_ACEITOS_FUNIL)"
B="$(ler_de "$ENV_FUNIL" GAMIFICACAO_API_TOKEN)"
U="$(ler_de "$ENV_FUNIL" GAMIFICACAO_API_URL)"
[ -n "$A" ] || parar "TOKENS_ACEITOS_FUNIL não ficou gravado em $ENV_GAMIFICACAO. As cópias intactas estão em $RAIZ ($BACKUPS)."
[ "$A" = "$B" ] || parar "os dois lados do par ficaram com valores DIFERENTES — isso daria 401 a cada carregamento da home. As cópias intactas estão em $RAIZ ($BACKUPS)."
[ "$U" = "$GAMIFICACAO_URL" ] || parar "GAMIFICACAO_API_URL não ficou como esperado em $ENV_FUNIL. As cópias intactas estão em $RAIZ ($BACKUPS)."
echo "  par funil→gamificacao ... confere nos dois lados"
echo "  endereco da gamificacao . $GAMIFICACAO_URL"
echo

# -----------------------------------------------------------------------------
# 5. REINICIAR quem precisa ler o env novo.
#    O `gamificacao-consumer` entra junto porque ele roda a MESMA imagem e lê o
#    MESMO env: deixá-lo para trás faria o processo que escuta os eventos ficar
#    com uma cópia velha do ambiente, e isso é o tipo de diferença que só
#    aparece semanas depois.
# -----------------------------------------------------------------------------
if [ -n "$MEXIDOS" ]; then
  echo "== reiniciando as celulas para que leiam o env novo =="
  # O VEREDITO VEM DO COMANDO, NUNCA DO PIPE. `if docker compose … | tail -5`
  # pergunta o estado do `tail`, que dá 0 quase sempre — e o ramo de erro abaixo
  # viraria código morto: o script diria PRONTO com as células paradas, e a home
  # continuaria sem o quadrinho sem nada na saída explicando por quê. É o
  # falso-verde do ARMADILHAS §5.10, o mesmo que fez os greens do deploy-celula
  # mentirem até 21/08/2026 (H13). A saída é guardada e só depois impressa, para
  # que o estado medido seja o do `docker compose`.
  saida_do_reinicio="$(docker compose up -d --force-recreate gamificacao gamificacao-consumer funil 2>&1)"
  estado_do_reinicio=$?
  printf '%s\n' "$saida_do_reinicio" | tail -5
  if [ "$estado_do_reinicio" -eq 0 ]; then
    echo
    echo "PRONTO. O site continua no ar: https://meshcraft.top/"
    echo "O quadrinho de progresso so aparece para quem JA tem ponto, e hoje"
    echo "ninguem tem: a economia inteira continua desligada. Ele nasce sozinho"
    echo "assim que voce ligar a primeira regra em /admin/economia/."
  else
    echo
    echo "Os arquivos ficaram certos, mas o reinicio das celulas FALHOU."
    echo "Nada foi perdido: os dois lados do par estao gravados e conferidos."
    echo "O site continua no ar, sem o quadrinho, e nada quebrou."
    echo "Rode a linha abaixo e me mande a saida:"
    echo "  cd $RAIZ && docker compose up -d --force-recreate gamificacao gamificacao-consumer funil"
  fi
else
  echo "Nada a fazer: os dois lados ja estavam ligados."
  echo "PRONTO. O site esta no ar: https://meshcraft.top/"
fi
