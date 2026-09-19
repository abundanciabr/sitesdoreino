#!/usr/bin/env bash
# =============================================================================
# LEVAR A CHAVE DA IA ATE A AREA ADMINISTRATIVA, o passo do mantenedor.
# Copia a chave da Anthropic (e o workspace dela, quando existe) de
# `env/forum.env` para `env/admin.env` e recria a celula `admin` para ela reler
# o arquivo.
#
# PARA QUE ESTA CHAVE SERVE, em uma frase: o robo analista do painel de gestao
# (degrau 16 do PLANO-PAINEL-DE-GESTAO) le o livro de ocorrencias e escreve o
# que esta vendo em portugues. Sem a chave ele nasce DESLIGADO em producao.
# Nada mais na area administrativa muda por causa disto: quem ja usa
# `/admin/` nao ve diferenca nenhuma nas outras telas.
#
# COMO O MANTENEDOR RODA (dentro da VPS, uma linha so, SEM argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/por-a-chave-da-ia-do-admin.sh -o /tmp/ia-admin.sh && bash /tmp/ia-admin.sh
#
#   O prompt tem de comecar com `deploy@srv...` ou `root@srv...`. Se comecar
#   com `PS C:\>`, voce esta no seu computador e este roteiro nao e para la.
#
# ELE TERMINA DE TRES JEITOS, e de nenhum outro. Quem cola isto e leigo em
# terminal, e uma tela que diz duas coisas ao mesmo tempo faz a pessoa escolher
# a que preferir ler:
#
#   1. `== PRONTO ==`. A chave chegou DENTRO do container, conferida por
#      resumo. E o unico verde, e so ele quer dizer que o robo analista pode
#      falar.
#   2. `(aviso: ...)`. Nao havia o que recarregar nesta maquina (sem docker, ou
#      sem o servico `admin` no compose). O arquivo ficou certo e o proximo
#      deploy rele o env sozinho. Nao e falha, e nao e PRONTO.
#   3. `PAROU POR SEGURANÇA: ...`. Qualquer outra coisa, e a frase seguinte diz
#      o que fazer. TUDO que nao provou que a chave chegou cai aqui: o docker
#      recusando, o container que nao renasceu, e o container que renasceu com
#      outra chave dentro.
#
# NAO EXISTE "PRONTO com ressalva". Ate 07/09/2026 existia: quando a chave nao
# chegava ao container, este roteiro imprimia um AVISO de rodape e terminava
# como se tivesse dado certo. O mantenedor ia ligar um robo que estava
# desligado, e a tela seguinte quebraria sem ele saber por que.
#
# ELE NAO PERGUNTA NADA, e essa e a decisao que da forma ao arquivo. A chave JA
# EXISTE nesta maquina desde 02/09/2026: o mantenedor a colou uma vez, em
# `env/forum.env`, pelo `infra/por-a-chave-da-ia-do-forum.sh`. Pedir de novo o
# que a maquina ja sabe seria faze-lo colar um segredo a toa, e colar segredo a
# toa e como um segredo acaba num lugar errado (`armadilhas/090`).
#
# E NENHUM VALOR PASSA POR ARGUMENTO DE LINHA DE COMANDO. Argumento e lido por
# qualquer processo da maquina pelo `ps aux`, fica no `~/.bash_history`, e vai
# junto no print de tela que o mantenedor manda ao agente para provar que
# funcionou. Foi assim que o segredo do OAuth do Google vazou em 24/08/2026.
#
# POR QUE E COPIA, e nao ligacao viva: cada celula le o proprio `env_file`, e
# nao existe um env comum nesta plataforma. A copia e uma FOTOGRAFIA. No dia em
# que a chave for trocada no forum, rode este roteiro de novo para a area
# administrativa acompanhar; ate la ela continua com a chave antiga, e o
# sintoma seria a IA do forum funcionando e a do painel recusando.
#
# IDEMPOTENTE: rodar de novo e seguro, e e o jeito de atualizar a copia. O env
# antigo vira `.bak-<epoch>` antes de qualquer edicao, e o bloco das duas
# linhas e reescrito INTEIRO, nunca duplicado: duas linhas
# `ANTHROPIC_API_KEY=` no mesmo env fazem o valor depender da ordem de leitura.
#
# O QUE ELE NAO FAZ, e a ausencia e decisao: nao cria chave, nao troca chave, e
# nao fala com a Anthropic. A chave nasce na conta do mantenedor e custa
# dinheiro por uso; aqui ela e so transportada de um arquivo desta maquina para
# outro arquivo desta mesma maquina.
# =============================================================================

