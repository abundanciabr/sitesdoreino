#!/usr/bin/env bash
# =============================================================================
# LIGAR O BOTÃO DE TESTAR O AVISO — o passo do mantenedor.
#
# A tela `/admin/avisos/` (03/09/2026) manda um aviso de teste pela porta de
# máquina `POST /aviso-de-teste` da célula `notificacoes`. Falar com outra
# célula exige credencial, e credencial não viaja por esteira (INV-P8,
# Lei 5): o `deploy-infra.yml` diz de si mesmo que JAMAIS toca `infra/env/`
# nem `/opt/plataforma/env/`. Por isso este passo é seu, e por isso este
# arquivo existe — para ele ser UMA linha, e não um texto para colar.
#
# COMO RODAR (dentro da VPS, uma linha só, SEM argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-par-do-teste-de-aviso.sh -o /tmp/p.sh && bash /tmp/p.sh
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
#   1. env/notificacoes.env  TOKENS_ACEITOS_ADMIN
#   2. env/admin.env         NOTIFICACOES_API_URL, NOTIFICACOES_API_TOKEN
#
# Provedor antes de consumidor porque a ordem inversa tem janela ruim: o
# consumidor com token que o provedor ainda não aceita responde 401 para gente
# de verdade. Ao contrário, um provedor que aceita um token que ninguém usa
# ainda não faz nada, e é uma janela sem sintoma.
#
# UM TOKEN PRÓPRIO, e não o mesmo de nenhum outro par do admin (gamificacao,
# catalogo, alunos, identidade). Token é POR PAR consumidor→provedor. Um valor
# só faria "trocar a credencial dos avisos" e "trocar a credencial da
# economia" serem o mesmo gesto, e no dia de rotacionar um deles o outro
# cairia junto, sem aviso.
#
# SE NADA FOR RODADO: o botão "Mandar um aviso de teste para mim" diz "Não
# deu para saber. A célula que guarda os aparelhos não respondeu." — é
# exatamente essa mensagem, honesta, que levou a este script. Nada quebra e
# nada muda no site: os avisos de verdade (sugestão respondida, matrícula
# liberada, cartas da gamificação) continuam saindo pelo fio de eventos, que
# não usa este par. Só o BOTÃO DE TESTE fica mudo até este passo rodar.
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
ENV_NOTIFICACOES="env/notificacoes.env"
ENV_ADMIN="env/admin.env"
# A referência de dono/permissão: um env que JÁ funciona nesta máquina.
ENV_REF="$ENV_NOTIFICACOES"

# O endereço interno sai do `servers:` do contrato congelado da notificacoes
# (`contracts/notificacoes.openapi.yaml`), e não é escolha deste script.
NOTIFICACOES_URL="http://notificacoes:8000/api/notificacoes"

# -----------------------------------------------------------------------------
# 1. ONDE — a pasta da plataforma e os dois arquivos de que dependo.
#    Tudo conferido ANTES de gerar ou escrever coisa nenhuma.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ — você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…)"
for arquivo in "$ENV_NOTIFICACOES" "$ENV_ADMIN"; do
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
T_ADMIN="$(ler_de "$ENV_NOTIFICACOES" TOKENS_ACEITOS_ADMIN)"
NOVO=0
if [ -z "$T_ADMIN" ]; then
  T_ADMIN="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
  NOVO=1
