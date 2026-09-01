#!/usr/bin/env bash
# =============================================================================
# A MEDALHA DE FUNDADOR PARA QUEM JA PEDIU ENTRADA NA ESCOLA.
#
# O QUE ELE FAZ, em uma frase: pergunta a parte da plataforma que guarda os
# pedidos de entrada quem sao essas pessoas, e entrega a lista para a parte das
# conquistas, que traduz cada e-mail no numero interno dela e da a medalha.
#
# COMO RODAR (dentro da VPS, uma linha so):
#
#   ENSAIO, que so mostra e nao muda nada:
#     curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/conceder-fundador-aos-alunos.sh -o /tmp/f.sh && bash /tmp/f.sh
#
#   DE VERDADE, depois de olhar a lista do ensaio:
#     bash /tmp/f.sh --confirmo
#
# O PADRAO E OLHAR. Sem a palavra --confirmo nenhuma medalha sai: o script monta
# a lista, mostra na tela agrupada por situacao e para. E essa saida que voce le
# antes de decidir.
#
# RODAR DE NOVO E SEGURO. Ninguem ganha a medalha duas vezes: a parte das
# conquistas tem uma trava no proprio banco que impede a segunda entrega, e os
# 25 Cristais tambem sao creditados uma vez so. Se a lista chegar pela metade
# hoje, rode de novo amanha que o resto entra e quem ja tem fica como esta.
#
# SE NADA FOR RODADO: nada acontece. A medalha continua existindo sem dono,
# ninguem recebe nada, e nenhuma tela do site muda. Este script e a unica porta
# por onde o Fundador sai em bloco, entao esquecer dele nao quebra coisa
# alguma, so deixa as pessoas sem o reconhecimento.
#
# QUEM ENTRA, POR PADRAO: todo mundo que tem um pedido de entrada em qualquer
# situacao, MENOS quem so tem pedido recusado. Quem teve a entrada negada nao
# "estava aqui no comeco", e por isso fica de fora. O ensaio mostra esse grupo
# contado em separado, com nome e e-mail, para voce conferir. Se voce decidir
# que eles tambem entram, acrescente --incluir-recusados:
#
#     bash /tmp/f.sh --incluir-recusados             (ensaio, com eles)
#     bash /tmp/f.sh --incluir-recusados --confirmo  (de verdade, com eles)
#
# A ESCOLHA E SUA. O padrao acima e so o caminho mais provavel, nao uma regra
# da casa.
#
# ELE NAO MUDA CONFIGURACAO NENHUMA. Ele so le, lista e chama os dois comandos.
# Falta uma autorizacao para a parte das conquistas poder perguntar "quem tem
# este e-mail?" a parte que guarda as identidades, e ela e um passo seu, de uma
# linha. Se ela estiver faltando, este script PARA antes de qualquer coisa e te
# entrega essa linha pronta, explicada. Ele nao mexe em segredo por conta
# propria: credencial nao viaja por esteira, e escrever no env de uma celula
# viva e coisa que se faz de olho aberto, nao de passagem.
#
# SE A MEDALHA AINDA ESTIVER DESLIGADA, o comando das conquistas recusa e
# explica: ligar uma medalha e decisao sua, tomada na tela de /admin/economia/,
# e fica registrada com data. Nenhum comando de linha liga economia. Ligue a
# medalha por la e rode este script de novo.
# =============================================================================

# O modo de falha de 24/08 em pessoa: carregado com `source`/`.`, um `exit` daqui
# derrubaria a sessão do mantenedor. Com `bash /tmp/f.sh` o exit morre no filho.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANÇA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessão. Rode com a palavra bash na frente: bash /tmp/f.sh"
  return 1 2>/dev/null || exit 1
fi

set -u

parar() { echo "PAROU POR SEGURANÇA: $1"; exit 1; }

CONFIRMO=0
INCLUIR_RECUSADOS=0
for argumento in "$@"; do
  case "$argumento" in
    --confirmo) CONFIRMO=1 ;;
    --incluir-recusados) INCLUIR_RECUSADOS=1 ;;
    *)
      parar "não conheço a opção '$argumento'. As que existem são --confirmo (concede de verdade) e --incluir-recusados (inclui quem teve o pedido negado). Sem nenhuma delas, o script só mostra a lista. Nada foi feito."
      ;;
  esac
done

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ENV_IDENTIDADE="env/identidade.env"
ENV_GAMIFICACAO="env/gamificacao.env"

# -----------------------------------------------------------------------------
# 1. ONDE — tudo conferido ANTES de listar ou conceder coisa nenhuma.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ. Você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…) Nada foi feito."
[ -f docker-compose.yml ] || parar "não achei $RAIZ/docker-compose.yml. Nada foi feito."
for arquivo in "$ENV_IDENTIDADE" "$ENV_GAMIFICACAO"; do
  [ -f "$arquivo" ] || parar "não achei $RAIZ/$arquivo. Alguma das células não está provisionada nesta máquina. Nada foi feito."
  [ -r "$arquivo" ] || parar "não consigo ler $RAIZ/$arquivo — rode como root ou como o dono dos env. Nada foi feito."