# Carregado com `source` (ou `.`), um `exit` daqui derrubaria a sessao do
# mantenedor no meio do trabalho, que e o modo de falha de 24/08/2026. Com
# `bash /tmp/ia-admin.sh` o exit morre no processo filho.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANÇA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessao. Rode com a palavra bash na frente: bash /tmp/ia-admin.sh"
  return 1 2>/dev/null || exit 1
fi

set -u

parar() { echo; echo "PAROU POR SEGURANÇA: $1"; exit 1; }

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ENV_ADMIN="env/admin.env"
ENV_FORUM="env/forum.env"
# A referencia de dono e permissao: um env que JA funciona nesta maquina
# (`armadilhas/091`). Rodando como root, uma edicao que recria o arquivo pode
# deixa-lo root:root, e ai o usuario `deploy` (que e quem o pipeline usa) nao
# consegue ler o env e a celula sobe sem nada.
ENV_REF="env/identidade.env"

# A marca do bloco que este roteiro escreve. Ela e filtrada na reescrita para o
# cabecalho nao empilhar a cada execucao, e por isso e uma linha LITERAL e
# fixa: muda-la aqui sem mudar o filtro la embaixo deixaria duas.
MARCA="# escrito por infra/por-a-chave-da-ia-do-admin.sh"

# O valor EXATAMENTE como esta no arquivo, do primeiro "=" para a frente.
#
# SEM LIMPEZA NENHUMA, e a ausencia e o conserto: a versao anterior apagava
# espacos e cortava o que viesse depois de um "#" ANTES de conferir os
# caracteres, e assim a conferencia aprovava o que ela mesma tinha acabado de
# arrumar. Uma chave colada como `sk-ant-api03-AAA BBB` era gravada como
# `sk-ant-api03-AAABBB` e o roteiro dizia que estava tudo certo, com uma chave
# que a Anthropic recusa. Valor sujo aqui vira recusa la embaixo, nunca
# conserto silencioso.
#
# O unico corte e o retorno de carro de um arquivo salvo no Windows: aquilo e
# fim de linha, e nao parte do valor.
ler_valor() {  # arquivo, chave
  local linha
  linha="$(grep "^$2=" "$1" 2>/dev/null | head -1 | cut -d= -f2-)"
  printf '%s' "${linha%$'\r'}"
}

# -----------------------------------------------------------------------------
# 1. ONDE, tudo conferido ANTES de tocar em arquivo nenhum.
#    Descobrir no meio do caminho que falta um arquivo deixaria meia-instalacao
#    para desfazer, e e a metade que ninguem percebe que ficou.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "nao achei $RAIZ. Voce esta na VPS certa? O comeco da linha onde voce digita tem de ser deploy@srv... ou root@srv..., nunca PS C:\\>."
[ -f docker-compose.yml ] || parar "nao achei docker-compose.yml em $RAIZ."
[ -f "$ENV_ADMIN" ] || parar "nao achei $RAIZ/$ENV_ADMIN. A area administrativa ainda nao foi provisionada nesta maquina: rode antes o infra/provisionar-admin.sh. Nada foi alterado."
[ -w "$ENV_ADMIN" ] || parar "nao consigo escrever em $RAIZ/$ENV_ADMIN. Rode como root ou como o dono dos env. Nada foi alterado."
[ -f "$ENV_FORUM" ] || parar "nao achei $RAIZ/$ENV_FORUM, que e de onde eu copio a chave da IA. Rode antes o infra/provisionar-forum.sh e depois o infra/por-a-chave-da-ia-do-forum.sh. Nada foi alterado."
[ -f "$ENV_REF" ] || parar "nao achei $RAIZ/$ENV_REF, que e de onde eu copio dono e permissao. Nada foi alterado."

