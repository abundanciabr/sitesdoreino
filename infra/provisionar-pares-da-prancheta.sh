#!/usr/bin/env bash
# =============================================================================
# DEIXAR A PRANCHETA PRONTA, o passo do mantenedor, numa linha só.
#
# A Prancheta do aluno (`/pages`, degrau 06 de PLANO-PORTFOLIO-DO-ALUNO.md)
# pergunta à `identidade` QUEM é a pessoa (com e-mail), pergunta à `alunos` se
# ela TEM MATRÍCULA ATIVA e pergunta ao `catalogo` QUAL É O MENU do topo do
# site. São três pares consumidor->provedor, e os três já existem no CÓDIGO
# (`services/pages/apps/core/clients.py` e `.../menu.py`). Além deles, a célula
# precisa saber DE QUE ESCOLA esta instalação é, para gravar a marcação do aluno
# no lado certo da fronteira (`SITE_ID`, lido por `.../views.py`). O que falta
# em todos os casos é a metade da VPS: credencial não viaja por esteira (INV-P8,
# Lei 5), e o `deploy-infra.yml` diz de si mesmo que JAMAIS toca `infra/env/`.
# Por isso este passo é seu, e por isso este arquivo existe: para ser UMA linha.
#
# COMO RODAR (dentro da VPS, uma linha só):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-pares-da-prancheta.sh -o /tmp/s.sh && bash /tmp/s.sh
#
# O NOME DO ARQUIVO FICOU MAIS ESTREITO QUE O CONTEÚDO, e ele fica assim de
# propósito: o endereço acima já está escrito no rodapé de
# `infra/provisionar-pages.sh` e na lei da identidade, e renomear um roteiro que
# o mantenedor ainda vai colar troca uma imprecisão de nome por um link morto na
# tela dele.
#
# O argumento do host é OPCIONAL e só serve para desempatar: com um site ativo
# no catálogo ele é dispensável, e com mais de um este roteiro PARA, lista os
# que achou e imprime a linha pronta com o host no fim (`bash /tmp/s.sh
# meshcraft.top`). "O primeiro da lista" seria o chute que amarra o portfólio de
# todo mundo à escola errada.
#
# ANTES DELE, A LINHA DO BANCO (`infra/provisionar-pages.sh`, degrau 04). É ela
# quem cria `env/pages.env`, e este script se RECUSA a criá-lo: aquele roteiro
# reescreve o env inteiro e PARA ao achar chave que não sabe gerar (a trava de
# deriva, `armadilhas/111`). Um env criado aqui, antes dele, o trancaria para
# sempre. Faltando o arquivo, a recusa abaixo traz a linha certa.
#
# O QUE ACONTECE HOJE, ANTES DELE, e são três sintomas de três ausências:
#
#   1. `meshcraft.top/pages/` responde 503 com "Não conseguimos conferir o seu
#      acesso agora" para TODO MUNDO, inclusive para aluno com matrícula ativa.
#      Isso NÃO é defeito: a porta é fail-closed por construção e, sem conseguir
#      perguntar quem é a pessoa, ela fecha em vez de abrir.
#   2. A barra de menu do topo aparece VAZIA nas Páginas do aluno: sem o par com
#      o catálogo, o motor do menu devolve lista vazia sem sequer tentar a rede
#      (medido em 06/09/2026: `/forum/` traz "Início", "Cadastro" e "Avisos da
#      escola"; `/pages/` traz o estilo da barra e nenhum item dentro dela).
#   3. A Prancheta mostra o roteiro inteiro mas RECUSA a marcação do aluno com
#      503, porque sem `SITE_ID` ela não sabe de que escola esta instalação é.
#      Também de propósito: gravar com o site em branco poria os alunos de duas
#      escolas do mesmo lado da fronteira no dia em que a segunda chegasse, e
#      nenhuma tela quebraria para avisar.
#
# NÃO PEDE NADA e NÃO PERGUNTA NADA A VOCÊ. Os segredos que faltam são gerados
# AQUI, dentro da VPS, e gravados direto nos arquivos: nenhum aparece na tela,
# nenhum passa por agente, nenhum entra no Git (`armadilhas/090`). A única
# pergunta que ele faz, ele faz ao CATÁLOGO, que é quem sabe o número do site.
#
# É IDEMPOTENTE E NÃO ROTACIONA. Um par que já existe é REUSADO, nunca
# regerado: trocar um token em uso derrubaria as chamadas até o container do
# outro lado reiniciar, e o sintoma seria 401 intermitente. Rodar de novo é
# seguro e é a cura de qualquer dúvida.
#
# O QUE ELE LIGA (a ordem é deliberada: PROVEDOR PRIMEIRO):
#
#   1. env/identidade.env  TOKENS_ACEITOS_PAGES   (quem pode perguntar)
#                          TOKENS_COMPLETOS_PAGES (o MESMO valor: o degrau que
#                          libera o e-mail, registrado por escrito em
#                          DECISAO-celula-de-identidade.md §6.3, item `pages`.
#                          Valores diferentes dariam 403 na resposta completa,
#                          a Prancheta não teria o e-mail para perguntar à
#                          `alunos`, e ela fecharia para todo mundo em silêncio)
#   2. env/alunos.env      TOKENS_ACEITOS_PAGES
#   3. env/catalogo.env    TOKENS_ACEITOS_PAGES (o menu do topo do site)
#   4. env/pages.env       IDENTIDADE_API_URL/_TOKEN, ALUNOS_API_URL/_TOKEN,
#                          CATALOGO_API_URL/TOKEN_CATALOGO, e SITE_ID
#
# Os nomes vêm do código que os lê (`services/pages/apps/core/clients.py`,
# `.../menu.py` e `.../views.py`), nunca de memória. Repare que o token do menu
# se chama `TOKEN_CATALOGO`, sem o sufixo `_API_`: é o nome que os outros quatro
# consumidores do catálogo já usam, e aqui vale a convenção que existe.
#
# Os endereços saem do `servers:` de cada contrato congelado
# (`contracts/identidade.openapi.yaml`, `contracts/alunos.openapi.yaml`,
# `contracts/catalogo.openapi.yaml`).
#
# Três pares, três tokens DISTINTOS: token é por par. Um só nos três lados faria
# a rotação de um derrubar os outros, sem aviso. O script confere isso ANTES de
# escrever e se recusa a gravar dois pares com o mesmo valor.
#
# O QUE ACONTECE SE OUTRO ROTEIRO RODAR DEPOIS DESTE: `provisionar-pages.sh`
# reescreve o env dele do ZERO, e desde 06/09/2026 ele CONHECE as sete chaves
# daqui: relê o token de cada provedor, repergunta o site ao catálogo, e regrava
# tudo igual em vez de apagar.
# Rodar aquele depois deste é seguro. Já `provisionar-identidade.sh` NÃO conhece
# as duas chaves que este script escreve no env da identidade, e por isso vai
# PARAR com "PAROU POR SEGURANÇA" listando o que sobrou. É o comportamento
# certo: ele não apaga nada em silêncio. Se acontecer, mande a tela ao agente.
#
# SE NADA FOR RODADO: a Prancheta continua respondendo 503 para todo mundo, o
# menu do topo continua vazio nas Páginas do aluno e a marcação continua
# recusada. Nada quebra e nada mais muda no ar.
# =============================================================================

