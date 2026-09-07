#!/usr/bin/env bash
# =============================================================================
# LIGAR O BOTAO DE EXCLUIR TAREFA DA TELA DOS ROBOS, o passo do mantenedor.
# Guarda a chave do GitHub no env da area administrativa e recarrega a celula.
#
# PARA QUE ESTA CHAVE SERVE, em uma frase: quando voce aperta "excluir tarefa"
# em https://meshcraft.top/admin/caixa/robos/, o site precisa escrever essa
# decisao no GitHub (ele abre um pedido de mudanca, e a esteira o aprova). Sem
# a chave o botao nasce DESLIGADO, dizendo na propria tela que falta rodar este
# roteiro. Nada quebra sem ela; so o botao nao funciona.
#
# -----------------------------------------------------------------------------
# PRIMEIRO, NO NAVEGADOR: criar a chave. Isso e no seu computador, nao na VPS.
# -----------------------------------------------------------------------------
#   1. Abra https://github.com/settings/personal-access-tokens/new
#      (se pedir senha, e a sua conta abundanciabr do GitHub mesmo)
#   2. Em "Token name", escreva:  fila de tarefas do site
#   3. Em "Expiration", escolha a validade. Leia o paragrafo VALIDADE abaixo.
#   4. Em "Repository access", marque "Only select repositories" e escolha
#      APENAS o repositorio  abundanciabr/sitesdoreino
#   5. Em "Permissions", abra "Repository permissions" e ponha:
#         Contents ........ Read and write
#         Pull requests ... Read and write
#      Nao mexa em mais nada. Tudo o que ficar em "No access" e proposital: a
#      chave so pode fazer o que o botao precisa, e nada alem disso.
#   6. Clique em "Generate token" no fim da pagina.
#   7. A chave aparece UMA VEZ SO, numa faixa verde no topo. Ela comeca com
#      github_pat_ e e bem comprida. Copie ela inteira agora: se voce fechar a
#      pagina sem copiar, nao da para ver de novo, e ai e so gerar outra.
#
# VALIDADE: o GitHub obriga a escolher uma data de vencimento, e no dia em que
# ela vencer a chave para de valer sozinha. Isso e uma protecao, nao um defeito:
# uma chave que valesse para sempre continuaria valendo tambem se vazasse. O que
# acontece no dia do vencimento e o mesmo de hoje antes de rodar isto: o botao
# de excluir tarefa volta a ficar desligado, dizendo na tela que a chave venceu.
# Ai voce cria uma chave nova pelos passos acima e roda este roteiro de novo,
# que e seguro rodar quantas vezes for preciso.
#
# -----------------------------------------------------------------------------
# DEPOIS, NA VPS: rodar este roteiro.
# -----------------------------------------------------------------------------
# Cole a linha abaixo na janela da VPS. Voce sabe que e a janela certa porque o
# comeco da linha onde voce digita e deploy@srv... ou root@srv...; se estiver
# escrito PS C:\> voce esta no seu computador, e ai a linha nao vai funcionar.
#
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/por-a-chave-do-github.sh -o /tmp/gh.sh && bash /tmp/gh.sh
#
# TRES SURPRESAS, ditas antes para nao assustarem:
#   a) quando ele pedir a chave e voce colar, NADA vai aparecer na tela. Nem
#      pontinhos. Isso e de proposito e esta funcionando: e assim que a chave
#      nao fica gravada no historico da maquina nem aparece num print de tela.
#      Cole e aperte Enter as cegas.
#   b) silencio e sucesso. Se ele nao reclamar, deu certo, e no fim ele escreve
#      PRONTO.
#   c) se ele parar, a primeira palavra vai ser PAROU POR SEGURANCA, e a frase
#      seguinte diz o que fazer. Quando ele para, nada foi alterado.
#
# A CHAVE NUNCA VEM COMO ARGUMENTO desta linha de comando, e essa decisao e o
# que da nome ao arquivo. Argumento aparece na tela, fica no ~/.bash_history, e
# qualquer processo da maquina o le pelo ps aux. Foi assim que o segredo do
# OAuth do Google vazou em 24/08/2026 (armadilhas/090). Pelo mesmo motivo a
# chamada de conferencia ao GitHub, mais abaixo, passa a chave para o curl por
# um cano e nao por um -H na linha de comando.
#
# IDEMPOTENTE: rodar de novo e seguro, e e assim que se TROCA a chave (chave
# vencida, chave que voce apagou no GitHub). O env antigo vira .bak-<epoch>
# antes de qualquer edicao, e so a linha da chave muda.
# =============================================================================