done

ler_de() {  # arquivo, chave — devolve o valor limpo, sem comentário nem espaços
  grep "^$2=" "$1" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | tr -d '[:space:]'
}

SITE="$(ler_de "$ENV_GAMIFICACAO" SITE_ID)"
[ -n "$SITE" ] || parar "não achei SITE_ID em $RAIZ/$ENV_GAMIFICACAO. Sem ele eu não sei de qual escola estou falando, e uma lista da escola errada é pior que lista nenhuma. Rode antes infra/provisionar-gamificacao.sh. Nada foi feito."

# -----------------------------------------------------------------------------
# 2. A AUTORIZAÇÃO QUE FALTA — conferida aqui, e nunca escrita por mim.
#
#    `TOKENS_ACEITOS_*` prova QUEM chama; `TOKENS_COMPLETOS_*` decide se aquele
#    par pode mexer com e-mail. A gamificação nasceu sem o segundo de propósito:
#    ela só precisava do id opaco do dono do cookie, e conceder o que não se usa
#    é superfície de graça. A ponte do Fundador é a primeira coisa que muda isso.
#
#    A conferência compara os VALORES, e não a presença da chave: as duas linhas
#    com valores diferentes dariam 403 na hora de traduzir os e-mails, e o
#    diagnóstico exigiria entrar no servidor para descobrir por quê.
# -----------------------------------------------------------------------------
TOKEN_DO_PAR="$(ler_de "$ENV_IDENTIDADE" TOKENS_ACEITOS_GAMIFICACAO)"
[ -n "$TOKEN_DO_PAR" ] || parar "não achei TOKENS_ACEITOS_GAMIFICACAO em $RAIZ/$ENV_IDENTIDADE. A conversa entre a parte das conquistas e a parte das identidades nunca foi aberta nesta máquina. Rode antes infra/provisionar-gamificacao.sh, que cria esse par. Nada foi feito."

DEGRAU="$(ler_de "$ENV_IDENTIDADE" TOKENS_COMPLETOS_GAMIFICACAO)"
if [ "$DEGRAU" != "$TOKEN_DO_PAR" ]; then
  echo "PAROU POR SEGURANÇA: falta UMA autorização, e ela é um passo seu."
  echo
  echo "O QUE FALTA, em portugues: a parte das conquistas precisa de permissao"
  echo "para perguntar 'quem tem este e-mail?' a parte que guarda as"
  echo "identidades. Ela nunca precisou disso ate hoje, entao a permissao nao"
  echo "existe nesta maquina. Sem ela, a traducao dos e-mails e recusada e"
  echo "nenhuma medalha sai."
  echo
  echo "COLE ESTAS TRES LINHAS AQUI MESMO, nesta janela da VPS (o prompt comeca"
  echo "com deploy@srv... ou root@srv...). Elas nao criam segredo novo: reusam o"
  echo "que o par ja tem, e por isso rodar de novo e inofensivo."
  echo
  echo "  cd $RAIZ"
  echo "  printf '\\nTOKENS_COMPLETOS_GAMIFICACAO=%s\\n' \"\$(grep '^TOKENS_ACEITOS_GAMIFICACAO=' $ENV_IDENTIDADE | cut -d= -f2-)\" >> $ENV_IDENTIDADE"
  echo "  docker compose up -d --force-recreate identidade"
  echo
  echo "ATENCAO ao sinal de maior duplo na linha do meio: >> ACRESCENTA ao fim"
  echo "do arquivo. Um sinal so (>) APAGARIA o arquivo inteiro. Copie a linha"
  echo "como ela esta."
  echo
  echo "Depois disso, rode este script de novo. Nada foi feito agora."
  exit 1
fi

echo "== o que eu vou fazer =="
printf '  %-28s %s\n' "escola" "$SITE"
if [ "$INCLUIR_RECUSADOS" -eq 1 ]; then
  printf '  %-28s %s\n' "quem entra" "todo mundo, INCLUSIVE quem teve o pedido negado"
  EXCETO=""
else
  printf '  %-28s %s\n' "quem entra" "todo mundo, menos quem so tem pedido negado"
  EXCETO="recusada"
fi
if [ "$CONFIRMO" -eq 1 ]; then
  printf '  %-28s %s\n' "modo" "CONCEDER DE VERDADE"
else
  printf '  %-28s %s\n' "modo" "ENSAIO (nada sera concedido)"
fi
printf '  %-28s %s\n' "autorizacao do e-mail" "confere nos dois lados"
echo