fi
[ ${#T_ADMIN} -ge 32 ] || parar "o token do par admin→notificacoes ficou curto demais. Nada foi alterado."

# Nenhum outro par do admin pode ser reusado aqui, e esta conferência existe
# para o caso de alguém "consertar" isso um dia copiando o valor de lá.
for OUTRO in TOKEN_GAMIFICACAO TOKEN_CATALOGO ALUNOS_API_TOKEN IDENTIDADE_API_TOKEN SUGESTOES_API_TOKEN; do
  T_OUTRO="$(ler_de "$ENV_ADMIN" "$OUTRO")"
  if [ -n "$T_OUTRO" ] && [ "$T_ADMIN" = "$T_OUTRO" ]; then
    parar "o token deste par é IGUAL ao de $OUTRO. Token é por par: um valor só faria a rotação de um derrubar o outro, sem aviso. Nada foi alterado."
  fi
done

echo "== estado ANTES =="
printf '  %-24s %s\n' "$ENV_NOTIFICACOES" "encontrado ($(wc -l < "$ENV_NOTIFICACOES") linhas)"
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
    grep -q "^# $cabecalho" "$arq" || printf '\n# %s\n# Escrito por infra/provisionar-par-do-teste-de-aviso.sh (a tela /admin/avisos/).\n' "$cabecalho" >> "$arq"
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
garantir "$ENV_NOTIFICACOES" TOKENS_ACEITOS_ADMIN "$T_ADMIN" "par admin→notificacoes: o botão de testar o aviso na tela do celular"
garantir "$ENV_ADMIN" NOTIFICACOES_API_URL "$NOTIFICACOES_URL" "par admin→notificacoes"
garantir "$ENV_ADMIN" NOTIFICACOES_API_TOKEN "$T_ADMIN" "par admin→notificacoes"

# -----------------------------------------------------------------------------
# 4. ESTADO DEPOIS — a conferência que fecha o assunto. Compara SEM imprimir
#    segredo: o que vai para a tela é "confere / não confere", nunca o valor.
# -----------------------------------------------------------------------------
echo "== estado DEPOIS =="
A="$(ler_de "$ENV_NOTIFICACOES" TOKENS_ACEITOS_ADMIN)"
B="$(ler_de "$ENV_ADMIN" NOTIFICACOES_API_TOKEN)"
U="$(ler_de "$ENV_ADMIN" NOTIFICACOES_API_URL)"
[ -n "$A" ] || parar "TOKENS_ACEITOS_ADMIN não ficou gravado em $ENV_NOTIFICACOES. As cópias intactas estão em $RAIZ ($BACKUPS)."
[ "$A" = "$B" ] || parar "os dois lados do par ficaram com valores DIFERENTES — isso daria 401 em toda tentativa de testar o aviso. As cópias intactas estão em $RAIZ ($BACKUPS)."
[ "$U" = "$NOTIFICACOES_URL" ] || parar "NOTIFICACOES_API_URL não ficou como esperado em $ENV_ADMIN. As cópias intactas estão em $RAIZ ($BACKUPS)."
echo "  par admin→notificacoes .. confere nos dois lados"
echo "  endereco da notificacoes  $NOTIFICACOES_URL"
echo

# -----------------------------------------------------------------------------
# 5. REINICIAR quem precisa ler o env novo.
#    O `notificacoes-consumer` entra junto porque ele roda a MESMA imagem e lê
#    o MESMO env: deixá-lo para trás faria o processo que escuta os eventos
#    ficar com uma cópia velha do ambiente, e isso é o tipo de diferença que só
#    aparece semanas depois.
# -----------------------------------------------------------------------------
if [ -n "$MEXIDOS" ]; then
  echo "== reiniciando as celulas para que leiam o env novo =="
  # O VEREDITO VEM DO COMANDO, NUNCA DO PIPE. `if docker compose … | tail -5`
  # pergunta o estado do `tail`, que dá 0 quase sempre — e o ramo de erro
  # abaixo viraria código morto: o script diria PRONTO com as células paradas, e
  # ele abriria uma tela que não funciona sem nada na saída explicando por quê.
  # É o falso-verde do ARMADILHAS §5.10, o mesmo que fez os greens do
  # deploy-celula mentirem até 21/08/2026 (H13). A saída é guardada e só depois
  # impressa, para que o estado medido seja o do `docker compose`.
  saida_do_reinicio="$(docker compose up -d --force-recreate notificacoes notificacoes-consumer admin 2>&1)"
  estado_do_reinicio=$?
  printf '%s\n' "$saida_do_reinicio" | tail -5
  if [ "$estado_do_reinicio" -eq 0 ]; then
    echo
    echo "PRONTO. Abra https://meshcraft.top/admin/avisos/ e clique no botão."
  else
    echo
    echo "Os arquivos ficaram certos, mas o reinicio das celulas FALHOU."
    echo "Nada foi perdido: os dois lados do par estao gravados e conferidos."
    echo "Rode a linha abaixo e me mande a saida:"
    echo "  cd $RAIZ && docker compose up -d --force-recreate notificacoes notificacoes-consumer admin"
  fi
else
  echo "Nada a fazer: os dois lados ja estavam ligados."
  echo "PRONTO. Abra https://meshcraft.top/admin/avisos/ e clique no botão."
fi
