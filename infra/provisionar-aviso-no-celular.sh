#!/usr/bin/env bash
# =============================================================================
# LIGAR O AVISO NA TELA DO CELULAR — o passo do mantenedor.
#
# Desde 31/08/2026 a plataforma inteira sabe mandar aviso para o celular de
# quem instalou o app: a célula `notificacoes` guarda o aparelho e envia, e o
# site pede a permissão. Falta UMA coisa, e ela só pode ser feita aqui dentro:
# a CHAVE VAPID, que é o que prova aos servidores da Google, da Apple e da
# Mozilla que o aviso saiu mesmo deste site.
#
# ENV NÃO VIAJA POR PIPELINE (INV-P8, Lei 5) — por isso este passo é seu.
#
# COMO RODAR (dentro da VPS, uma linha só, SEM argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-aviso-no-celular.sh -o /tmp/p.sh && bash /tmp/p.sh
#
# NENHUM SEGREDO VEM DE FORA. O par de chaves nasce AQUI, dentro da VPS, com o
# `openssl` que já está na máquina. A metade PRIVADA vai para o env da
# `notificacoes` e nunca aparece na tela; a metade PÚBLICA vai para o env do
# `funil` — essa não é segredo, ela existe justamente para o navegador de cada
# aluno poder lê-la.
#
# NÃO REESCREVE NENHUM ENV. Mesma forma do `provisionar-porta-de-avisos.sh`:
# os dois arquivos já estão VIVOS, com segredos em uso. Este script acrescenta
# ou atualiza SÓ as chaves que lhe dizem respeito; o resto continua byte a
# byte como estava.
#
# IDEMPOTENTE, E AQUI ISSO IMPORTA MAIS QUE NOS OUTROS: se o par de chaves já
# existir, ele é REAPROVEITADO. Gerar um par novo por cima invalidaria, de uma
# vez, TODOS os aparelhos já inscritos — cada um deles pararia de receber
# aviso, em silêncio, e só voltaria se a pessoa desinstalasse e instalasse o
# app de novo. É a razão pela qual este script prefere não fazer nada a fazer
# duas vezes.
# =============================================================================

if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANÇA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessão. Rode com a palavra bash na frente: bash /tmp/p.sh"
  return 1 2>/dev/null || exit 1
fi

set -u

parar() { echo "PAROU POR SEGURANÇA: $1"; exit 1; }

# Só para os testes fora da VPS. O mantenedor nunca define isto.
RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"

# Um endereço de contato é EXIGIDO pelo padrão do web push: é por ele que um
# fabricante fala com o dono do site se algo der errado com os envios. Não é
# segredo e não é o e-mail pessoal de ninguém — é o contato do domínio.
CONTATO="mailto:contato@meshcraft.top"

cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ — você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…)"
for ARQUIVO in env/funil.env env/notificacoes.env; do
  [ -f "$ARQUIVO" ] || parar "não achei $RAIZ/$ARQUIVO — alguma das duas células não parece provisionada nesta máquina. Nada foi alterado."
  [ -w "$ARQUIVO" ] || parar "não consigo escrever em $RAIZ/$ARQUIVO — rode como root ou como o dono dos outros env. Nada foi alterado."
done
command -v openssl >/dev/null 2>&1 || parar "não achei o openssl nesta máquina, e é ele que gera a chave. Nada foi alterado."

ler_de() {  # arquivo, chave — devolve o valor limpo, sem comentário nem espaços
  grep "^$2=" "$1" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | tr -d '[:space:]'
}

eh_placeholder() {  # $1 = valor — verdadeiro se ainda é o texto de exemplo, ou vazio
  case "$1" in
    ""|*TROQUE_*|*troque_*) return 0 ;;
    *) return 1 ;;
  esac
}

