#!/usr/bin/env bash
# =============================================================================
# LIGAR A LISTA DE APROVADORES DA CAIXA DE SUGESTÕES — o passo do mantenedor.
#
# Desde 25/08/2026 só quem está em `SUGESTOES_APROVADORES` pode mandar uma ideia
# da Caixa para desenvolvimento. A célula lê a variável no PONTO DE USO e é
# FAIL-CLOSED: ausente ou vazia ⇒ NINGUÉM aprova. Ou seja, enquanto este script
# não rodar, o botão de aprovar não existe para pessoa alguma — a Caixa continua
# servindo normalmente, mas nenhuma ideia anda.
#
# ENV NÃO VIAJA POR PIPELINE (INV-P8, Lei 5). O `deploy-infra.yml` diz de si
# mesmo que JAMAIS toca `infra/env/` nem `/opt/plataforma/env/`. Por isso esta
# linha só existe se o mantenedor a puser na VPS — e por isso este arquivo
# existe: para esse passo ser UMA linha e não um texto para colar.
#
# POR QUE SCRIPT VERSIONADO, e não um bloco colado no terminal:
# em 24/08/2026 um passo entregue como bloco de colar falhou TRÊS vezes seguidas
# com o mantenedor, nenhuma por culpa dele — `set -euo pipefail` derrubou a
# sessão interativa, o console embaralhou a colagem multi-linha (os pedaços se
# sobrepuseram e o script rodou pela metade), e o env nasceu ilegível para o
# usuário do pipeline. O H20 (`provisionar-identidade.sh`) deu certo de PRIMEIRA
# exatamente por ter virado script + uma linha curta de invocação.
#
# COMO O MANTENEDOR RODA (dentro da VPS, uma linha só):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-aprovadores.sh -o /tmp/p.sh && bash /tmp/p.sh voce@gmail.com
#
# O E-MAIL PODE SER ARGUMENTO, E ISSO É DELIBERADO. A `armadilhas/090` proíbe
# SEGREDO em argumento porque ele vaza pela tela, pelo `~/.bash_history`, pelo
# `ps aux` e — o caminho que mais pega — pelo print que a pessoa manda para
# provar que funcionou. Aqui não há segredo nenhum: a lista de aprovadores é só
# endereço de e-mail, o mesmo tipo de dado que já está em claro no
# `SUGESTOES_STAFF_EMAILS` deste mesmo env. A própria armadilha manda separar:
# "o id do cliente é público por desenho e pode ser argumento; o segredo, não".
# Tratar tudo como segredo cansa o mantenedor — e um `read -s` aqui só
# esconderia da tela um dado que a Caixa exibe. NENHUM VALOR SECRETO É LIDO,
# ESCRITO OU IMPRESSO POR ESTE SCRIPT.
#
# SEM ARGUMENTO ele NÃO adivinha, e isso é de propósito. Se `SUGESTOES_STAFF_EMAILS`
# tiver EXATAMENTE UM endereço, não há ambiguidade — quem é staff sozinho é o
# dono, e ele herda esse valor dizendo na tela qual foi. Com dois ou mais, ele
# PARA e pergunta: herdar a lista inteira de staff ampliaria a autoridade em
# silêncio, que é o oposto exato da decisão de hoje ("só eu aprovo"). Moderar
# não é aprovar.
#
# NÃO REESCREVE O ENV. Repare a diferença para o `provisionar-sugestoes.sh`:
# aquele faz `cat > env/sugestoes.env` porque CRIA o arquivo, gerando chave do
# Django e senha do banco na hora. Aqui o arquivo já está VIVO — refazê-lo
# rotacionaria segredos em uso e derrubaria a sessão de todo mundo. Este script
# acrescenta ou atualiza UMA linha, com `>>` ou `sed`, e o resto do arquivo
# continua byte a byte como estava.
#
# IDEMPOTENTE: rodar de novo é seguro. Se a linha já existe com o mesmo valor,
# ele não toca em nada (nem faz cópia de segurança). Se existe com outro valor,
# ATUALIZA em vez de duplicar — chave repetida num env_file faz o Docker Compose
# usar a última, e um valor velho ficaria por baixo sem nada acusar.
#
# CUIDADO CONHECIDO: `provisionar-sugestoes.sh` regenera `env/sugestoes.env`
# inteiro a partir do molde dele, que NÃO tem esta variável. Se um dia aquele
# script rodar de novo, esta linha SOME e a Caixa volta a fail-closed (ninguém
# aprova) sem barulho. A cura é rodar ESTE script logo depois — é idempotente,
# custa uma linha.
# =============================================================================

