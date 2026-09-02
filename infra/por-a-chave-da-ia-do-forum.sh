#!/usr/bin/env bash
# =============================================================================
# LIGAR A IA QUE RASCUNHA RESPOSTA NO FÓRUM — o passo do mantenedor.
# Guarda a chave da Anthropic no env do fórum e recarrega a célula.
#
# COMO O MANTENEDOR RODA (dentro da VPS, uma linha só, SEM argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/por-a-chave-da-ia-do-forum.sh -o /tmp/ia.sh && bash /tmp/ia.sh
#
# ELE PERGUNTA A CHAVE, com digitação invisível, e essa é a decisão que dá nome
# ao arquivo. A chave NUNCA vem como argumento: argumento de linha de comando
# aparece na tela, fica no `~/.bash_history`, é lido por qualquer processo pelo
# `ps aux`, e vai junto no print que o mantenedor manda ao agente para provar
# que funcionou. Foi assim que o segredo do OAuth do Google vazou em 24/08/2026
# (`armadilhas/090`), e é o quarto caminho que engana: a regra "segredo não
# passa por chat" existia, e o desenho do comando garantia que passaria.
#
# IDEMPOTENTE: rodar de novo é seguro e serve para TROCAR a chave. O env antigo
# vira `.bak-<epoch>` antes de qualquer edição, e só a linha da chave muda.
#
# ELE NÃO GERA NADA. Esta é a única variável do fórum que nasce fora daqui: ela
# vem da conta da Anthropic do mantenedor, em console.anthropic.com, e custa
# dinheiro por uso. ANTES de colar a chave aqui, ponha um TETO DE GASTO MENSAL
# no painel de lá: é ele que garante que a conta nunca passa do valor escolhido,
# e nenhuma linha deste repositório consegue fazer isso por você.
# =============================================================================

# O modo de falha de 24/08 em pessoa: carregado com `source`/`.`, um `exit` daqui
# derrubaria a sessão do mantenedor. Com `bash /tmp/ia.sh` o exit morre no filho.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANÇA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessão. Rode com a palavra bash na frente: bash /tmp/ia.sh"
  return 1 2>/dev/null || exit 1
fi

set -u

parar() { echo "PAROU POR SEGURANÇA: $1"; exit 1; }

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ENV_FORUM="env/forum.env"
# A referência de dono/permissão: um env que JÁ funciona nesta máquina
# (`armadilhas/091`). Rodando como root, uma edição recria o arquivo e pode
# deixá-lo root:root, e aí o usuário `deploy` (que é quem o pipeline usa) não lê.
ENV_REF="env/alunos.env"

# -----------------------------------------------------------------------------
# 1. ONDE — tudo conferido ANTES de pedir a chave.
#    Perguntar primeiro e descobrir depois que o arquivo não existe faria o
#    mantenedor colar um segredo à toa, e colar segredo à toa é como um segredo
#    acaba num lugar errado.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ — você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…)"
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em $RAIZ."
[ -f "$ENV_FORUM" ] || parar "não achei $RAIZ/$ENV_FORUM. O fórum ainda não foi provisionado nesta máquina: rode antes o infra/provisionar-forum.sh. Nada foi alterado."
[ -w "$ENV_FORUM" ] || parar "não consigo escrever em $RAIZ/$ENV_FORUM — rode como root ou como o dono dos env. Nada foi alterado."
[ -f "$ENV_REF" ] || parar "não achei $RAIZ/$ENV_REF, que é de onde eu copio dono e permissão. Nada foi alterado."

echo "== estado ANTES =="
if grep -q '^ANTHROPIC_API_KEY=.\+' "$ENV_FORUM" 2>/dev/null; then
  echo "  a IA do fórum ..... JÁ está ligada (vou TROCAR a chave por esta nova)"
else
  echo "  a IA do fórum ..... desligada (vou ligar)"
fi
echo

# -----------------------------------------------------------------------------
# 2. A CHAVE — perguntada, invisível, e conferida antes de tocar em nada.
# -----------------------------------------------------------------------------
echo "Abra console.anthropic.com, ponha o TETO DE GASTO MENSAL, e copie a chave."
echo "Ela começa com sk-ant- e é bem comprida."
echo
printf 'Cole a chave e aperte Enter (NADA vai aparecer na tela, isso é normal): '
read -r -s CHAVE
echo   # a quebra de linha que o -s engoliu
echo