# -----------------------------------------------------------------------------
# ESCREVER UMA CHAVE — acrescenta ou atualiza, nunca reescreve o arquivo
# inteiro. Cópia do padrão de `provisionar-porta-de-avisos.sh` (Lei 7: entre
# scripts de infra copia-se o padrão, e ele já foi endurecido por duas rodadas
# de uso real). $1 arquivo-alvo, $2 arquivo-de-referência (dono/modo),
# $3 chave, $4 valor.
# -----------------------------------------------------------------------------
BACKUPS=""
escrever_chave() {
  ARQ="$1"; REF="$2"; CHAVE="$3"; VALOR="$4"
  ATUAL="$(ler_de "$ARQ" "$CHAVE")"

  if [ "$ATUAL" = "$VALOR" ]; then
    return 0
  fi

  BK="$ARQ.bak-$(date +%s)"
  cp -a "$ARQ" "$BK" 2>/dev/null || parar "não consegui guardar a cópia de segurança de $ARQ. Não mexi em nada."
  BACKUPS="$BACKUPS $BK"

  if grep -q "^$CHAVE=" "$ARQ"; then
    sed -i "s|^$CHAVE=.*|$CHAVE=$VALOR|" "$ARQ" \
      || parar "a edição de $ARQ falhou. A cópia intacta está em $RAIZ/$BK."
  else
    # A última linha de um env é um VALOR: sem esta quebra, a chave nova
    # grudaria no fim dela e as duas iriam para o lixo juntas.
    if [ -s "$ARQ" ] && [ "$(tail -c 1 "$ARQ" | wc -l)" -eq 0 ]; then
      printf '\n' >> "$ARQ" || parar "não consegui escrever em $ARQ. A cópia intacta está em $RAIZ/$BK."
    fi
    printf '%s=%s\n' "$CHAVE" "$VALOR" >> "$ARQ" \
      || parar "não consegui escrever em $ARQ. A cópia intacta está em $RAIZ/$BK."
  fi

  if [ "$(stat -c '%U:%G %a' "$ARQ" 2>/dev/null)" != "$(stat -c '%U:%G %a' "$REF" 2>/dev/null)" ]; then
    chown --reference="$REF" "$ARQ" 2>/dev/null \
      || parar "não consegui ajustar o dono de $ARQ — rode como root ou como o dono dos outros env. A cópia intacta está em $RAIZ/$BK."
    chmod --reference="$REF" "$ARQ" 2>/dev/null \
      || parar "não consegui ajustar as permissões de $ARQ. A cópia intacta está em $RAIZ/$BK."
  fi

  GRAVADO="$(ler_de "$ARQ" "$CHAVE")"
  REPETIDA="$(grep -c "^$CHAVE=" "$ARQ")"
  [ "$GRAVADO" = "$VALOR" ] || parar "$ARQ não ficou com o valor esperado em $CHAVE. A cópia intacta está em $RAIZ/$BK — me mande esta tela inteira."
  [ "$REPETIDA" -eq 1 ] || parar "a chave $CHAVE aparece $REPETIDA vezes em $ARQ, e o Docker Compose usaria só a última. A cópia intacta está em $RAIZ/$BK — me mande esta tela inteira."
}

echo "== estado ANTES =="
PRIVADA="$(ler_de env/notificacoes.env VAPID_PRIVATE_KEY)"
eh_placeholder "$PRIVADA" && PRIVADA=""
PUBLICA_LA="$(ler_de env/notificacoes.env VAPID_PUBLIC_KEY)"
eh_placeholder "$PUBLICA_LA" && PUBLICA_LA=""
PUBLICA_FUNIL="$(ler_de env/funil.env VAPID_PUBLIC_KEY)"
eh_placeholder "$PUBLICA_FUNIL" && PUBLICA_FUNIL=""
if [ -n "$PRIVADA" ]; then echo "  chave do aviso ............. já existe (vou reaproveitar)"
else echo "  chave do aviso ............. não existe (vou gerar uma agora)"; fi
if [ -n "$PUBLICA_FUNIL" ]; then echo "  metade pública no site ..... já existe"
else echo "  metade pública no site ..... falta"; fi
echo

# -----------------------------------------------------------------------------
# O PAR DE CHAVES. Reaproveitado quando as DUAS metades existem; gerado quando
# falta qualquer uma — a metade pública não pode ser recalculada a partir da
# privada aqui em shell puro, e um par pela metade não serve para nada.
# -----------------------------------------------------------------------------
if [ -n "$PRIVADA" ] && [ -n "$PUBLICA_LA" ]; then
  PUBLICA="$PUBLICA_LA"