# O modo de falha de 24/08 em pessoa: carregado com `source`/`.`, um `exit` daqui
# derrubaria a sessão do mantenedor. Com `bash /tmp/p.sh` o exit morre no filho.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANÇA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessão. Rode com a palavra bash na frente: bash /tmp/p.sh"
  return 1 2>/dev/null || exit 1
fi

set -u

parar() { echo "PAROU POR SEGURANÇA: $1"; exit 1; }

# Só para os testes fora da VPS. O mantenedor nunca define isto: o valor de
# verdade é /opt/plataforma, e é o que vale quando ele cola a linha.
RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
CHAVE="SUGESTOES_APROVADORES"
ENV_ALVO="env/sugestoes.env"
ENV_REF="env/alunos.env"

# -----------------------------------------------------------------------------
# 1. O VALOR — validado ANTES de tocar em arquivo nenhum.
#    Se o e-mail estiver malformado, nada é criado, nada é copiado, nada é
#    alterado: o script para aqui, antes até de procurar a pasta da plataforma.
# -----------------------------------------------------------------------------
# Já normalizado para minúsculas quando chega aqui, então [a-z0-9] basta. De
# quebra, este formato exclui espaço, vírgula, aspas e os metacaracteres que
# quebrariam o `sed` mais abaixo (| & \ $ `) — validar o e-mail é também o que
# torna a substituição segura.
FORMATO='^[a-z0-9]([a-z0-9._%+-]*[a-z0-9])?@[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*\.[a-z][a-z]+$'

LISTA=""
juntar() {  # acrescenta $1 à LISTA: normaliza, valida, e não duplica
  # Espaço SÓ nas pontas é aparado (colar de um e-mail costuma trazer um). Espaço
  # no MEIO fica, e o formato abaixo o recusa — medido nesta bateria em
  # 25/08/2026: com `tr -d '[:space:]'`, o erro de digitação `dono @gmail.com`
  # virava `dono@gmail.com` e era GRAVADO. Consertar em silêncio o que a pessoa
  # digitou é adivinhar quem manda numa lista de autoridade.
  e="$(printf '%s' "$1" | tr 'A-Z' 'a-z' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  [ -n "$e" ] || return 0
  case "$e" in
    *troque_*|*cole_*|*@exemplo.com|*@exemplo.com.br)
      parar "'$1' ainda é o texto de exemplo, não um e-mail de verdade. Nada foi alterado." ;;
  esac
  printf '%s' "$e" | LC_ALL=C grep -qE "$FORMATO" \
    || parar "'$1' não tem cara de e-mail. Nada foi alterado — rode de novo com o endereço completo, no formato nome@dominio.com."
  case ",$LISTA," in *",$e,"*) return 0 ;; esac
  if [ -z "$LISTA" ]; then LISTA="$e"; else LISTA="$LISTA,$e"; fi
}

# Aceita as duas formas: `bash p.sh a@x.com b@y.com` e `bash p.sh "a@x.com,b@y.com"`.
IFS_ORIGINAL="$IFS"
for argumento in "$@"; do
  IFS=','
  for pedaco in $argumento; do juntar "$pedaco"; done
  IFS="$IFS_ORIGINAL"
done

# -----------------------------------------------------------------------------
# 2. ONDE — a pasta da plataforma e os dois arquivos de que dependo.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ — você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…)"
[ -f "$ENV_ALVO" ] || parar "não achei $RAIZ/$ENV_ALVO — a Caixa de Sugestões não parece provisionada nesta máquina. Nada foi criado."
[ -f "$ENV_REF" ] || parar "não achei $RAIZ/$ENV_REF — é dele que eu copio dono e permissões, e sem essa referência eu não escrevo (o env nasceria ilegível para o pipeline)."
[ -w "$ENV_ALVO" ] || parar "não consigo escrever em $RAIZ/$ENV_ALVO — rode como root ou como o dono dos outros env. Nada foi alterado."

ler_de() {  # arquivo, chave — devolve o valor limpo, sem comentário nem espaços
  grep "^$2=" "$1" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | tr -d '[:space:]'
}