# O modo de falha de 24/08 em pessoa: carregado com `source`/`.`, um `exit` daqui
# derrubaria a sessão do mantenedor. Com `bash /tmp/s.sh` o exit morre no filho.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANÇA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessão. Rode com a palavra bash na frente: bash /tmp/s.sh"
  return 1 2>/dev/null || exit 1
fi

set -u

parar() { echo "PAROU POR SEGURANÇA: $1"; exit 1; }

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ENV_PAGES="env/pages.env"
ENV_IDENTIDADE="env/identidade.env"
ENV_ALUNOS="env/alunos.env"
ENV_CATALOGO="env/catalogo.env"
# A referência de dono/permissão: um env que JÁ funciona nesta máquina.
ENV_REF="$ENV_IDENTIDADE"

# Os endereços internos saem do `servers:` dos contratos congelados
# (`contracts/<celula>.openapi.yaml`), e não são escolha deste script.
IDENTIDADE_URL="http://identidade:8000/interno"
ALUNOS_URL="http://alunos:8000/api/alunos"
CATALOGO_URL="http://catalogo:8000/api/catalogo"

LINHA_DO_BANCO="curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-pages.sh -o /tmp/p.sh && bash /tmp/p.sh"

# -----------------------------------------------------------------------------
# 1. ONDE: a pasta da plataforma e os quatro arquivos de que dependo.
#    Tudo conferido ANTES de gerar ou escrever coisa nenhuma.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ. Você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…, nunca PS C:\\>)"