# -----------------------------------------------------------------------------
# 2. OS DOIS VALORES, lidos e conferidos ANTES de escrever.
#    Ler antes de escrever e o que faz uma recusa significar "nada foi
#    alterado" de verdade.
# -----------------------------------------------------------------------------
echo "== 1/4: lendo o que esta maquina ja sabe =="

CHAVE_DA_IA="$(ler_valor "$ENV_FORUM" ANTHROPIC_API_KEY)"
[ -n "$CHAVE_DA_IA" ] || parar "o ANTHROPIC_API_KEY de $RAIZ/$ENV_FORUM esta vazio, e e de la que eu copio a chave da IA. Rode primeiro: curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/por-a-chave-da-ia-do-forum.sh -o /tmp/ia.sh && bash /tmp/ia.sh, e depois este de novo. Nada foi alterado."
# So letras, numeros, hifen e sublinhado. Nao e frescura de formato: e o que
# garante que o valor entra no arquivo como uma linha so, sem virar comentario
# nem carregar aspas pela metade.
case "$CHAVE_DA_IA" in
  *[!A-Za-z0-9_-]*) parar "a chave em $ENV_FORUM tem um caractere estranho e eu nao a gravo assim. Rode de novo o infra/por-a-chave-da-ia-do-forum.sh, colando a chave direto do site da Anthropic. Nada foi alterado." ;;
esac

# O workspace da chave. VAZIO E RESPOSTA LEGITIMA e por isso nao para aqui:
# quem usa chave classica (de workspace) nao tem esse numero, e o forum trata
# assim desde 02/09/2026. So a chave nova, ligada a identidade de quem a criou,
# e recusada sem ele, com HTTP 400. A LINHA nasce mesmo vazia, de proposito: e
# ela que deixa trocar de chave sem herdar o workspace da anterior.
WORKSPACE_DA_IA="$(ler_valor "$ENV_FORUM" ANTHROPIC_WORKSPACE_ID)"
case "$WORKSPACE_DA_IA" in
  *[!A-Za-z0-9_-]*) parar "o ANTHROPIC_WORKSPACE_ID de $ENV_FORUM tem um caractere estranho. Confira aquele arquivo. Nada foi alterado." ;;
esac

# O valor NUNCA aparece na tela, so o tamanho dele: e o print de tela que o
# mantenedor manda ao agente que faz um segredo mudar de lugar.
echo "  chave da IA no forum ...... ${#CHAVE_DA_IA} caracteres (nao mostro o conteudo, de proposito)"
if [ -n "$WORKSPACE_DA_IA" ]; then
  echo "  workspace da IA ........... $WORKSPACE_DA_IA"
else
  echo "  workspace da IA ........... vazio (e o normal para chave de workspace)"
fi
if [ "$(ler_valor "$ENV_ADMIN" ANTHROPIC_API_KEY)" = "$CHAVE_DA_IA" ]; then
  echo "  na area administrativa .... a mesma chave ja esta la (vou reescrever igual e recarregar)"
else
  echo "  na area administrativa .... ainda nao esta la (vou levar)"
fi
echo

# -----------------------------------------------------------------------------
# 3. GRAVAR, com copia do arquivo antes e o bloco reescrito inteiro.
#
#    A reescrita tira as duas linhas antigas e as poe de volta juntas, no fim.
#    E o que faz a segunda execucao deixar o arquivo IGUAL a primeira, em vez de
#    empilhar cabecalho e linha repetida.
#
#    Quem escreve e o `printf`, que e palavra interna do shell e nao cria
#    processo nenhum: um `sed -i "s|^X=.*|X=$valor|"` poria o segredo no argv do
#    `sed`, e argv e lido por qualquer processo da maquina (`armadilhas/090`).
# -----------------------------------------------------------------------------
echo "== 2/4: gravando em $ENV_ADMIN =="
umask 077
cp -a "$ENV_ADMIN" "$ENV_ADMIN.bak-$(date +%s)" || parar "nao consegui guardar a copia de seguranca de $ENV_ADMIN. Nada foi alterado."

