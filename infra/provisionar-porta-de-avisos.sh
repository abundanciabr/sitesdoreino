#!/usr/bin/env bash
# =============================================================================
# LIGAR O SINO À CAIXA CENTRAL DE AVISOS — o passo do mantenedor.
#
# Desde 27/08/2026 a porta de consulta da célula `notificacoes` está pronta e
# no ar (Fase 4/5/6 do sininho), e DUAS células já sabem chamá-la: o `funil`
# (o sino ao lado do nome, em toda página) e a `sugestoes` (a própria tela de
# avisos da Caixa). As duas hoje falham ABERTO/VISÍVEL na ausência das
# credenciais — nada quebra enquanto este script não rodar, o sino só continua
# invisível e a tela de avisos continua avisando que não consegue buscar.
#
# ENV NÃO VIAJA POR PIPELINE (INV-P8, Lei 5) — por isso este passo é seu.
#
# COMO RODAR (dentro da VPS, uma linha só, SEM argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-porta-de-avisos.sh -o /tmp/p.sh && bash /tmp/p.sh
#
# NENHUM SEGREDO VEM DE FORA. As duas credenciais (o par funil↔notificacoes e
# o par sugestoes↔notificacoes) são geradas AQUI, dentro da VPS
# (`openssl rand -hex 32`), gravadas direto nos três arquivos — nada aparece
# na tela, nada passa por agente, nada entra no Git.
#
# NÃO REESCREVE NENHUM ENV. Mesma forma do `provisionar-aprovadores.sh`: os
# três arquivos (`funil.env`, `sugestoes.env`, `notificacoes.env`) já estão
# VIVOS, com segredos em uso — refazê-los do zero rotacionaria tudo e
# derrubaria a sessão de todo mundo. Este script acrescenta ou atualiza SÓ as
# chaves que lhe dizem respeito, com `>>` ou `sed`; o resto de cada arquivo
# continua byte a byte como estava.
#
# IDEMPOTENTE, INCLUSIVE PARA OS SEGREDOS: se um par já tem token dos dois
# lados, este script REAPROVEITA o valor que já existe em vez de gerar um
# novo — gerar de novo sem atualizar os dois lados quebraria o par (um lado
# fica com o token velho, o outro com o novo, e a chamada volta 401 sem nada
# no deploy acusando). Só quando o par não existe em lugar nenhum é que um
# token novo nasce.
# =============================================================================

if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANÇA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessão. Rode com a palavra bash na frente: bash /tmp/p.sh"
  return 1 2>/dev/null || exit 1
fi

set -u

parar() { echo "PAROU POR SEGURANÇA: $1"; exit 1; }

# Só para os testes fora da VPS. O mantenedor nunca define isto.
RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
URL_NOTIFICACOES="http://notificacoes:8000/api/notificacoes"

cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ — você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…)"
for ARQUIVO in env/funil.env env/sugestoes.env env/notificacoes.env; do
  [ -f "$ARQUIVO" ] || parar "não achei $RAIZ/$ARQUIVO — alguma das três células não parece provisionada nesta máquina. Nada foi alterado."
  [ -w "$ARQUIVO" ] || parar "não consigo escrever em $RAIZ/$ARQUIVO — rode como root ou como o dono dos outros env. Nada foi alterado."