if [ ! -f "$ENV_PAGES" ]; then
  echo "PAROU POR SEGURANÇA: não achei $RAIZ/$ENV_PAGES."
  echo
  echo "O env das Páginas do aluno nasce junto com o banco delas, e essa linha"
  echo "ainda não rodou nesta máquina. Eu NÃO crio esse arquivo: quem o cria é a"
  echo "linha do banco, e um arquivo criado aqui antes dela a travaria para"
  echo "sempre."
  echo
  echo "Cole PRIMEIRO esta linha, aqui mesmo, e depois a minha de novo:"
  echo
  echo "  $LINHA_DO_BANCO"
  echo
  echo "Nada foi criado, nada foi alterado."
  exit 1
fi
for arquivo in "$ENV_IDENTIDADE" "$ENV_ALUNOS" "$ENV_CATALOGO" "$ENV_PAGES"; do
  [ -f "$arquivo" ] || parar "não achei $RAIZ/$arquivo. A Prancheta precisa conversar com essa célula, e ela não está provisionada aqui. Nada foi criado, nada foi alterado."
  [ -w "$arquivo" ] || parar "não consigo escrever em $RAIZ/$arquivo. Rode como root ou como o dono dos env. Nada foi alterado."
done

ler_de() {  # arquivo, chave: devolve o valor limpo, sem comentário nem espaços
  grep "^$2=" "$1" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | tr -d '[:space:]'
}

