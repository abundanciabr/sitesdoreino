#!/usr/bin/env bash
# Os números do banco, sem nome nem e-mail de ninguém. Serve para comparar o site no ar com um
# backup restaurado (infra/ensaiar-restauracao.sh) e para conferir uma restauração.
#
# Uso:
#   bash infra/numeros-do-banco.sh                       o Postgres do site (na VPS)
#   PG_CONTAINER=<id> bash infra/numeros-do-banco.sh     outro Postgres, como o do ensaio

set -eu
PROJETO="${PROJETO_COMPOSE:-plataforma}"
PG="${PG_CONTAINER:-$(docker ps -q --filter "label=com.docker.compose.project=$PROJETO" \
  --filter label=com.docker.compose.service=postgres | head -n1)}"
[ -n "$PG" ] || { echo "não achei o contêiner do Postgres (projeto $PROJETO)."; exit 1; }

numero() { # rótulo base consulta
  local n
  n="$(docker exec -i "$PG" psql -U postgres -AtX -d "$2" -c "$3" 2> /dev/null)" || n="(não deu para contar)"
  echo "  $1: $n"
}

numero "alunos (e-mails distintos com matrícula)" alunos_db "SELECT count(DISTINCT lower(email)) FROM matriculas_matricula"
numero "matrículas" alunos_db "SELECT count(*) FROM matriculas_matricula"
docker exec -i "$PG" psql -U postgres -AtX -F ': ' -d alunos_db -c "
  SELECT '    ' || CASE WHEN order_id LIKE 'pre:%' THEN 'liberado'
                         WHEN order_id LIKE 'admin:%' THEN 'administrativo' ELSE 'comprou' END
         || ', ' || status, count(*)
  FROM matriculas_matricula GROUP BY 1 ORDER BY 1" 2> /dev/null || true
numero "pagamentos registrados nas matrículas" alunos_db "SELECT count(*) FROM matriculas_pagamento"
numero "intenções de pagamento" pagamentos_db "SELECT count(*) FROM core_intent"
numero "tentativas de pagamento" pagamentos_db "SELECT count(*) FROM core_paymentattempt"
numero "operações de pagamento (transações)" pagamentos_db "SELECT count(*) FROM core_paymentoperation"
numero "pedidos do checkout" checkout_db "SELECT count(*) FROM pedidos_order"
numero "contas da identidade" identidade_db "SELECT count(*) FROM identidade_identidade"
numero "progresso nos cursos" cursos_db "SELECT count(*) FROM cursos_progresso"
numero "encomendas" encomendas_db "SELECT count(*) FROM encomendas_encomenda"
numero "tópicos do fórum" forum_db "SELECT count(*) FROM forum_topico"
numero "mensagens do fórum" forum_db "SELECT count(*) FROM forum_mensagem"
numero "lançamentos de pontos (XP)" gamificacao_db "SELECT count(*) FROM gamificacao_lancamentodexp"
numero "medalhas concedidas" gamificacao_db "SELECT count(*) FROM gamificacao_concessao"
numero "contatos (leads)" leads_db "SELECT count(*) FROM core_lead"
