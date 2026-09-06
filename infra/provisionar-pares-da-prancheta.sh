#!/usr/bin/env bash
# =============================================================================
# LIGAR AS DUAS CONVERSAS DA PRANCHETA, o passo do mantenedor.
#
# A Prancheta do aluno (`/pages`, degrau 06 de PLANO-PORTFOLIO-DO-ALUNO.md)
# pergunta à `identidade` QUEM é a pessoa (com e-mail) e pergunta à `alunos` se
# ela TEM MATRÍCULA ATIVA. São dois pares consumidor->provedor, e os dois já
# existem no CÓDIGO (`services/pages/apps/core/clients.py`). O que falta é a
# metade da VPS: credencial não viaja por esteira (INV-P8, Lei 5), e o
# `deploy-infra.yml` diz de si mesmo que JAMAIS toca `infra/env/`. Por isso
# este passo é seu, e por isso este arquivo existe: para ser UMA linha.
#
# COMO RODAR (dentro da VPS, uma linha só, SEM argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-pares-da-prancheta.sh -o /tmp/s.sh && bash /tmp/s.sh
#
# ANTES DELE, A LINHA DO BANCO (`infra/provisionar-pages.sh`, degrau 04). É ela
# quem cria `env/pages.env`, e este script se RECUSA a criá-lo: aquele roteiro
# reescreve o env inteiro e PARA ao achar chave que não sabe gerar (a trava de
# deriva, `armadilhas/111`). Um env criado aqui, antes dele, o trancaria para
# sempre. Faltando o arquivo, a recusa abaixo traz a linha certa.
#
# O QUE ACONTECE HOJE, ANTES DELE: `meshcraft.top/pages/` responde 503 com
# "Não conseguimos conferir o seu acesso agora" para TODO MUNDO, inclusive para
# aluno com matrícula ativa. Isso NÃO é defeito: a porta é fail-closed por
# construção e, sem conseguir perguntar quem é a pessoa, ela fecha em vez de
# abrir. É a ausência destes dois pares, e é isto aqui que a cura.
#
# NÃO PERGUNTA NADA e NÃO PEDE NADA. Os segredos que faltam são gerados AQUI,
# dentro da VPS, e gravados direto nos arquivos: nenhum aparece na tela, nenhum
# passa por agente, nenhum entra no Git (`armadilhas/090`).
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
#   3. env/pages.env       IDENTIDADE_API_URL/_TOKEN, ALUNOS_API_URL/_TOKEN
#
# Os nomes vêm do código que os lê (`services/pages/apps/core/clients.py`),
# nunca de memória. Os endereços saem do `servers:` de cada contrato congelado
# (`contracts/identidade.openapi.yaml`, `contracts/alunos.openapi.yaml`).
#
# Dois pares, dois tokens DISTINTOS: token é por par. Um só nos dois lados
# faria a rotação de um derrubar o outro, sem aviso. O script confere isso
# ANTES de escrever e se recusa a gravar dois pares com o mesmo valor.
#
# O QUE ACONTECE SE OUTRO ROTEIRO RODAR DEPOIS DESTE: `provisionar-pages.sh`
# reescreve o env dele do ZERO, e desde 06/09/2026 ele CONHECE as quatro chaves
# daqui: relê o token de cada provedor e o regrava igual, em vez de apagá-lo.
# Rodar aquele depois deste é seguro. Já `provisionar-identidade.sh` NÃO conhece
# as duas chaves que este script escreve no env da identidade, e por isso vai
# PARAR com "PAROU POR SEGURANÇA" listando o que sobrou. É o comportamento
# certo: ele não apaga nada em silêncio. Se acontecer, mande a tela ao agente.
#
# SE NADA FOR RODADO: a Prancheta continua respondendo 503 para todo mundo.
# Nada quebra e nada mais muda no ar.
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
# A referência de dono/permissão: um env que JÁ funciona nesta máquina.
ENV_REF="$ENV_IDENTIDADE"

# Os endereços internos saem do `servers:` dos contratos congelados
# (`contracts/<celula>.openapi.yaml`), e não são escolha deste script.
IDENTIDADE_URL="http://identidade:8000/interno"
ALUNOS_URL="http://alunos:8000/api/alunos"

LINHA_DO_BANCO="curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-pages.sh -o /tmp/p.sh && bash /tmp/p.sh"

# -----------------------------------------------------------------------------
# 1. ONDE: a pasta da plataforma e os três arquivos de que dependo.
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
for arquivo in "$ENV_IDENTIDADE" "$ENV_ALUNOS" "$ENV_PAGES"; do
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
NOVOS=0
if [ -z "$T_IDENTIDADE" ]; then
  T_IDENTIDADE="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
  NOVOS=$((NOVOS + 1))