# Carregado com `source` (ou `.`), um `exit` daqui derrubaria a sessao do
# mantenedor no meio do trabalho. Com `bash /tmp/gh.sh` o exit morre no filho.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANCA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessao. Rode com a palavra bash na frente: bash /tmp/gh.sh"
  return 1 2>/dev/null || exit 1
fi

set -u

parar() { echo "PAROU POR SEGURANCA: $1"; exit 1; }

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ENV_ADMIN="env/admin.env"
# A referencia de dono e permissao: um env que JA funciona nesta maquina
# (armadilhas/091). Rodando como root, uma edicao recria o arquivo e pode
# deixa-lo root:root, e ai o usuario deploy (que e quem o pipeline usa) nao le.
ENV_REF="env/identidade.env"
REPO="abundanciabr/sitesdoreino"

# -----------------------------------------------------------------------------
# 1. ONDE, e tudo conferido ANTES de pedir a chave.
#    Perguntar primeiro e descobrir depois que o arquivo nao existe faria o
#    mantenedor colar um segredo a toa, e colar segredo a toa e como um segredo
#    acaba num lugar errado.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "nao achei $RAIZ. Voce esta na VPS certa? O comeco da linha onde voce digita tem de ser deploy@srv... ou root@srv..., nunca PS C:\\>."
[ -f docker-compose.yml ] || parar "nao achei docker-compose.yml em $RAIZ."
[ -f "$ENV_ADMIN" ] || parar "nao achei $RAIZ/$ENV_ADMIN. A area administrativa ainda nao foi provisionada nesta maquina: rode antes o infra/provisionar-admin.sh. Nada foi alterado."
[ -w "$ENV_ADMIN" ] || parar "nao consigo escrever em $RAIZ/$ENV_ADMIN. Rode como root ou como o dono dos env. Nada foi alterado."
[ -f "$ENV_REF" ] || parar "nao achei $RAIZ/$ENV_REF, que e de onde eu copio dono e permissao. Nada foi alterado."
command -v curl >/dev/null 2>&1 || parar "nao achei o curl nesta maquina, e sem ele eu nao consigo perguntar ao GitHub se a chave presta. Gravar sem conferir seria pior. Mande esta tela ao agente. Nada foi alterado."

echo "== estado ANTES =="
if grep -q '^GITHUB_TOKEN_FILA=.\+' "$ENV_ADMIN" 2>/dev/null; then
  echo "  o botao de excluir tarefa ..... JA esta ligado (vou TROCAR a chave por esta nova)"
else
  echo "  o botao de excluir tarefa ..... desligado (vou ligar)"
fi
echo

# -----------------------------------------------------------------------------
# 2. A CHAVE, perguntada, invisivel, e conferida antes de tocar em nada.
# -----------------------------------------------------------------------------
echo "Abra https://github.com/settings/personal-access-tokens/new e crie a chave"
echo "pelos 7 passos que estao no comeco deste arquivo. Ela comeca com github_pat_"
echo "e e bem comprida."
echo
printf 'Cole a chave e aperte Enter (NADA vai aparecer na tela, isso e normal): '
read -r -s CHAVE
echo   # a quebra de linha que o -s engoliu
echo

# Espaco em volta e o acidente mais comum de quem copia de uma pagina web.
CHAVE="$(printf '%s' "$CHAVE" | tr -d '[:space:]')"

[ -n "$CHAVE" ] || parar "voce nao colou nada. Nada foi alterado."
case "$CHAVE" in
  github_pat_*|ghp_*) : ;;
  *) parar "isso nao parece uma chave do GitHub: ela comeca com github_pat_. Confira se voce copiou da faixa verde do topo da pagina, e a linha inteira. Nada foi alterado." ;;