NOVO="$ENV_ADMIN.novo-$$"
# ESTE ARQUIVO CARREGA A CHAVE DENTRO. Entre a escrita dele e a troca existem
# alguns segundos, e um Ctrl-C ali deixaria o segredo em $RAIZ/env/ com um nome
# que nenhuma mensagem cita: ninguem procuraria, e nenhuma execucao seguinte o
# apagaria (`armadilhas/090`). O `trap` fecha essa janela em qualquer saida,
# inclusive nas que este roteiro nao escolheu.
trap 'rm -f "$NOVO"' EXIT INT TERM
# Dois filtros em vez de um so com alternancia: o segundo e `-xF`, texto fixo e
# linha inteira, e assim a MARCA nao precisa ser escapada como expressao. Um
# ponto sem escape numa expressao casa qualquer caractere, e e assim que um
# filtro come a linha errada sem ninguem perceber.
grep -vE '^(ANTHROPIC_API_KEY|ANTHROPIC_WORKSPACE_ID)=' "$ENV_ADMIN" \
  | grep -vxF "$MARCA" > "$NOVO"
# Saida vazia aqui so acontece se a leitura falhou: um `admin.env` de verdade
# tem DATABASE_URL e ADMIN_EMAILS. Escrever por cima com um arquivo vazio seria
# o pior desfecho possivel (a area administrativa inteira sairia do ar), entao
# eu paro antes.
[ -s "$NOVO" ] || parar "a reescrita de $ENV_ADMIN saiu vazia, e eu nao escrevo por cima assim. NADA foi alterado; ha copia intacta em $ENV_ADMIN.bak-*."

# NAO HA GUARDA DE QUEBRA DE LINHA AQUI, e a ausencia e medida, nao esquecida.
# Um `admin.env` que termine sem quebra de linha grudaria a primeira linha nova
# no fim da ultima, e a ultima linha de um env e um VALOR. Quem ja resolve isso
# e o `grep` acima: ele termina TODA linha que imprime, inclusive a ultima, e
# por isso `$NOVO` sempre chega aqui com a quebra. Uma guarda a mais nunca
# rodaria, e guarda que nunca roda e decoracao que um dia alguem acredita. O
# desfecho continua provado, pelo caminho de fora, em
# `ci/tests/test_por_a_chave_da_ia_do_admin.py`.
{
  printf '%s\n' "$MARCA"
  printf 'ANTHROPIC_API_KEY=%s\n' "$CHAVE_DA_IA"
  printf 'ANTHROPIC_WORKSPACE_ID=%s\n' "$WORKSPACE_DA_IA"
} >> "$NOVO" || parar "nao consegui escrever em $RAIZ. Nada foi alterado."

# `cat >` e nao `mv`, de proposito: assim o arquivo mantem o mesmo inode, e com
# ele o dono e a permissao que ja funcionavam. Um `mv` traria dono e modo do
# arquivo temporario (root:root, rodando como root) e o usuario `deploy`, que e
# quem o pipeline usa, deixaria de ler o env (`armadilhas/091`).
cat "$NOVO" > "$ENV_ADMIN" || parar "a escrita de $ENV_ADMIN falhou no meio. Ha copia intacta em $ENV_ADMIN.bak-*: recupere-a com cp e mande esta tela ao agente."
rm -f "$NOVO"

# A conferencia do dono, mesmo assim: se o arquivo ja estava com dono errado
# antes de eu chegar, o problema nao e meu mas o efeito seria (a area
# administrativa subiria sem env nenhum). So age quando de fato divergiu.
if [ "$(stat -c '%U:%G %a' "$ENV_ADMIN" 2>/dev/null)" != "$(stat -c '%U:%G %a' "$ENV_REF" 2>/dev/null)" ]; then
  chown --reference="$ENV_REF" "$ENV_ADMIN" 2>/dev/null \
    || parar "nao consegui ajustar o dono de $ENV_ADMIN. As linhas JA estao gravadas; rode este roteiro de novo como root."
  chmod --reference="$ENV_REF" "$ENV_ADMIN" 2>/dev/null \
    || parar "nao consegui ajustar as permissoes de $ENV_ADMIN. As linhas JA estao gravadas; rode este roteiro de novo como root."