fi
if [ -z "$T_ALUNOS" ]; then
  T_ALUNOS="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
  NOVOS=$((NOVOS + 1))
fi
[ ${#T_IDENTIDADE} -ge 32 ] || parar "o token do par pages->identidade ficou curto demais. Nada foi alterado."
[ ${#T_ALUNOS} -ge 32 ] || parar "o token do par pages->alunos ficou curto demais. Nada foi alterado."

# DOIS tokens, DOIS valores distintos, conferido ANTES de escrever.
DISTINTOS="$(printf '%s\n%s\n' "$T_IDENTIDADE" "$T_ALUNOS" | sort -u | wc -l | tr -d '[:space:]')"
[ "$DISTINTOS" = "2" ] || parar "os dois pares da Prancheta estão com o MESMO token nos env desta máquina. Token é por par, e um só faria a rotação de um derrubar o outro sem aviso. Nada foi alterado. Me mande esta tela inteira."

echo "== estado ANTES =="
printf '  %-22s %s\n' "$ENV_IDENTIDADE" "encontrado ($(wc -l < "$ENV_IDENTIDADE") linhas)"
printf '  %-22s %s\n' "$ENV_ALUNOS" "encontrado ($(wc -l < "$ENV_ALUNOS") linhas)"
printf '  %-22s %s\n' "$ENV_PAGES" "encontrado ($(wc -l < "$ENV_PAGES") linhas)"
if [ "$NOVOS" -eq 0 ]; then
  echo "  segredos ............... os dois pares JÁ existiam; vou reusar, não regerar"
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
# E só então o consumidor.
garantir "$ENV_PAGES" IDENTIDADE_API_URL "$IDENTIDADE_URL" "par pages->identidade"
garantir "$ENV_PAGES" IDENTIDADE_API_TOKEN "$T_IDENTIDADE" "par pages->identidade"
garantir "$ENV_PAGES" ALUNOS_API_URL "$ALUNOS_URL" "par pages->alunos"
garantir "$ENV_PAGES" ALUNOS_API_TOKEN "$T_ALUNOS" "par pages->alunos"

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

conferir_endereco() {  # arquivo, chave, valor-esperado
  [ "$(ler_de "$1" "$2")" = "$3" ] || parar "$2 não ficou como esperado em $1. As cópias intactas estão em $RAIZ ($BACKUPS). Me mande esta tela inteira."
}
conferir_endereco "$ENV_PAGES" IDENTIDADE_API_URL "$IDENTIDADE_URL"
conferir_endereco "$ENV_PAGES" ALUNOS_API_URL "$ALUNOS_URL"
echo "  endereços .............. os dois são os dos contratos congelados"

# Chave repetida é o modo de falha mais traiçoeiro de um env: o Docker Compose
# usa a ÚLTIMA, e um valor velho ficaria por baixo sem nada acusar.
for par in "$ENV_IDENTIDADE:TOKENS_ACEITOS_PAGES" "$ENV_IDENTIDADE:TOKENS_COMPLETOS_PAGES" \
           "$ENV_ALUNOS:TOKENS_ACEITOS_PAGES" \
           "$ENV_PAGES:IDENTIDADE_API_URL" "$ENV_PAGES:IDENTIDADE_API_TOKEN" \
           "$ENV_PAGES:ALUNOS_API_URL" "$ENV_PAGES:ALUNOS_API_TOKEN"; do
  arq="${par%%:*}"; chave="${par##*:}"
  n="$(grep -c "^$chave=" "$arq")"
  [ "$n" -eq 1 ] || parar "a chave $chave aparece $n vezes em $arq, e o Docker Compose usaria só a última. As cópias intactas estão em $RAIZ ($BACKUPS). Me mande esta tela inteira."
done
echo "  chaves repetidas ....... nenhuma (conferido nas 7)"
echo

# -----------------------------------------------------------------------------
# 5. RECARREGAR: as células precisam reler o env para as chaves valerem.
#    JAMAIS `docker compose up -d` sem argumento: isso devolveria TODAS as
#    células à tag :main do compose (RITOS §4). Só estes serviços, pelo nome.
# -----------------------------------------------------------------------------
echo "== recarregando as células para elas relerem o env =="
if command -v docker >/dev/null 2>&1; then
  ALVOS=""
  # Ordem: provedores, depois quem pergunta.
  for servico in identidade alunos pages; do
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
else
  echo "  (aviso: não achei o docker aqui. Os arquivos JÁ estão certos; o próximo deploy relê o env.)"
fi
echo

echo "A partir de agora a Prancheta sabe QUEM entrou e se a pessoa tem matrícula"
echo "ativa. Rodar esta mesma linha de novo é seguro: os segredos que já existem"
echo "são reusados, nunca trocados."
echo
echo "PRONTO: as duas conversas da Prancheta estão ligadas. Copie esta tela inteira e mande para o robô."