esac
[ ${#CHAVE} -ge 40 ] || parar "a chave ficou curta demais (${#CHAVE} caracteres). Provavelmente veio pela metade: copie de novo, inteira. Nada foi alterado."
# So letras, numeros, hifen e sublinhado. Nao e frescura de formato: e o que
# torna o sed la embaixo seguro. Um caractere de pontuacao no meio do valor
# viraria parte da EXPRESSAO do sed, e o arquivo sairia corrompido.
case "$CHAVE" in
  *[!A-Za-z0-9_-]*) parar "a chave tem um caractere estranho. Copie de novo, direto da pagina do GitHub, sem passar por editor de texto. Nada foi alterado." ;;
esac

# -----------------------------------------------------------------------------
# 2b. PERGUNTAR AO GITHUB SE A CHAVE PRESTA, antes de grava-la.
#
# E esta secao que separa este roteiro de um `echo >>`. Uma chave colada pela
# metade, vencida, ou criada sem marcar o repositorio certo, e gravada sem
# conferencia, so falharia semanas depois, na hora em que ele apertasse o botao
# de excluir uma tarefa, e o sintoma seria uma tela de erro sem relacao visivel
# com o dia em que a chave foi colada. Conferir custa um segundo.
#
# A chave vai ao curl por um CANO (`curl -K -` le a configuracao da entrada
# padrao), nunca num `-H` da linha de comando: um -H apareceria no `ps aux` de
# qualquer processo da maquina enquanto a chamada acontece (armadilhas/090).
# -----------------------------------------------------------------------------
echo "Perguntando ao GitHub se a chave presta (um segundo)..."
HTTP="$(printf 'url = "https://api.github.com/repos/%s"\nheader = "Authorization: Bearer %s"\nheader = "Accept: application/vnd.github+json"\nheader = "X-GitHub-Api-Version: 2022-11-28"\nsilent\noutput = "/dev/null"\nwrite-out = "%%{http_code}"\nconnect-timeout = 10\nmax-time = 20\n' "$REPO" "$CHAVE" | curl -K - 2>/dev/null)"
# So os digitos, e so os TRES ULTIMOS: o codigo tem sempre tres digitos e o
# `write-out` o poe no fim. Se algum dia o corpo da resposta escapar para a
# saida, os numeros dele ficam antes, e a leitura continua certa.
HTTP="$(printf '%s' "$HTTP" | tr -cd '0-9' | tail -c 3)"

case "$HTTP" in
  200)
    echo "  o GitHub respondeu 200, que quer dizer: a chave vale e enxerga o $REPO."
    ;;
  401)
    parar "o GitHub recusou a chave (resposta 401, que quer dizer 'nao te conheco'). Ou ela veio pela metade, ou foi apagada, ou voce colou outra coisa. Crie uma chave nova pelos 7 passos do comeco deste arquivo e rode isto de novo. Nada foi alterado."
    ;;
  403)
    parar "o GitHub conhece a chave mas nao deixou ela ver o $REPO (resposta 403). Isso costuma ser chave criada sem marcar 'Only select repositories' com o $REPO, ou sem a permissao Contents. Refaca os passos 4 e 5 do comeco deste arquivo. Nada foi alterado."
    ;;
  404)
    parar "o GitHub disse que o $REPO nao existe para esta chave (resposta 404). Quase sempre e a mesma coisa do 403: a chave nao foi ligada a ESTE repositorio no passo 4. Refaca os passos 4 e 5 do comeco deste arquivo. Nada foi alterado."
    ;;
  "")
    parar "nao consegui falar com o GitHub daqui (a chamada nao voltou). Pode ser a internet da VPS. Espere um minuto e rode isto de novo; se insistir, mande esta tela ao agente. Nada foi alterado."
    ;;
  *)
    parar "o GitHub respondeu $HTTP, que eu nao sei interpretar, e gravar uma chave sem ter certeza de que ela presta seria pior do que nao gravar. Mande esta tela ao agente. Nada foi alterado."
    ;;
esac
echo

# -----------------------------------------------------------------------------
# 3. GRAVAR, com copia do arquivo antes, e so a linha da chave mudando.
# -----------------------------------------------------------------------------
umask 077
cp -a "$ENV_ADMIN" "$ENV_ADMIN.bak-$(date +%s)" || parar "nao consegui guardar a copia de seguranca. Nada foi alterado."