# Espaço em volta é o acidente mais comum de quem copia de uma página web.
CHAVE="$(printf '%s' "$CHAVE" | tr -d '[:space:]')"

[ -n "$CHAVE" ] || parar "você não colou nada. Nada foi alterado."
case "$CHAVE" in
  sk-ant-*) : ;;
  *) parar "isso não parece uma chave da Anthropic: ela começa com sk-ant-. Confira se você copiou a linha inteira. Nada foi alterado." ;;
esac
[ ${#CHAVE} -ge 40 ] || parar "a chave ficou curta demais (${#CHAVE} caracteres). Provavelmente veio pela metade: copie de novo, inteira. Nada foi alterado."
# Só letras, números, hífen e sublinhado. Não é frescura de formato: é o que
# torna o `sed` lá embaixo seguro. Um caractere de pontuação no meio do valor
# viraria parte da EXPRESSÃO do sed, e o arquivo sairia corrompido.
case "$CHAVE" in
  *[!A-Za-z0-9_-]*) parar "a chave tem um caractere estranho. Copie de novo, direto do site da Anthropic, sem passar por editor de texto. Nada foi alterado." ;;
esac

# -----------------------------------------------------------------------------
# 2b. O WORKSPACE — opcional, e visivel enquanto se digita (nao e segredo).
#
# POR QUE ELE EXISTE: em 02/09/2026, na primeira vez que o botao foi usado de
# verdade, a Anthropic recusou com HTTP 400 e a frase "anthropic-workspace-id is
# required when authenticating with an identity-linked API key". A chave nova,
# ligada a identidade de quem a criou, exige dizer em qual workspace o pedido
# age; a chave classica, de workspace, ja carrega isso e nao precisa.
#
# VAZIO E RESPOSTA LEGITIMA, e por isso ele nao para aqui: quem usa chave de
# workspace aperta Enter e segue. Se fizer falta, quem avisa e a propria tela do
# forum, com a frase que manda rodar este comando de novo.
#
# Ele e ecoado de proposito, ao contrario da chave: id de workspace nao e
# segredo, e ver o que colou evita a colagem pela metade que ninguem percebe.
# -----------------------------------------------------------------------------
echo "Agora o WORKSPACE, e ele so faz falta se a sua chave for do tipo novo,"
echo "ligada a sua identidade. No console da Anthropic ele aparece na parte de"
echo "Workspaces. Se voce nao souber, aperte Enter: o forum avisa se fizer falta."
echo
printf 'Cole o id do workspace (ou so aperte Enter para pular): '
read -r WORKSPACE
echo

WORKSPACE="$(printf '%s' "$WORKSPACE" | tr -d '[:space:]')"
case "$WORKSPACE" in
  *[!A-Za-z0-9_-]*) parar "o id do workspace tem um caractere estranho. Copie de novo, direto do console. Nada foi alterado." ;;
esac

# -----------------------------------------------------------------------------
# 3. GRAVAR — com cópia do arquivo antes, e só a linha da chave mudando.
# -----------------------------------------------------------------------------
umask 077
cp -a "$ENV_FORUM" "$ENV_FORUM.bak-$(date +%s)" || parar "não consegui guardar a cópia de segurança. Nada foi alterado."

# Uma função para as DUAS variáveis: escrever cada uma com o seu próprio bloco
# de código seria a segunda expressão da mesma regra, e a primeira a esquecer a
# guarda da quebra de linha.
gravar() {  # chave, valor
  if grep -q "^$1=" "$ENV_FORUM"; then
    sed -i "s|^$1=.*|$1=$2|" "$ENV_FORUM" \
      || parar "a edição falhou. Há cópia intacta em $ENV_FORUM.bak-*."
  else
    # Sem esta guarda, um arquivo que não termina em quebra de linha grudaria a
    # linha nova no fim da última — e a última linha de um env é um valor.
    if [ -s "$ENV_FORUM" ] && [ "$(tail -c 1 "$ENV_FORUM" | wc -l)" -eq 0 ]; then
      printf '\n' >> "$ENV_FORUM" || parar "não consegui escrever em $ENV_FORUM."
    fi
    grep -q '^# A IA que rascunha resposta no forum' "$ENV_FORUM" \
      || printf '\n# A IA que rascunha resposta no forum (por-a-chave-da-ia-do-forum.sh).\n' >> "$ENV_FORUM"
    printf '%s=%s\n' "$1" "$2" >> "$ENV_FORUM" \
      || parar "não consegui escrever em $ENV_FORUM. Há cópia intacta em $ENV_FORUM.bak-*."
  fi
}