# -----------------------------------------------------------------------------
# 3. A LISTA — quem pediu entrada, na voz da célula que sabe.
#
#    Duas leituras do MESMO comando: uma para você ler, outra para a máquina
#    consumir. Um comando com dois formatos, e não dois comandos: dois comandos
#    seriam duas consultas que um dia discordariam sobre quem está na lista, e a
#    divergência apareceria como gente recebendo o que não devia.
#
#    O VEREDITO VEM DO COMANDO, NUNCA DO PIPE. `… | tail -5` pergunta o estado
#    do `tail`, que dá 0 quase sempre, e o ramo de erro viraria código morto: o
#    script seguiria com uma lista vazia achando que perguntou. É o falso-verde
#    do ARMADILHAS §5.10, o mesmo que fez os greens do deploy-celula mentirem
#    até 21/08/2026.
# -----------------------------------------------------------------------------
listar() {  # os argumentos extras do comando da célula alunos
  if [ -n "$EXCETO" ]; then
    docker compose exec -T alunos python manage.py listar_pedidos_de_entrada \
      --site "$SITE" --exceto "$EXCETO" "$@" 2>&1
  else
    docker compose exec -T alunos python manage.py listar_pedidos_de_entrada \
      --site "$SITE" "$@" 2>&1
  fi
}

echo "== quem pediu entrada nesta escola =="
panorama="$(listar)"
estado_do_panorama=$?
printf '%s\n' "$panorama"
[ "$estado_do_panorama" -eq 0 ] || parar "nao consegui ler a lista de quem pediu entrada (a saida crua esta logo acima). Nenhuma medalha foi concedida."
echo

lista="$(listar --formato emails)"
estado_da_lista=$?
[ "$estado_da_lista" -eq 0 ] || { printf '%s\n' "$lista"; parar "nao consegui montar a lista de e-mails (a saida crua esta logo acima). Nenhuma medalha foi concedida."; }

# O `tr -d` do retorno de carro existe porque a saída atravessa o
# `docker compose exec`: uma quebra de linha no formato do Windows viraria parte
# do último e-mail, em silêncio. O `grep '@'` descarta qualquer linha que não
# seja um endereço, que é a segunda rede da mesma preocupação.
EMAILS="$(printf '%s' "$lista" | tr -d '\r' | grep '@' | paste -sd, -)"
QUANTOS="$(printf '%s' "$lista" | tr -d '\r' | grep -c '@')"

if [ -z "$EMAILS" ]; then
  echo "Ninguem na lista: esta escola nao tem nenhum pedido de entrada que se encaixe."
  echo "Se voce esperava gente aqui, confira se a escola e mesmo esta: $SITE"
  echo "(esse numero sai de SITE_ID em $RAIZ/$ENV_GAMIFICACAO)"
  echo
  echo "PRONTO. Nada foi concedido, e nada mudou no site."
  exit 0
fi
echo "Sao $QUANTOS pessoa(s) na lista de quem receberia a medalha."
echo

# -----------------------------------------------------------------------------
# 4. A MEDALHA — o comando das conquistas, que é quem decide e quem escreve.
#
#    Ele traduz cada e-mail no id opaco pela célula `identidade` ANTES de
#    conceder qualquer coisa. Se aquela conversa falhar no meio, ele para e não
#    concede nada a ninguém: "não consegui perguntar" nunca vira "esta pessoa
#    não existe". E-mail que a identidade simplesmente não conhece é outro caso,
#    e esse entra no relatório sem parar o resto da lista.
# -----------------------------------------------------------------------------
if [ "$CONFIRMO" -eq 1 ]; then
  echo "== concedendo a medalha =="
  saida_da_concessao="$(docker compose exec -T gamificacao python manage.py conceder_fundador --site "$SITE" --emails "$EMAILS" --confirmo 2>&1)"
else
  echo "== ENSAIO: mostrando quem receberia, sem conceder nada =="
  saida_da_concessao="$(docker compose exec -T gamificacao python manage.py conceder_fundador --site "$SITE" --emails "$EMAILS" 2>&1)"
fi
estado_da_concessao=$?
printf '%s\n' "$saida_da_concessao"
echo

if [ "$estado_da_concessao" -ne 0 ]; then
  echo "O comando das conquistas RECUSOU, e o motivo esta escrito logo acima."
  echo "Nenhuma medalha foi concedida. Rodar de novo depois de resolver e seguro."
  exit 1
fi

if [ "$CONFIRMO" -eq 1 ]; then
  echo "PRONTO. As medalhas acima foram concedidas, com os 25 Cristais e a carta"
  echo "que avisa cada pessoa. Rodar este script de novo nao concede duas vezes."
else
  echo "ENSAIO TERMINADO. Nada foi concedido e nada mudou no site."
  echo "Se a lista acima estiver certa, rode a mesma linha com --confirmo no fim:"
  if [ "$INCLUIR_RECUSADOS" -eq 1 ]; then
    echo "  bash /tmp/f.sh --incluir-recusados --confirmo"
  else
    echo "  bash /tmp/f.sh --confirmo"
  fi
fi