fi
echo "  $ENV_ADMIN ..... escrito ($(grep -c '=' "$ENV_ADMIN") variaveis)"
echo "  dono e permissao ..... $(stat -c '%U:%G %a' "$ENV_ADMIN" 2>/dev/null) (igual ao $ENV_REF: $(stat -c '%U:%G %a' "$ENV_REF" 2>/dev/null))"
echo

# -----------------------------------------------------------------------------
# 4. RECARREGAR. Sem isto, as linhas estao no arquivo e a area administrativa
#    nao sabe: um container so rele o env dele quando renasce.
#
#    JAMAIS `docker compose up -d` sem argumento: isso devolveria TODAS as
#    celulas a tag :main do compose (RITOS parag. 4). So a `admin`, pelo nome.
# -----------------------------------------------------------------------------
echo "== 3/4: recarregando a area administrativa para ela reler o env =="

# O CAMINHO DECLARADO de nao ter o que recarregar, e ele nao e falha nenhuma: o
# arquivo JA esta certo, e o proximo deploy da area administrativa rele o env
# sozinho. Parar aqui faria o mantenedor achar que perdeu o trabalho.
if ! command -v docker >/dev/null 2>&1; then
  echo "  (aviso: nao achei o docker nesta maquina. O arquivo JA esta certo; o proximo deploy da area administrativa rele o env. Avise o agente.)"
  exit 0
fi

# O texto de conserto que serve a TODAS as recusas daqui para baixo: a partir
# deste ponto as linhas ja estao gravadas, e o que pode dar errado e sempre a
# area administrativa nao ter voltado.
COMO_LEVANTAR="A chave JA esta gravada e certa, e ha copia do env anterior em
$RAIZ/$ENV_ADMIN.bak-*, entao nao rode este roteiro de novo por causa dela.

COLE ESTA LINHA AQUI MESMO, nesta janela da VPS, para levantar de volta:

  cd $RAIZ && docker compose up -d admin; docker compose ps admin

Se depois disso ela continuar fora do ar, mande esta tela inteira ao agente."

# `config` falha por muito mais do que servico ausente: basta um `env_file`
# citado no compose estar faltando. Traduzir QUALQUER falha dele para "o
# servico admin nao esta no docker-compose.yml" seria afirmar uma causa que
# ninguem mediu, e mandar o mantenedor procurar o problema errado.
SERVICOS="$(docker compose config --services 2>&1)"
CODIGO_CONFIG=$?
[ "$CODIGO_CONFIG" -eq 0 ] || parar "o docker nao conseguiu ler o docker-compose.yml desta maquina (codigo $CODIGO_CONFIG), e assim eu nao sei nem se a area administrativa esta declarada nele.

A chave JA esta gravada em $RAIZ/$ENV_ADMIN e ha copia do anterior em $RAIZ/$ENV_ADMIN.bak-*, entao nao rode este roteiro de novo por causa dela.

O que o docker respondeu:
$(printf '%s\n' "$SERVICOS" | sed 's/^/    /')

Mande esta tela ao agente."

if ! printf '%s\n' "$SERVICOS" | grep -qx admin; then
  echo "  (aviso: o servico 'admin' nao esta no docker-compose.yml desta maquina. O arquivo JA esta certo; o proximo deploy da area administrativa rele o env. Avise o agente.)"
  exit 0
fi

# O ID DO CONTAINER ANTES, porque e a unica medicao que distingue "recriado" de
# "nunca foi tocado". Um `up` que falha no meio deixa o container ANTIGO
# rodando, e ai o `docker compose ps` continua dizendo "Up" com a maior calma:
# quem le so o "Up" esta lendo o container errado, com o env antigo dentro.
ID_ANTES="$(docker compose ps -q admin 2>/dev/null | tr -d '[:space:]')"