done

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
# inteiro. $1 arquivo-alvo, $2 arquivo-de-referência (dono/modo), $3 chave,
# $4 valor. Devolve em $ACAO o que fez, para o relatório final.
# -----------------------------------------------------------------------------
BACKUPS=""
escrever_chave() {
  ARQ="$1"; REF="$2"; CHAVE="$3"; VALOR="$4"
  ATUAL="$(ler_de "$ARQ" "$CHAVE")"

  if [ "$ATUAL" = "$VALOR" ]; then
    ACAO="já estava certo"
    return 0
  fi

  BK="$ARQ.bak-$(date +%s)"
  cp -a "$ARQ" "$BK" 2>/dev/null || parar "não consegui guardar a cópia de segurança de $ARQ. Não mexi em nada."
  BACKUPS="$BACKUPS $BK"

  if grep -q "^$CHAVE=" "$ARQ"; then
    sed -i "s|^$CHAVE=.*|$CHAVE=$VALOR|" "$ARQ" \
      || parar "a edição de $ARQ falhou. A cópia intacta está em $RAIZ/$BK."
    ACAO="atualizei a linha que já existia"
  else
    if [ -s "$ARQ" ] && [ "$(tail -c 1 "$ARQ" | wc -l)" -eq 0 ]; then
      printf '\n' >> "$ARQ" || parar "não consegui escrever em $ARQ. A cópia intacta está em $RAIZ/$BK."
    fi
    printf '%s=%s\n' "$CHAVE" "$VALOR" >> "$ARQ" \
      || parar "não consegui escrever em $ARQ. A cópia intacta está em $RAIZ/$BK."
    ACAO="acrescentei a linha ao fim do arquivo"
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
for PAR in "env/funil.env NOTIFICACOES_API_TOKEN" "env/sugestoes.env NOTIFICACOES_API_TOKEN" "env/notificacoes.env TOKENS_ACEITOS_FUNIL" "env/notificacoes.env TOKENS_ACEITOS_SUGESTOES"; do
  set -- $PAR
  V="$(ler_de "$1" "$2")"
  if eh_placeholder "$V"; then echo "  $1 :: $2 ...... ausente"
  else echo "  $1 :: $2 ...... já existe"; fi
done
echo

# -----------------------------------------------------------------------------
# OS DOIS PARES — reaproveita o token se JÁ existir dos dois lados; gera um
# novo só quando o par não existe em lugar nenhum.
# -----------------------------------------------------------------------------
TOKEN_FUNIL="$(ler_de env/funil.env NOTIFICACOES_API_TOKEN)"
eh_placeholder "$TOKEN_FUNIL" && TOKEN_FUNIL=""
DO_LADO_DE_LA="$(ler_de env/notificacoes.env TOKENS_ACEITOS_FUNIL)"
eh_placeholder "$DO_LADO_DE_LA" && DO_LADO_DE_LA=""
if [ -n "$TOKEN_FUNIL" ] && [ "$TOKEN_FUNIL" = "$DO_LADO_DE_LA" ]; then
  : # os dois lados já concordam — reaproveita, não gera de novo
elif [ -n "$TOKEN_FUNIL" ]; then
  : # um lado já tem valor — reaproveita ESSE valor para o outro lado, nunca gera por cima
else
  TOKEN_FUNIL="$(openssl rand -hex 32)"
fi

TOKEN_SUGESTOES="$(ler_de env/sugestoes.env NOTIFICACOES_API_TOKEN)"
eh_placeholder "$TOKEN_SUGESTOES" && TOKEN_SUGESTOES=""
DO_LADO_DE_LA2="$(ler_de env/notificacoes.env TOKENS_ACEITOS_SUGESTOES)"
eh_placeholder "$DO_LADO_DE_LA2" && DO_LADO_DE_LA2=""
if [ -n "$TOKEN_SUGESTOES" ] && [ "$TOKEN_SUGESTOES" = "$DO_LADO_DE_LA2" ]; then
  :
elif [ -n "$TOKEN_SUGESTOES" ]; then
  :
else
  TOKEN_SUGESTOES="$(openssl rand -hex 32)"
fi

escrever_chave env/funil.env         env/sugestoes.env NOTIFICACOES_API_URL   "$URL_NOTIFICACOES"
escrever_chave env/funil.env         env/sugestoes.env NOTIFICACOES_API_TOKEN "$TOKEN_FUNIL"
escrever_chave env/sugestoes.env     env/alunos.env    NOTIFICACOES_API_URL   "$URL_NOTIFICACOES"
escrever_chave env/sugestoes.env     env/alunos.env    NOTIFICACOES_API_TOKEN "$TOKEN_SUGESTOES"
escrever_chave env/notificacoes.env  env/sugestoes.env TOKENS_ACEITOS_FUNIL      "$TOKEN_FUNIL"
escrever_chave env/notificacoes.env  env/sugestoes.env TOKENS_ACEITOS_SUGESTOES  "$TOKEN_SUGESTOES"

echo "== estado DEPOIS =="
for PAR in "env/funil.env NOTIFICACOES_API_URL" "env/funil.env NOTIFICACOES_API_TOKEN" "env/sugestoes.env NOTIFICACOES_API_URL" "env/sugestoes.env NOTIFICACOES_API_TOKEN" "env/notificacoes.env TOKENS_ACEITOS_FUNIL" "env/notificacoes.env TOKENS_ACEITOS_SUGESTOES"; do
  set -- $PAR
  V="$(ler_de "$1" "$2")"
  if eh_placeholder "$V"; then echo "  $1 :: $2 ...... FALTANDO"; else echo "  $1 :: $2 ...... OK"; fi
done
echo "  cópias de segurança ..........${BACKUPS:- (nenhuma — nada precisou mudar)}"
echo

[ "$(ler_de env/funil.env NOTIFICACOES_API_TOKEN)" = "$(ler_de env/notificacoes.env TOKENS_ACEITOS_FUNIL)" ] \
  || parar "o par funil↔notificacoes ficou com valores DIFERENTES nos dois lados. Não prossegui para o recarregamento — me mande esta tela inteira."
[ "$(ler_de env/sugestoes.env NOTIFICACOES_API_TOKEN)" = "$(ler_de env/notificacoes.env TOKENS_ACEITOS_SUGESTOES)" ] \
  || parar "o par sugestoes↔notificacoes ficou com valores DIFERENTES nos dois lados. Não prossegui para o recarregamento — me mande esta tela inteira."

# -----------------------------------------------------------------------------
# RECARREGAR — só os serviços que leem estes três env, pelo nome. JAMAIS
# `docker compose up -d` sem argumento (RITOS §4): isso devolveria TODAS as
# células à tag :main do compose.
# -----------------------------------------------------------------------------
echo "== recarregando as três células para elas relerem o env =="
if command -v docker >/dev/null 2>&1; then
  ALVOS=""
  for servico in funil sugestoes sugestoes-relay notificacoes notificacoes-consumer; do
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

echo "PRONTO. O sino ao lado do seu nome e a tela de avisos da Caixa já podem"
echo "falar com a caixa central de avisos. Nenhum segredo apareceu na tela."
echo "Avise a sessão do agente — ela confere de fora que o sino está respondendo."