# -----------------------------------------------------------------------------
# 3. SEM ARGUMENTO: herda só se não houver dúvida. Nunca amplia por conta.
# -----------------------------------------------------------------------------
HERDADO="nao"
if [ -z "$LISTA" ]; then
  STAFF="$(ler_de "$ENV_ALVO" SUGESTOES_STAFF_EMAILS)"
  quantos=0; unico=""
  IFS=','
  for pedaco in $STAFF; do
    [ -n "$pedaco" ] || continue
    quantos=$((quantos + 1)); unico="$pedaco"
  done
  IFS="$IFS_ORIGINAL"

  if [ "$quantos" -eq 1 ]; then
    juntar "$unico"
    HERDADO="sim"
  elif [ "$quantos" -eq 0 ]; then
    parar "você não me disse quem aprova, e não há de quem deduzir (SUGESTOES_STAFF_EMAILS está vazia em $ENV_ALVO). Rode de novo com o seu e-mail no fim da linha:  bash /tmp/p.sh voce@gmail.com"
  else
    echo "A lista de quem MODERA a Caixa tem $quantos pessoas: $STAFF"
    echo "Mas moderar não é aprovar, e quem aprova é decisão sua — eu não escolho por você."
    parar "não sei qual dessas $quantos pessoas aprova. Rode de novo com o seu e-mail no fim da linha:  bash /tmp/p.sh voce@gmail.com   (nada foi alterado)"
  fi
fi

[ -n "$LISTA" ] || parar "fiquei sem nenhum e-mail para gravar. Nada foi alterado."

# -----------------------------------------------------------------------------
# 4. ESTADO ANTES — nenhuma linha de segredo é lida ou impressa aqui.
# -----------------------------------------------------------------------------
ATUAL="$(ler_de "$ENV_ALVO" "$CHAVE")"
echo "== estado ANTES =="
echo "  $ENV_ALVO ........ encontrado ($(wc -l < "$ENV_ALVO") linhas)"
if grep -q "^$CHAVE=" "$ENV_ALVO"; then
  if [ -n "$ATUAL" ]; then echo "  $CHAVE .. já existe: $ATUAL"
  else echo "  $CHAVE .. já existe, mas VAZIA (hoje ninguém aprova)"; fi
else
  echo "  $CHAVE .. não existe (hoje ninguém aprova)"
fi
if [ "$HERDADO" = "sim" ]; then
  echo "  quem vai aprovar ............... $LISTA  (herdado: é a única pessoa na lista de staff)"
else
  echo "  quem vai aprovar ............... $LISTA  (foi o que você me passou)"
fi
echo

# -----------------------------------------------------------------------------
# 5. ESCRITA — uma linha, e só ela. Nada de reescrever o arquivo.
# -----------------------------------------------------------------------------
if [ "$ATUAL" = "$LISTA" ]; then
  ACAO="nada a fazer: já estava assim"
  BACKUP="(nenhuma — não precisei tocar no arquivo)"
else
  BACKUP="$ENV_ALVO.bak-$(date +%s)"
  cp -a "$ENV_ALVO" "$BACKUP" 2>/dev/null \
    || parar "não consegui guardar a cópia de segurança de $ENV_ALVO. Não mexi em nada."

  if grep -q "^$CHAVE=" "$ENV_ALVO"; then
    sed -i "s|^$CHAVE=.*|$CHAVE=$LISTA|" "$ENV_ALVO" \
      || parar "a edição de $ENV_ALVO falhou. A cópia intacta está em $RAIZ/$BACKUP."
    ACAO="atualizei a linha que já existia"
  else
    # Se o arquivo não terminar em quebra de linha, o `>>` grudaria a chave nova
    # no fim da última linha — e a última linha de um env é um valor.
    if [ -s "$ENV_ALVO" ] && [ "$(tail -c 1 "$ENV_ALVO" | wc -l)" -eq 0 ]; then
      printf '\n' >> "$ENV_ALVO" || parar "não consegui escrever em $ENV_ALVO. A cópia intacta está em $RAIZ/$BACKUP."
    fi
    grep -q "^# aprovadores da Caixa" "$ENV_ALVO" \
      || printf '\n# aprovadores da Caixa — só quem está aqui manda uma ideia para desenvolvimento.\n# Escrita pelo infra/provisionar-aprovadores.sh; vazia ou ausente ⇒ ninguém aprova.\n' >> "$ENV_ALVO"
    printf '%s=%s\n' "$CHAVE" "$LISTA" >> "$ENV_ALVO" \
      || parar "não consegui escrever em $ENV_ALVO. A cópia intacta está em $RAIZ/$BACKUP."
    ACAO="acrescentei a linha ao fim do arquivo"
  fi

  # DONO E MODO copiados de um env que JÁ FUNCIONA, nunca escolhidos por mim
  # (armadilhas/091): rodando como root, o `sed -i` recria o arquivo e pode
  # deixá-lo root:root — e o usuário `deploy`, que é quem o pipeline usa, não lê
  # um 600 de root. O `deploy-infra` reprova com "permission denied" na
  # validação do compose, e a mensagem não diz quem não conseguiu ler.
  # Só chamo chown/chmod se algo REALMENTE divergiu — assim o script não exige
  # root quando não precisa.
  if [ "$(stat -c '%U:%G %a' "$ENV_ALVO" 2>/dev/null)" != "$(stat -c '%U:%G %a' "$ENV_REF" 2>/dev/null)" ]; then
    chown --reference="$ENV_REF" "$ENV_ALVO" 2>/dev/null \
      || parar "não consegui ajustar o dono de $ENV_ALVO — rode como root ou como o dono dos outros env. A cópia intacta está em $RAIZ/$BACKUP."
    chmod --reference="$ENV_REF" "$ENV_ALVO" 2>/dev/null \
      || parar "não consegui ajustar as permissões de $ENV_ALVO — rode como root ou como o dono dos outros env. A cópia intacta está em $RAIZ/$BACKUP."
  fi