# A SAIDA DE ERRO NUNCA VAI PARA O LIXO AQUI (`armadilhas/377`). Em 06/09/2026
# um roteiro desta casa recarregou duas celulas com `>/dev/null 2>&1`, o comando
# falhou, e o texto que teria dito o porque foi apagado: a pagina ficou 502 por
# minutos enquanto a tela dizia PRONTO.
#
# `--force-recreate` porque `up -d` sozinho ve a mesma imagem e a mesma
# configuracao de compose e nao faz nada, e mudanca DENTRO do env_file nao conta
# como mudanca para ele. Sem isso, a chave ficaria no arquivo e fora do processo.
SAIDA_UP="$(docker compose up -d --force-recreate --wait --wait-timeout 180 admin 2>&1)"
CODIGO_UP=$?

# O CODIGO DE SAIDA NAO SE JOGA FORA. Ele e a unica coisa que sabe a diferenca
# entre "recriei" e "tentei recriar e o container novo nem passou no exame de
# saude"; nos dois casos o `ps` pode dizer "Up".
[ "$CODIGO_UP" -eq 0 ] || parar "eu pedi ao docker para recarregar a area administrativa e ele recusou (codigo $CODIGO_UP). Ela pode estar fora do ar NESTE MOMENTO, e isso precisa de conserto.

$COMO_LEVANTAR

O que o docker respondeu:
$(printf '%s\n' "$SAIDA_UP" | sed 's/^/    /')"

# O id de DEPOIS. Ele nao veta sozinho, e a decisao e deliberada: se o
# container nao renasceu mas ja estava com a chave certa dentro, esta tudo bem
# de verdade, e recusar quem esta certo e o pior defeito que um roteiro de
# colar pode ter. O que ele faz e transformar uma chave errada la dentro em
# diagnostico: "nao renasceu" e "renasceu e mesmo assim leu outra coisa" sao
# dois problemas diferentes, com conserto diferente, e sem esta medicao os dois
# chegariam ao agente com a mesma cara.
ID_DEPOIS="$(docker compose ps -q admin 2>/dev/null | tr -d '[:space:]')"
if [ "$ID_DEPOIS" = "$ID_ANTES" ]; then
  RENASCEU="NAO: o container e exatamente o mesmo de antes, e um container so le o env quando renasce"
else
  RENASCEU="sim, este container e outro"
fi

ESTADO="$(docker compose ps admin 2>&1)"
case "$ESTADO" in
  *[Uu]p*) ;;
  *) parar "eu recarreguei a area administrativa e ela NAO voltou de pe. Ela esta fora do ar NESTE MOMENTO.

$COMO_LEVANTAR

O que o docker respondeu:
$(printf '%s\n' "$ESTADO" | sed 's/^/    /')" ;;
esac

echo "  recarreguei a area administrativa, e conferi que ela voltou de pe:"
printf '%s\n' "$ESTADO" | sed 's/^/    /'
echo

# -----------------------------------------------------------------------------
# 5. A PROVA, medida DE DENTRO do container. "O comando devolveu zero" nao e
#    evidencia de nada: o arquivo estar certo e o processo estar com ele sao
#    duas coisas diferentes, e a segunda e a que vale.
#
#    NAO HA `curl` PARA A INTERNET AQUI, e a ausencia e conserto: um endereco
#    fixo mede o site de PRODUCAO, rode este roteiro na maquina que rodar, e
#    chamar isso de prova do que acabou de acontecer aqui e medir o vizinho e
#    assinar embaixo.
# -----------------------------------------------------------------------------
echo "== 4/4: conferindo =="

