#!/usr/bin/env bash
# =============================================================================
# PROVISIONAR A CÉLULA `notificacoes` NA VPS — o passo do mantenedor.
# Cria o par banco+role isolado e escreve o env real da célula.
#
# COMO O MANTENEDOR RODA (dentro da VPS, uma linha só, SEM argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-notificacoes.sh -o /tmp/p.sh && bash /tmp/p.sh
#
# POR QUE ESTE ARQUIVO EXISTE, e não um bloco colado no terminal: em 24/08/2026
# o console da VPS embaralhou DUAS colagens seguidas de um bloco multi-linha —
# os pedaços se sobrepuseram, o script rodou pela metade e um deles derrubou a
# sessão do mantenedor. Script versionado + uma linha curta de invocação elimina
# os dois modos de falha (H18/H19/H20, e a lei da gênese: DECISAO-notificacoes
# §1.4, que exige exatamente esta forma).
#
# NÃO PERGUNTA NADA e não precisa de segredo nenhum vindo de fora: esta célula
# não fala com Google, com Mercado Pago nem com a API de ninguém. Ela ouve o fio
# e escreve no próprio banco. É o provisionamento mais simples da plataforma até
# hoje, e isso é consequência do desenho: a carta chega endereçada, então a
# caixa nunca precisa perguntar quem é a pessoa.
#
# SEGREDOS: as duas senhas (banco e Django) são geradas AQUI, dentro da VPS, e
# gravadas direto no arquivo. Nenhuma aparece na tela, nenhuma passa por agente,
# nenhuma entra no Git (INV-P8, Lei 5).
#
# IDEMPOTENTE: rodar de novo é seguro. O role ganha senha nova, o banco só nasce
# se faltar, e o env antigo vira `.bak-<epoch>` antes de ser reescrito. ATENÇÃO:
# re-rodar ROTACIONA a chave do Django e a senha do banco desta célula — os
# avisos guardados continuam intactos (estão no banco, não na chave), mas a
# célula reinicia.
# =============================================================================
set -u

parar() { echo "PAROU POR SEGURANÇA: $1"; exit 1; }

cd /opt/plataforma 2>/dev/null || parar "não achei /opt/plataforma — você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…)"
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em /opt/plataforma."
[ -f env/sugestoes.env ]  || parar "não achei env/sugestoes.env — é dele que eu copio dono e permissões do arquivo novo."

# ---------------------------------------------------------------------------
# TRAVA DE DERIVA — este script REESCREVE `env/notificacoes.env` inteiro (o
# `cat >` lá embaixo). Logo, só pode rodar enquanto o heredoc souber gerar TODAS
# as chaves que o arquivo vivo já tem.
#
# Sem esta trava, o dia em que a Fase 4 acrescentar um `TOKENS_ACEITOS_FUNIL`
# aqui, re-rodar o script apagaria o token e o sino do site pararia de responder
# — com o deploy verde e nada acusando (é a `armadilhas/111`, e o script irmão
# da Caixa foi flagrado com esse buraco em 25/08/2026).
#
# A lista acompanha o heredoc, e
# `ci/tests/test_provisionamento_nao_perde_variavel.py` reprova se divergirem.
# ---------------------------------------------------------------------------
CHAVES_QUE_EU_GERO="DATABASE_URL DEBUG DJANGO_SECRET_KEY NOTIFICACOES_DIAS_ATE_ARQUIVAR REDIS_STREAMS_URL"

if [ -f env/notificacoes.env ]; then
  SOBRANDO=""
  for CHAVE in $(grep -oE '^[A-Z_][A-Z0-9_]*=' env/notificacoes.env | tr -d '=' | sort -u); do
    case " $CHAVES_QUE_EU_GERO " in
      *" $CHAVE "*) : ;;
      *) SOBRANDO="$SOBRANDO $CHAVE" ;;
    esac
  done
  if [ -n "$SOBRANDO" ]; then
    echo "PAROU POR SEGURANÇA: o env/notificacoes.env desta máquina tem variável que"
    echo "eu NÃO sei gerar, e eu reescrevo o arquivo inteiro. Rodar assim apagaria:"
    for CHAVE in $SOBRANDO; do echo "   - $CHAVE"; done
    echo
    echo "NADA foi alterado. O caminho de volta, por tipo de chave:"
    for CHAVE in $SOBRANDO; do
      case "$CHAVE" in
        TOKENS_ACEITOS_*|TOKENS_COMPLETOS_*)
          CELULA=$(echo "$CHAVE" | sed -E 's/^TOKENS_(ACEITOS|COMPLETOS)_//' | tr '[:upper:]' '[:lower:]')
          echo "   · $CHAVE -> é o par da célula '$CELULA'. Rode-me primeiro e"
          echo "     DEPOIS o infra/provisionar-$CELULA.sh, que regrava os dois lados."
          ;;
        VAPID_*)
          echo "   · $CHAVE -> é a chave do aviso na tela do celular. Rode-me"
          echo "     primeiro e DEPOIS o infra/provisionar-aviso-no-celular.sh."
          echo "     ATENÇÃO: a chave vai NASCER DE NOVO, e todo aparelho que já"
          echo "     recebia aviso vai precisar ligar outra vez (o cartaz volta a"
          echo "     aparecer para essas pessoas). Nada mais se perde."
          ;;
        *)
          echo "   · $CHAVE -> não sei de quem é. Mande esta tela ao agente."
          ;;
      esac
    done
    exit 1
  fi