else
  if [ -n "$PRIVADA" ]; then
    echo "AVISO: achei a metade privada sem a pública. Vou gerar um PAR NOVO."
    echo "Se algum aparelho já estava recebendo avisos, ele vai precisar ligar de"
    echo "novo (o cartaz volta a aparecer para essas pessoas)."
    echo
  fi
  PEM="$(mktemp)" || parar "não consegui criar o arquivo temporário da chave."
  # `trap` porque a chave privada crua não pode sobreviver a uma saída no meio
  # do caminho: qualquer fim deste script apaga o arquivo.
  trap 'rm -f "$PEM"' EXIT INT TERM
  chmod 600 "$PEM" 2>/dev/null
  openssl ecparam -name prime256v1 -genkey -noout -out "$PEM" 2>/dev/null \
    || parar "o openssl não conseguiu gerar a chave. Nada foi alterado."
  # As duas metades saem do MESMO arquivo, em formato base64url sem preenchimento
  # — que é a forma que o padrão do web push exige nos dois lados.
  PRIVADA="$(openssl ec -in "$PEM" -outform DER 2>/dev/null | tail -c +8 | head -c 32 | base64 | tr -d '\n=' | tr '+/' '-_')"
  PUBLICA="$(openssl ec -in "$PEM" -pubout -outform DER 2>/dev/null | tail -c 65 | base64 | tr -d '\n=' | tr '+/' '-_')"
  rm -f "$PEM"
  trap - EXIT INT TERM
  [ ${#PRIVADA} -eq 43 ] || parar "a chave privada saiu com tamanho estranho (${#PRIVADA} caracteres, esperado 43). Nada foi alterado."
  [ ${#PUBLICA} -eq 87 ] || parar "a chave pública saiu com tamanho estranho (${#PUBLICA} caracteres, esperado 87). Nada foi alterado."
fi

escrever_chave env/notificacoes.env env/funil.env VAPID_PRIVATE_KEY "$PRIVADA"
escrever_chave env/notificacoes.env env/funil.env VAPID_PUBLIC_KEY  "$PUBLICA"
escrever_chave env/notificacoes.env env/funil.env VAPID_SUBJECT     "$CONTATO"
escrever_chave env/funil.env        env/funil.env VAPID_PUBLIC_KEY  "$PUBLICA"

echo "== estado DEPOIS =="
for PAR in "env/notificacoes.env VAPID_PRIVATE_KEY" "env/notificacoes.env VAPID_PUBLIC_KEY" "env/notificacoes.env VAPID_SUBJECT" "env/funil.env VAPID_PUBLIC_KEY"; do
  set -- $PAR
  V="$(ler_de "$1" "$2")"
  if eh_placeholder "$V"; then echo "  $1 :: $2 ...... FALTANDO"; else echo "  $1 :: $2 ...... OK"; fi
done
echo "  cópias de segurança ..........${BACKUPS:- (nenhuma — nada precisou mudar)}"
echo

# As duas metades TÊM de ser do mesmo par nos dois arquivos. Diferentes, o
# navegador recusa a inscrição com um erro que só aparece no celular da pessoa
# — e do lado de cá tudo pareceria certo.
[ "$(ler_de env/funil.env VAPID_PUBLIC_KEY)" = "$(ler_de env/notificacoes.env VAPID_PUBLIC_KEY)" ] \
  || parar "a metade pública ficou DIFERENTE nos dois arquivos. Não prossegui para o recarregamento — me mande esta tela inteira."

# -----------------------------------------------------------------------------
# RECARREGAR — só os serviços que leem estes dois env, pelo nome. JAMAIS
# `docker compose up -d` sem argumento (RITOS §4): isso devolveria TODAS as
# células à tag :main do compose.
# -----------------------------------------------------------------------------
echo "== recarregando as células para elas relerem o env =="
if command -v docker >/dev/null 2>&1; then
  ALVOS=""
  for servico in funil notificacoes notificacoes-consumer; do
    if docker compose config --services 2>/dev/null | grep -qx "$servico"; then
      ALVOS="$ALVOS $servico"
    fi
  done
  if [ -n "$ALVOS" ]; then
    if docker compose up -d $ALVOS >/dev/null 2>&1; then
      echo "  recarreguei:$ALVOS"
    else
      echo "  (aviso: não consegui recarregar$ALVOS — os arquivos JÁ estão certos; o próximo deploy relê o env de qualquer forma. Avise o agente.)"
    fi
  else
    echo "  (aviso: não achei os serviços no compose desta máquina — o próximo deploy relê o env.)"
  fi
else
  echo "  (aviso: não achei o docker aqui — os arquivos JÁ estão certos; o próximo deploy relê o env.)"
fi
echo

echo "PRONTO. O aviso na tela do celular está ligado."
echo "A metade privada da chave não apareceu nesta tela, e não deve aparecer em"
echo "lugar nenhum. Avise a sessão do agente: ela confere de fora que o cartaz"
echo "de ligar os avisos já aparece para quem entrou no site pelo celular."