gerar_segredo() {
  # `openssl` primeiro; `/dev/urandom` como caminho alternativo MEDIDO, nunca
  # silencioso. Se nenhum dos dois existir, o script para em vez de gravar um
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
# 2. OS VALORES: reusados se já existem, gerados só se faltam.
#    Quem manda é sempre o PROVEDOR: o valor vem da lista de aceitos dele, e o
#    consumidor é realinhado a ela. A direção importa: alinhar pelo consumidor
#    deixaria uma célula qualquer mudar o que o provedor aceita.
# -----------------------------------------------------------------------------
T_IDENTIDADE="$(ler_de "$ENV_IDENTIDADE" TOKENS_ACEITOS_PAGES)"
T_ALUNOS="$(ler_de "$ENV_ALUNOS" TOKENS_ACEITOS_PAGES)"
T_CATALOGO="$(ler_de "$ENV_CATALOGO" TOKENS_ACEITOS_PAGES)"
NOVOS=0
if [ -z "$T_IDENTIDADE" ]; then
  T_IDENTIDADE="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
  NOVOS=$((NOVOS + 1))
fi
if [ -z "$T_ALUNOS" ]; then
  T_ALUNOS="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
  NOVOS=$((NOVOS + 1))
fi
if [ -z "$T_CATALOGO" ]; then
  T_CATALOGO="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
  NOVOS=$((NOVOS + 1))
fi
[ ${#T_IDENTIDADE} -ge 32 ] || parar "o token do par pages->identidade ficou curto demais. Nada foi alterado."
[ ${#T_ALUNOS} -ge 32 ] || parar "o token do par pages->alunos ficou curto demais. Nada foi alterado."
[ ${#T_CATALOGO} -ge 32 ] || parar "o token do par pages->catalogo ficou curto demais. Nada foi alterado."

# TRÊS tokens, TRÊS valores distintos, conferido ANTES de escrever. A conta é de
# valores únicos em vez de comparação par a par: com três pares seriam três
# comparações escritas à mão, e o quarto par que chegasse entraria com seis, uma
# delas esquecida, e o guarda passaria verde justo no caso que ele existe para
# pegar.
DISTINTOS="$(printf '%s\n%s\n%s\n' "$T_IDENTIDADE" "$T_ALUNOS" "$T_CATALOGO" | sort -u | wc -l | tr -d '[:space:]')"
[ "$DISTINTOS" = "3" ] || parar "dois pares desta casa estão com o MESMO token nos env desta máquina. Token é por par, e um só faria a rotação de um derrubar o outro sem aviso. Nada foi alterado. Me mande esta tela inteira."

# -----------------------------------------------------------------------------
# 2b. O SITE, perguntado ao catálogo, e este roteiro NÃO TERMINA sem ele.
#     Vem ANTES de escrever qualquer coisa, de propósito: recusar aqui significa
#     que nada foi alterado e não há meia-instalação para desfazer.
#
#     A regra do host é a MESMA de `infra/provisionar-cursos.sh`: com argumento,
#     usa o pedido e PARA se ele não existir; sem argumento, só segue se houver
#     exatamente UM site ativo.
# -----------------------------------------------------------------------------
command -v docker >/dev/null 2>&1 || parar "não achei o docker nesta máquina, e é pelo catálogo que eu descubro de que escola esta instalação é. Você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…, nunca PS C:\\>). Nada foi alterado."
ESTADO=$(docker compose ps --status running --services 2>/dev/null | grep -Fx "catalogo" || true)
[ -n "$ESTADO" ] || parar "o serviço 'catalogo' não está rodando, e é ele quem sabe o número do site. Suba a plataforma (cd $RAIZ && docker compose up -d) e cole a minha linha de novo. Nada foi alterado."

# A resposta CRUA primeiro, e o filtro depois, em dois passos de propósito: num
# pipe único, "o catálogo não respondeu" e "o catálogo respondeu que não há site
# ativo" chegariam aqui como o MESMO exit 1 (quem falha é o `grep`), e o
# mantenedor leria "não consegui perguntar" quando o problema é outro
# (`armadilhas/240`). Duas causas diferentes precisam de duas telas diferentes.
BRUTO=$(docker compose exec -T catalogo python manage.py shell -c \
  "from apps.sites.models import Site
for s in Site.objects.filter(active=True).order_by('host'):
    print(f'{s.id}\t{s.host}')" 2>/dev/null) \
  || parar "não consegui perguntar ao catálogo quais sites existem. Nada foi alterado."

SITES=$(printf '%s\n' "$BRUTO" | tr -d '\r' | grep -E '^[0-9a-fA-F-]{36}\s' || true)
QUANTOS=$(printf '%s\n' "$SITES" | grep -c . || true)
[ "${QUANTOS:-0}" -ge 1 ] || parar "o catálogo não tem NENHUM site ativo. Sem site não há a que escola amarrar o portfólio do aluno. Nada foi alterado."

listar_sites() {
  printf '%s\n' "$SITES" | while IFS="$(printf '\t')" read -r ID HOST; do
    echo "     - $HOST  ($ID)"
  done
}

HOST_PEDIDO="${1:-}"
if [ -n "$HOST_PEDIDO" ]; then
  LINHA=$(printf '%s\n' "$SITES" | awk -F"\t" -v h="$HOST_PEDIDO" '$2==h {print; exit}')
  if [ -z "$LINHA" ]; then
    echo "  O site '$HOST_PEDIDO' não está entre os ativos do catálogo. Os que estão:"
    listar_sites
    parar "host pedido não encontrado. Confira a grafia (sem https://, sem barra no fim). Nada foi alterado."
  fi
  SITE_ID=$(printf '%s' "$LINHA" | cut -f1)
  SITE_HOST=$(printf '%s' "$LINHA" | cut -f2)
elif [ "$QUANTOS" -gt 1 ]; then
  echo "  Achei mais de um site ativo:"
  listar_sites
  echo
  echo "  Cole esta linha de novo, com o endereço da escola no fim:"
  echo "     bash /tmp/s.sh meshcraft.top"
  parar "há $QUANTOS sites ativos e eu não escolho por você. Nada foi alterado."
else
  SITE_ID=$(printf '%s\n' "$SITES" | head -n1 | cut -f1)
  SITE_HOST=$(printf '%s\n' "$SITES" | head -n1 | cut -f2)
fi

# A recusa final: se chegamos aqui com o campo vazio, alguma leitura acima
# falhou de um jeito que eu não previ, e gravar assim seria pior do que parar.
[ -n "${SITE_ID:-}" ] || parar "li a resposta do catálogo mas não consegui extrair o número do site. Sem SITE_ID a Prancheta recusa toda marcação do aluno, então eu não gravo nada. Nada foi alterado."

echo "== estado ANTES =="
printf '  %-22s %s\n' "$ENV_IDENTIDADE" "encontrado ($(wc -l < "$ENV_IDENTIDADE") linhas)"
printf '  %-22s %s\n' "$ENV_ALUNOS" "encontrado ($(wc -l < "$ENV_ALUNOS") linhas)"
printf '  %-22s %s\n' "$ENV_CATALOGO" "encontrado ($(wc -l < "$ENV_CATALOGO") linhas)"
printf '  %-22s %s\n' "$ENV_PAGES" "encontrado ($(wc -l < "$ENV_PAGES") linhas)"
printf '  %-22s %s\n' "escola" "${SITE_HOST:-?} ($SITE_ID)"
if [ "$NOVOS" -eq 0 ]; then
  echo "  segredos ............... os três pares JÁ existiam; vou reusar, não regerar"
else
  echo "  segredos ............... vou gerar $NOVOS (os outros, se houver, são reusados)"
fi
echo

# -----------------------------------------------------------------------------
# 3. ESCRITA: uma chave por vez, com cópia de segurança por arquivo.
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
    # chave nova no fim da última linha, e a última linha de um env é um valor.
    if [ -s "$arq" ] && [ "$(tail -c 1 "$arq" | wc -l)" -eq 0 ]; then
      printf '\n' >> "$arq" || parar "não consegui escrever em $arq. As cópias intactas estão em $RAIZ ($BACKUPS)."
    fi
    grep -q "^# $cabecalho" "$arq" || printf '\n# %s\n# Escrito por infra/provisionar-pares-da-prancheta.sh (PLANO-PORTFOLIO-DO-ALUNO, degrau 06).\n' "$cabecalho" >> "$arq"
    printf '%s=%s\n' "$chave" "$valor" >> "$arq" \
      || parar "não consegui escrever em $arq. As cópias intactas estão em $RAIZ ($BACKUPS)."
  fi

  # DONO E MODO copiados de um env que JÁ FUNCIONA, nunca escolhidos por mim
  # (`armadilhas/091`): rodando como root, o `sed -i` recria o arquivo e pode
  # deixá-lo root:root, e o usuário `deploy`, que é quem o pipeline usa, não lê
  # um 600 de root.
  if [ "$(stat -c '%U:%G %a' "$arq" 2>/dev/null)" != "$(stat -c '%U:%G %a' "$ENV_REF" 2>/dev/null)" ]; then
    chown --reference="$ENV_REF" "$arq" 2>/dev/null \
      || parar "não consegui ajustar o dono de $arq. Rode como root ou como o dono dos env. As cópias intactas estão em $RAIZ ($BACKUPS)."
    chmod --reference="$ENV_REF" "$arq" 2>/dev/null \
      || parar "não consegui ajustar as permissões de $arq. Rode como root. As cópias intactas estão em $RAIZ ($BACKUPS)."
  fi

  case "$MEXIDOS" in *" $arq"*) : ;; *) MEXIDOS="$MEXIDOS $arq" ;; esac
}

# PROVEDOR PRIMEIRO (ver o cabeçalho deste arquivo).
garantir "$ENV_IDENTIDADE" TOKENS_ACEITOS_PAGES "$T_IDENTIDADE" "par pages->identidade: a Prancheta pergunta quem e a pessoa"
garantir "$ENV_IDENTIDADE" TOKENS_COMPLETOS_PAGES "$T_IDENTIDADE" "degrau de e-mail da Prancheta (DECISAO-celula-de-identidade §6.3, item pages): o MESMO token de TOKENS_ACEITOS_PAGES"
garantir "$ENV_ALUNOS" TOKENS_ACEITOS_PAGES "$T_ALUNOS" "par pages->alunos: a Prancheta pergunta se a pessoa tem matricula ativa"
garantir "$ENV_CATALOGO" TOKENS_ACEITOS_PAGES "$T_CATALOGO" "par pages->catalogo: as Paginas do aluno mostram o mesmo menu do site"
# E só então o consumidor.
garantir "$ENV_PAGES" IDENTIDADE_API_URL "$IDENTIDADE_URL" "par pages->identidade"
garantir "$ENV_PAGES" IDENTIDADE_API_TOKEN "$T_IDENTIDADE" "par pages->identidade"
garantir "$ENV_PAGES" ALUNOS_API_URL "$ALUNOS_URL" "par pages->alunos"
garantir "$ENV_PAGES" ALUNOS_API_TOKEN "$T_ALUNOS" "par pages->alunos"
garantir "$ENV_PAGES" CATALOGO_API_URL "$CATALOGO_URL" "par pages->catalogo"
garantir "$ENV_PAGES" TOKEN_CATALOGO "$T_CATALOGO" "par pages->catalogo"
# E, por fim, o que não é par nenhum: de que escola esta instalacao e. Sem esta
# linha a Prancheta mostra o roteiro e RECUSA a marcacao do aluno com 503.
garantir "$ENV_PAGES" SITE_ID "$SITE_ID" "de que escola esta instalacao e (perguntado ao catalogo)"

# -----------------------------------------------------------------------------
# 4. ESTADO DEPOIS: a conferência que fecha o assunto. Compara SEM imprimir
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
    parar "o par '$1' NÃO ficou igual nos dois lados ($3/$4 e $5/$6). Isso daria 401 silencioso. As cópias intactas estão em $RAIZ ($BACKUPS). Me mande esta tela inteira."
  fi
}
conferir_par "par pages->identidade" "$T_IDENTIDADE" "$ENV_IDENTIDADE" TOKENS_ACEITOS_PAGES "$ENV_PAGES" IDENTIDADE_API_TOKEN
conferir_par "e-mail para a Prancheta" "$T_IDENTIDADE" "$ENV_IDENTIDADE" TOKENS_ACEITOS_PAGES "$ENV_IDENTIDADE" TOKENS_COMPLETOS_PAGES
conferir_par "par pages->alunos" "$T_ALUNOS" "$ENV_ALUNOS" TOKENS_ACEITOS_PAGES "$ENV_PAGES" ALUNOS_API_TOKEN
conferir_par "par pages->catalogo" "$T_CATALOGO" "$ENV_CATALOGO" TOKENS_ACEITOS_PAGES "$ENV_PAGES" TOKEN_CATALOGO

conferir_endereco() {  # arquivo, chave, valor-esperado
  [ "$(ler_de "$1" "$2")" = "$3" ] || parar "$2 não ficou como esperado em $1. As cópias intactas estão em $RAIZ ($BACKUPS). Me mande esta tela inteira."
}
conferir_endereco "$ENV_PAGES" IDENTIDADE_API_URL "$IDENTIDADE_URL"
conferir_endereco "$ENV_PAGES" ALUNOS_API_URL "$ALUNOS_URL"
conferir_endereco "$ENV_PAGES" CATALOGO_API_URL "$CATALOGO_URL"
echo "  endereços .............. os três são os dos contratos congelados"

# O SITE_ID gravado tem de ser o MESMO que o catálogo respondeu. Sem esta
# conferência, uma linha `SITE_ID=` antiga e vazia no arquivo passaria despercebida
# e a Prancheta continuaria recusando a marcação com a tela dizendo PRONTO.
conferir_endereco "$ENV_PAGES" SITE_ID "$SITE_ID"
echo "  escola ................. ${SITE_HOST:-?}, gravada como o catálogo respondeu"

# Chave repetida é o modo de falha mais traiçoeiro de um env: o Docker Compose
# usa a ÚLTIMA, e um valor velho ficaria por baixo sem nada acusar.
for par in "$ENV_IDENTIDADE:TOKENS_ACEITOS_PAGES" "$ENV_IDENTIDADE:TOKENS_COMPLETOS_PAGES" \
           "$ENV_ALUNOS:TOKENS_ACEITOS_PAGES" "$ENV_CATALOGO:TOKENS_ACEITOS_PAGES" \
           "$ENV_PAGES:IDENTIDADE_API_URL" "$ENV_PAGES:IDENTIDADE_API_TOKEN" \
           "$ENV_PAGES:ALUNOS_API_URL" "$ENV_PAGES:ALUNOS_API_TOKEN" \
           "$ENV_PAGES:CATALOGO_API_URL" "$ENV_PAGES:TOKEN_CATALOGO" \
           "$ENV_PAGES:SITE_ID"; do
  arq="${par%%:*}"; chave="${par##*:}"
  n="$(grep -c "^$chave=" "$arq")"
  [ "$n" -eq 1 ] || parar "a chave $chave aparece $n vezes em $arq, e o Docker Compose usaria só a última. As cópias intactas estão em $RAIZ ($BACKUPS). Me mande esta tela inteira."
done
echo "  chaves repetidas ....... nenhuma (conferido nas 11)"
echo

# -----------------------------------------------------------------------------
# 5. RECARREGAR: as células precisam reler o env para as chaves valerem.
#    JAMAIS `docker compose up -d` sem argumento: isso devolveria TODAS as
#    células à tag :main do compose (RITOS §4). Só estes serviços, pelo nome.
# -----------------------------------------------------------------------------
#    Aqui não há mais `command -v docker`: o passo 2b já parou o roteiro se o
#    docker não existisse, e um segundo teste do mesmo fato seria ramo morto.
echo "== recarregando as células para elas relerem o env =="
ALVOS=""
# Ordem: provedores, depois quem pergunta.
for servico in identidade alunos catalogo pages; do
  docker compose config --services 2>/dev/null | grep -qx "$servico" && ALVOS="$ALVOS $servico"
done
if [ -n "$ALVOS" ]; then
  if docker compose up -d $ALVOS >/dev/null 2>&1; then
    echo "  recarreguei:$ALVOS"
  else
    echo "  (aviso: não consegui recarregar$ALVOS. Os arquivos JÁ estão certos; o próximo deploy de cada célula relê o env. Avise o agente.)"
  fi
  case " $ALVOS " in
    *" pages "*) : ;;
    *) echo "  (a Prancheta ainda não está no compose desta máquina; quando entrar, nasce lendo o env já pronto)" ;;
  esac
else
  echo "  (aviso: não achei estes serviços no compose desta máquina. O próximo deploy relê o env.)"
fi
echo

echo "A partir de agora a Prancheta sabe QUEM entrou, se a pessoa tem matrícula"
echo "ativa e de que escola esta instalação é, e o menu do topo aparece nas"
echo "Páginas do aluno. Rodar esta mesma linha de novo é seguro: os segredos que"
echo "já existem são reusados, nunca trocados."
echo
echo "PRONTO: a Prancheta está completa. Copie esta tela inteira e mande para o robô."