gravar ANTHROPIC_API_KEY "$CHAVE"
# O workspace é gravado MESMO VAZIO, e isso é decisão: a linha presente e vazia
# é o que faz o `provisionar-forum.sh` saber que ela existe, e é o que deixa
# trocar de chave sem herdar o workspace da anterior.
gravar ANTHROPIC_WORKSPACE_ID "$WORKSPACE"

# DONO E MODO copiados de um env que JÁ FUNCIONA, e SÓ quando mudaram
# (`armadilhas/091`, e o mesmo desenho do `garantir()` de
# `provisionar-forum.sh`): rodando como root, o `sed -i` recria o arquivo e
# pode deixá-lo root:root, e o usuário `deploy` (que é quem o pipeline usa)
# não lê um 600 de root. Conferir antes de agir evita chamar o `chown` onde
# ele não é preciso nem possível.
if [ "$(stat -c '%U:%G %a' "$ENV_FORUM" 2>/dev/null)" != "$(stat -c '%U:%G %a' "$ENV_REF" 2>/dev/null)" ]; then
  chown --reference="$ENV_REF" "$ENV_FORUM" 2>/dev/null \
    || parar "não consegui ajustar o dono de $ENV_FORUM — rode como root."
  chmod --reference="$ENV_REF" "$ENV_FORUM" 2>/dev/null \
    || parar "não consegui ajustar as permissões de $ENV_FORUM — rode como root."
fi

echo "  chave guardada .... ${#CHAVE} caracteres (não mostro o conteúdo, de propósito)"
if [ -n "$WORKSPACE" ]; then
  echo "  workspace ......... $WORKSPACE"
else
  echo "  workspace ......... vazio (só faz falta se a sua chave for do tipo novo)"
fi

# -----------------------------------------------------------------------------
# 4. RECARREGAR O FÓRUM — sem isto, a chave está no arquivo e o site não sabe.
#    Um container só relê o env dele quando renasce.
#
#    JAMAIS `docker compose up -d` sem argumento: isso devolveria TODAS as
#    células à tag :main do compose (RITOS §4). Só o `forum`, pelo nome.
# -----------------------------------------------------------------------------
echo
echo "== recarregando o fórum para ele reler o env =="
if ! command -v docker >/dev/null 2>&1; then
  echo "  (aviso: não achei o docker aqui. O arquivo JÁ está certo; o próximo deploy do fórum relê o env. Avise o agente.)"
  exit 0
fi

if ! docker compose config --services 2>/dev/null | grep -qx forum; then
  echo "  (aviso: o serviço 'forum' não está neste compose. O arquivo JÁ está certo. Avise o agente.)"
  exit 0
fi

if docker compose up -d forum >/dev/null 2>&1; then
  echo "  recarreguei o fórum"
else
  parar "não consegui recarregar o fórum. A chave JÁ está no arquivo, e há cópia do anterior em $ENV_FORUM.bak-*. Mande esta tela ao agente."
fi

# A conferência é de PRESENÇA, e o valor nunca aparece: `printenv` imprimiria a
# chave inteira na tela, que é exatamente o que este script existe para evitar.
LIDA="$(docker compose exec -T forum sh -c 'printf %s "${ANTHROPIC_API_KEY:-}" | wc -c' 2>/dev/null | tr -d '[:space:]')"
echo
if [ "$LIDA" = "${#CHAVE}" ]; then
  echo "== PRONTO =="
  echo "O fórum está com a chave (conferi: ${LIDA} caracteres, dentro do container)."
  echo
  echo "Para ver funcionando: abra https://meshcraft.top/forum, entre numa dúvida"
  echo "de aluno, e logo acima da caixa de responder vai estar a caixa"
  echo "'Rascunhar com a IA', com o botão 'Gerar resposta'."
  echo
  echo "Lembre: o texto dela cai na caixa de resposta para VOCÊ ler e ajustar."
  echo "Nada vai ao ar sem você clicar em Responder."
else
  echo "AVISO: gravei a chave e recarreguei o fórum, mas não consegui confirmar de"
  echo "dentro do container (li '${LIDA}' e esperava '${#CHAVE}')."
  echo "Não é motivo para colar de novo. Abra o fórum numa dúvida e veja se o botão"
  echo "'Gerar resposta' aparece; se não aparecer, mande esta tela ao agente."
fi