if grep -q '^GITHUB_TOKEN_FILA=' "$ENV_ADMIN"; then
  sed -i "s|^GITHUB_TOKEN_FILA=.*|GITHUB_TOKEN_FILA=$CHAVE|" "$ENV_ADMIN" \
    || parar "a edicao falhou. Ha copia intacta em $ENV_ADMIN.bak-*."
else
  # Sem esta guarda, um arquivo que nao termina em quebra de linha grudaria a
  # linha nova no fim da ultima, e a ultima linha de um env e um valor.
  if [ -s "$ENV_ADMIN" ] && [ "$(tail -c 1 "$ENV_ADMIN" | wc -l)" -eq 0 ]; then
    printf '\n' >> "$ENV_ADMIN" || parar "nao consegui escrever em $ENV_ADMIN."
  fi
  printf '\n# A chave do GitHub que grava a exclusao de tarefa (por-a-chave-do-github.sh).\n' >> "$ENV_ADMIN" \
    || parar "nao consegui escrever em $ENV_ADMIN. Ha copia intacta em $ENV_ADMIN.bak-*."
  printf 'GITHUB_TOKEN_FILA=%s\n' "$CHAVE" >> "$ENV_ADMIN" \
    || parar "nao consegui escrever em $ENV_ADMIN. Ha copia intacta em $ENV_ADMIN.bak-*."
fi

# DONO E MODO copiados de um env que JA FUNCIONA, e SO quando mudaram
# (armadilhas/091, e o mesmo desenho do provisionar-admin.sh): rodando como
# root, o sed -i recria o arquivo e pode deixa-lo root:root, e o usuario deploy
# (que e quem o pipeline usa) nao le um 600 de root. Conferir antes de agir
# evita chamar o chown onde ele nao e preciso nem possivel.
if [ "$(stat -c '%U:%G %a' "$ENV_ADMIN" 2>/dev/null)" != "$(stat -c '%U:%G %a' "$ENV_REF" 2>/dev/null)" ]; then
  chown --reference="$ENV_REF" "$ENV_ADMIN" 2>/dev/null \
    || parar "nao consegui ajustar o dono de $ENV_ADMIN. Rode como root."
  chmod --reference="$ENV_REF" "$ENV_ADMIN" 2>/dev/null \
    || parar "nao consegui ajustar as permissoes de $ENV_ADMIN. Rode como root."
fi

echo "== estado DEPOIS =="
echo "  chave guardada ................ ${#CHAVE} caracteres (nao mostro o conteudo, de proposito)"
echo "  dono e permissao do env ....... $(stat -c '%U:%G %a' "$ENV_ADMIN") (igual ao $ENV_REF: $(stat -c '%U:%G %a' "$ENV_REF"))"

# -----------------------------------------------------------------------------
# 4. RECARREGAR A AREA ADMINISTRATIVA, sem o que a chave esta no arquivo e o
#    site nao sabe. Um container so rele o env dele quando renasce.
#
#    JAMAIS `docker compose up -d` sem argumento: isso devolveria TODAS as
#    celulas a tag :main do compose (RITOS parag. 4). So a `admin`, pelo nome.
# -----------------------------------------------------------------------------
echo
echo "== recarregando a area administrativa para ela reler o env =="
if ! command -v docker >/dev/null 2>&1; then
  echo "  (aviso: nao achei o docker aqui. O arquivo JA esta certo; o proximo deploy da area administrativa rele o env. Avise o agente.)"
  exit 0
fi

if ! docker compose config --services 2>/dev/null | grep -qx admin; then
  echo "  (aviso: o servico 'admin' nao esta neste compose. O arquivo JA esta certo. Avise o agente.)"
  exit 0
fi

# A SAIDA DE ERRO NUNCA VAI PARA O LIXO AQUI (armadilhas/377). Em 06/09/2026 um
# roteiro desta casa recarregou duas celulas com `>/dev/null 2>&1`, o comando
# falhou, e o texto que teria dito o porque foi apagado: a pagina ficou 502 por
# minutos enquanto a tela dizia PRONTO. `docker compose up -d` REMOVE o
# container velho antes de subir o novo, entao falhar no meio nao deixa as
# coisas como estavam, deixa a celula fora do ar.
SAIDA_UP="$(docker compose up -d admin 2>&1)"
CODIGO_UP=$?