fi

docker compose ps postgres >/dev/null 2>&1 || parar "não consegui falar com o Docker Compose aqui."
psql_super() { docker compose exec -T postgres psql -U postgres "$@"; }

echo "== estado ANTES =="
if psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='notificacoes_db'" 2>/dev/null | grep -q 1
then echo "  banco notificacoes_db ...... já existe"; else echo "  banco notificacoes_db ...... não existe"; fi
if [ -f env/notificacoes.env ]
then echo "  env/notificacoes.env ....... já existe (guardo cópia antes de reescrever)"
else echo "  env/notificacoes.env ....... não existe"; fi
echo

SENHA_DB="$(openssl rand -hex 24)"
CHAVE_DJANGO="$(openssl rand -hex 32)"

# Role: ALTER primeiro (caso de re-execução), CREATE se ainda não existir.
psql_super -c "ALTER ROLE notificacoes_user LOGIN PASSWORD '$SENHA_DB'" >/dev/null 2>&1 \
  || psql_super -c "CREATE ROLE notificacoes_user LOGIN PASSWORD '$SENHA_DB'" >/dev/null \
  || parar "não consegui criar/atualizar o usuário notificacoes_user."

psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='notificacoes_db'" 2>/dev/null | grep -q 1 \
  || psql_super -c "CREATE DATABASE notificacoes_db OWNER notificacoes_user" >/dev/null \
  || parar "não consegui criar o banco notificacoes_db."

# A muralha de dados (Lei 2): nenhuma outra célula enxerga este banco.
psql_super -c "REVOKE ALL ON DATABASE notificacoes_db FROM PUBLIC" >/dev/null \
  || parar "não consegui fechar o banco ao público."

umask 077
[ -f env/notificacoes.env ] && cp -a env/notificacoes.env "env/notificacoes.env.bak-$(date +%s)"

# O molde é infra/env/notificacoes.env.exemplo — se aquele arquivo ganhar
# variável nova, este bloco precisa ganhar junto, senão a célula sobe sem ela.
cat > env/notificacoes.env <<ENV
DJANGO_SECRET_KEY=$CHAVE_DJANGO
DATABASE_URL=postgres://notificacoes_user:$SENHA_DB@postgres:5432/notificacoes_db
DEBUG=0
REDIS_STREAMS_URL=redis://redis:6379/0
NOTIFICACOES_DIAS_ATE_ARQUIVAR=30
ENV

# DONO E MODO copiados de um env que JÁ FUNCIONA, em vez de escolhidos por mim:
# `umask 077` cria o arquivo do dono que rodou o script — e se isso for `root`,
# o usuário `deploy` (que o pipeline usa) NÃO consegue ler, e o deploy reprova
# com "permission denied". Medido em 24/08/2026, no primeiro deploy da Caixa.
chown --reference=env/sugestoes.env env/notificacoes.env 2>/dev/null || parar "não consegui ajustar o dono de env/notificacoes.env — rode como root ou como o dono dos outros env."
chmod --reference=env/sugestoes.env env/notificacoes.env 2>/dev/null || parar "não consegui ajustar as permissões de env/notificacoes.env."

echo "== estado DEPOIS =="
if psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='notificacoes_db'" 2>/dev/null | grep -q 1
then echo "  banco notificacoes_db ...... OK"; else echo "  banco notificacoes_db ...... FALTANDO"; fi
echo "  linhas em notificacoes.env . $(wc -l < env/notificacoes.env)  (esperado 5)"
echo "  dono/modo do env ........... $(stat -c '%U:%G %a' env/notificacoes.env) (igual ao sugestoes.env: $(stat -c '%U:%G %a' env/sugestoes.env))"
echo
echo "PRONTO. Agora avise o agente: ele sobe a célula pelo pipeline e confere que"
echo "ela respondeu. Você NÃO precisa rodar mais nada aqui."