fi

# -----------------------------------------------------------------------------
# 6. ESTADO DEPOIS — a conferência que fecha o assunto.
# -----------------------------------------------------------------------------
GRAVADO="$(ler_de "$ENV_ALVO" "$CHAVE")"
REPETIDA="$(grep -c "^$CHAVE=" "$ENV_ALVO")"
echo "== estado DEPOIS =="
echo "  o que eu fiz ................... $ACAO"
echo "  $CHAVE .. $GRAVADO"
echo "  vezes que a linha aparece ...... $REPETIDA  (tem de ser 1)"
echo "  linhas no arquivo .............. $(wc -l < "$ENV_ALVO")"
echo "  dono/modo do env ............... $(stat -c '%U:%G %a' "$ENV_ALVO" 2>/dev/null) (igual ao $ENV_REF: $(stat -c '%U:%G %a' "$ENV_REF" 2>/dev/null))"
echo "  cópia de segurança ............. $BACKUP"
echo

[ "$GRAVADO" = "$LISTA" ] || parar "o arquivo não ficou com o valor que eu queria gravar. A cópia intacta está em $RAIZ/$BACKUP — me mande esta tela inteira."
[ "$REPETIDA" -eq 1 ] || parar "a linha $CHAVE aparece $REPETIDA vezes em $ENV_ALVO, e o Docker Compose usaria só a última. A cópia intacta está em $RAIZ/$BACKUP — me mande esta tela inteira."
if [ "$(stat -c '%U:%G %a' "$ENV_ALVO" 2>/dev/null)" != "$(stat -c '%U:%G %a' "$ENV_REF" 2>/dev/null)" ]; then
  parar "o dono/permissão de $ENV_ALVO ficou diferente do $ENV_REF, e assim o deploy reprovaria com 'permission denied'. A cópia intacta está em $RAIZ/$BACKUP — me mande esta tela inteira."
fi

# -----------------------------------------------------------------------------
# 7. RECARREGAR — a Caixa precisa reler o env para a lista valer.
#    JAMAIS `docker compose up -d` sem argumento: isso devolveria TODAS as
#    células à tag :main do compose (RITOS §4). Só os serviços da Caixa, pelo
#    nome, e só os que existem neste compose.
# -----------------------------------------------------------------------------
echo "== recarregando a Caixa para ela reler o env =="
if command -v docker >/dev/null 2>&1; then
  ALVOS=""
  for servico in sugestoes sugestoes-relay; do
    if docker compose config --services 2>/dev/null | grep -qx "$servico"; then
      ALVOS="$ALVOS $servico"
    fi
  done
  if [ -n "$ALVOS" ]; then
    if docker compose up -d $ALVOS >/dev/null 2>&1; then
      echo "  recarreguei:$ALVOS"
    else
      echo "  (aviso: não consegui recarregar$ALVOS — o arquivo JÁ está certo; o próximo deploy da Caixa relê o env de qualquer forma. Avise o agente.)"
    fi
  else
    echo "  (aviso: não achei os serviços da Caixa no compose desta máquina — o próximo deploy da Caixa relê o env.)"
  fi
else
  echo "  (aviso: não achei o docker aqui — o arquivo JÁ está certo; o próximo deploy da Caixa relê o env.)"
fi
echo

echo "A partir de agora, só estes endereços mandam uma ideia da Caixa para"
echo "desenvolvimento: $GRAVADO"
echo "Trocar quem aprova é rodar esta mesma linha de novo com outro e-mail."
echo
echo "PRONTO: lista de aprovadores da Caixa ligada."