# POR RESUMO, e nao por tamanho. Duas chaves da mesma conta da Anthropic tem o
# mesmo comprimento, e acompanhar uma troca de chave e o caso NORMAL deste
# roteiro: medindo tamanho, a chave velha ainda no processo passaria por chave
# nova sem ninguem perceber. O resumo distingue as duas e continua sem mostrar
# segredo nenhum, porque doze caracteres de um sha256 nao voltam a ser a chave.
RESUMO_ESPERADO="$(printf %s "$CHAVE_DA_IA" | sha256sum 2>/dev/null | cut -c1-12)"
[ -n "$RESUMO_ESPERADO" ] || parar "nao consegui calcular o resumo da chave nesta maquina (faltou o programa sha256sum), e sem ele eu nao tenho como provar que a chave certa chegou ao container. As linhas JA estao gravadas em $RAIZ/$ENV_ADMIN. Mande esta tela ao agente."
MEDIDA_ESPERADA="$RESUMO_ESPERADO:${#CHAVE_DA_IA}"

# O comando que roda LA DENTRO nao carrega valor nenhum, so o NOME da variavel:
# o segredo nunca passa pelo argv do docker (`armadilhas/090`). Vem de la o
# resumo e a contagem, e e a contagem que separa "nao chegou nada" de "chegou
# outra coisa" na hora de dizer ao mantenedor o que houve.
MEDIDA_LIDA="$(docker compose exec -T admin sh -c 'printf %s "${ANTHROPIC_API_KEY:-}" | sha256sum | cut -c1-12; printf ":"; printf %s "${ANTHROPIC_API_KEY:-}" | wc -c' 2>&1 | tr -d '[:space:]')"

# A FORMA DA RESPOSTA E CONFERIDA, e nao so o conteudo dela. Qualquer coisa que
# nao seja doze digitos de resumo, dois-pontos e um numero e uma resposta que
# eu nao entendi (o container recusou a pergunta, faltou o sha256sum na imagem
# dele, o docker reclamou de outra coisa), e resposta que eu nao entendi NAO
# vira diagnostico: vira o texto cru na tela, para o agente ler.
DOZE_DO_RESUMO='[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'
case "$MEDIDA_LIDA" in
  "$MEDIDA_ESPERADA") ;;
  $DOZE_DO_RESUMO:0)
    parar "gravei a chave e a area administrativa voltou de pe, MAS A CHAVE NAO CHEGOU LA DENTRO: o container leu uma chave vazia. O robo analista do painel continua desligado, e nao adianta abrir a tela dele.

O container renasceu quando eu recarreguei? $RENASCEU.

O arquivo $RAIZ/$ENV_ADMIN esta certo e ha copia do anterior em $RAIZ/$ENV_ADMIN.bak-*. Nao rode nada por conta disso: mande esta tela ao agente." ;;
  $DOZE_DO_RESUMO:[1-9]*)
    parar "gravei a chave e a area administrativa voltou de pe, MAS DENTRO DELA HA UMA CHAVE DIFERENTE da que esta no forum. E o que acontece quando o container nao releu o arquivo: ele continua com a chave de antes, que pode ate ter o mesmo tamanho.

O container renasceu quando eu recarreguei? $RENASCEU.

O arquivo $RAIZ/$ENV_ADMIN esta certo e ha copia do anterior em $RAIZ/$ENV_ADMIN.bak-*. Nao rode nada por conta disso: mande esta tela ao agente." ;;
  *)
    parar "gravei a chave e a area administrativa voltou de pe, mas nao consegui perguntar a ela o que leu, entao nao posso dizer que esta pronto.

O arquivo $RAIZ/$ENV_ADMIN esta certo e ha copia do anterior em $RAIZ/$ENV_ADMIN.bak-*. Nao rode nada por conta disso: mande esta tela ao agente.

O que veio de dentro do container:
    $MEDIDA_LIDA" ;;
esac

echo "== PRONTO =="
echo "A area administrativa esta com a chave da IA, e eu conferi isso DENTRO do"
echo "container: a chave que esta rodando la e exatamente a mesma que esta no"
echo "forum, nao so uma do mesmo tamanho."
echo
echo "E a mesma chave e a mesma conta que o forum ja usa desde 02/09/2026, e o"
echo "que voce paga por ela continua sendo so o uso."
echo
echo "Rodar esta mesma linha de novo e seguro, e e o jeito de a area"
echo "administrativa acompanhar uma troca de chave que voce faca no forum."