# E O QUE VALE E O ESTADO MEDIDO, nao o codigo de saida do `up`: sair zero nao e
# prova de container de pe.
ESTADO="$(docker compose ps admin 2>&1)"
NO_AR=0
case "$ESTADO" in
  *[Uu]p*) NO_AR=1 ;;
esac

if [ "$NO_AR" -eq 1 ]; then
  echo "  recarreguei a area administrativa, e conferi que ela voltou de pe:"
  printf '%s\n' "$ESTADO" | sed 's/^/    /'
else
  echo
  echo "PAROU POR SEGURANCA: eu recarreguei a area administrativa e ela NAO"
  echo "voltou de pe. Isso quer dizer que https://meshcraft.top/admin/ esta fora"
  echo "do ar NESTE MOMENTO, e nao e um aviso de rodape: precisa de conserto."
  echo
  echo "A chave JA esta gravada e certa, e ha copia do env anterior em"
  echo "$ENV_ADMIN.bak-*, entao nao cole a chave de novo."
  echo
  echo "COLE ESTA LINHA AQUI MESMO, nesta janela da VPS, para levantar de volta:"
  echo
  echo "  cd $RAIZ && docker compose up -d admin; docker compose ps admin"
  echo
  echo "Se depois disso ela continuar fora do ar, mande esta tela inteira ao agente."
  echo
  echo "O que o docker respondeu (codigo $CODIGO_UP):"
  printf '%s\n' "$SAIDA_UP" | sed 's/^/    /'
  echo "  o estado que eu li:"
  printf '%s\n' "$ESTADO" | sed 's/^/    /'
  exit 1
fi

# A PROVA DE FORA, que e a que vale: o site respondendo pela porta publica. Um
# container "Up" que devolve 502 na borda continua sendo uma pagina quebrada.
if command -v curl >/dev/null 2>&1; then
  SAUDE="$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 10 --max-time 20 https://meshcraft.top/admin/healthz 2>/dev/null)"
  case "$SAUDE" in
    200) echo "  e a area administrativa responde de fora (https://meshcraft.top/admin/healthz devolveu 200)" ;;
    "")  echo "  (nao consegui perguntar de fora se o site responde. Abra https://meshcraft.top/admin/ no navegador para conferir com os olhos.)" ;;
    *)   echo "  ATENCAO: de dentro ela esta de pe, mas https://meshcraft.top/admin/healthz devolveu $SAUDE em vez de 200. Espere um minuto (ela pode estar acabando de subir), abra https://meshcraft.top/admin/ no navegador, e se continuar errado mande esta tela ao agente." ;;
  esac
fi

# A conferencia e de PRESENCA, e o valor nunca aparece: um printenv imprimiria a
# chave inteira na tela, que e exatamente o que este roteiro existe para evitar.
LIDA="$(docker compose exec -T admin sh -c 'printf %s "${GITHUB_TOKEN_FILA:-}" | wc -c' 2>/dev/null | tr -d '[:space:]')"
echo
if [ "$LIDA" = "${#CHAVE}" ]; then
  echo "== PRONTO =="
  echo "A area administrativa esta com a chave (conferi: ${LIDA} caracteres, dentro"
  echo "do container), e o GitHub ja confirmou que ela presta."
  echo
  echo "Para ver funcionando: abra https://meshcraft.top/admin/caixa/robos/ e o"
  echo "botao de excluir tarefa vai estar ligado. Ao apertar, o site abre um"
  echo "pedido de mudanca no GitHub e a esteira o aprova sozinha; a tarefa some"
  echo "da fila em alguns minutos, nao na hora."
  echo
  echo "Guarde a data de vencimento que voce escolheu. No dia em que ela chegar,"
  echo "o botao volta a ficar desligado dizendo isso, e ai e criar chave nova e"
  echo "rodar esta mesma linha de novo."
else
  echo "AVISO: gravei a chave e recarreguei a area administrativa, mas nao consegui"
  echo "confirmar de dentro do container (li '${LIDA}' e esperava '${#CHAVE}')."
  echo "Nao e motivo para colar de novo, e o GitHub ja disse que a chave presta."
  echo "Abra https://meshcraft.top/admin/caixa/robos/ e veja se o botao de excluir"
  echo "tarefa esta ligado; se nao estiver, mande esta tela ao agente."
fi
