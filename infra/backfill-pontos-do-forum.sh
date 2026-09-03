#!/usr/bin/env bash
# =============================================================================
# ACERTO DE CONTAS ÚNICO DO FÓRUM — paga retroativamente o XP que as regras
# forum-topico-criado e forum-resposta-aceita deixaram de fora enquanto
# estiveram desligadas por engano (01/09/2026 a 03/09/2026).
#
# POR QUE ELE EXISTE
# -------------------
# Auditoria pedida pelo mantenedor em 03/09/2026: alunos já tinham participado
# do fórum, mas o quadro de pontos continuava zerado. Duas causas achadas e
# consertadas no PR #918 (a quarentena nunca era liberada sozinha; as 3 regras
# do fórum apareciam sem tradução em /admin/economia/ e provavelmente nunca
# foram reconhecidas para ligar). Uma vez ligadas, o mecanismo de "nunca
# retroativo" (`RegraDePontuacao.vigente_desde`) passou a proteger o
# instante do clique — e por desenho NUNCA paga o que aconteceu antes dele.
#
# O mantenedor pediu explicitamente para pagar esse intervalo retroativamente
# (é uma exceção CONSCIENTE e ANUNCIADA à lei §10.5, não um contorno
# silencioso — ver a docstring do comando
# `backfill_pontos_do_forum` para o raciocínio completo).
#
# COMO RODA (normalmente NÃO é o mantenedor quem roda):
#   pelo pipeline, `.github/workflows/backfill-pontos-do-forum.yml`, disparado
#   à mão pelo agente. Nenhum terminal envolvido.
#
# ENSAIO POR PADRÃO. Este script só passa `--confirmo` ao comando quando a
# variável de ambiente CONFIRMAR valer exatamente "sim" — e ela só chega assim
# quando o disparo do workflow pedir explicitamente. Todo disparo "no escuro"
# roda em ensaio, e ensaio NUNCA grava nada (o comando confirma isso sozinho:
# roda tudo dentro de uma transação e desfaz no final).
#
# SEGURO DE RODAR DUAS VEZES: o comando é idempotente por construção
# (`origem_event_id` determinístico + a MESMA trava única do ledger normal).
# Rodar de novo, mesmo confirmado, não paga duas vezes.
#
# NÃO escreve segredo, não toca env, não reinicia serviço, não faz deploy. A
# única escrita são lançamentos de XP na própria gamificação, e só quando
# CONFIRMAR=sim.
# =============================================================================
set -u

parar() { echo; echo "PAROU POR SEGURANÇA: $1"; echo "NADA foi alterado."; exit 1; }

CONFIRMAR="${CONFIRMAR:-nao}"

cd /opt/plataforma 2>/dev/null || parar "não achei /opt/plataforma — você está na VPS certa?"
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em /opt/plataforma."
docker compose ps >/dev/null 2>&1 || parar "não consegui falar com o Docker Compose aqui."

echo "== 1/3 — conferindo se a gamificação está de pé =="
ESTADO=$(docker compose ps --status running --services 2>/dev/null | grep -Fx "gamificacao" || true)
[ -n "$ESTADO" ] || parar "o serviço 'gamificacao' não está rodando."
echo "  gamificacao ...... de pé"

echo
echo "== 2/3 — descobrindo de qual escola são as linhas =="
SITE=$(docker compose exec -T gamificacao printenv SITE_ID 2>/dev/null | tr -d '\r[:space:]')
[ -n "$SITE" ] || parar "o contêiner da gamificação não declara SITE_ID."
echo "  site lido do contêiner ...... ${SITE}"

echo
if [ "$CONFIRMAR" = "sim" ]; then
  echo "== 3/3 — CREDITANDO DE VERDADE (--confirmo) =="
else
  echo "== 3/3 — ENSAIO (nada será gravado) =="
fi
FLAG=""
[ "$CONFIRMAR" = "sim" ] && FLAG="--confirmo"
SAIDA=$(docker compose exec -T gamificacao python manage.py backfill_pontos_do_forum --site-id "$SITE" $FLAG 2>&1) \
  || { echo "$SAIDA"; parar "o comando falhou. A saída acima diz por quê."; }
echo "$SAIDA"

printf '%s' "$SAIDA" | grep -q '^TOTAL:' \
  || parar "o comando rodou mas não imprimiu a linha TOTAL — não posso afirmar o resultado."

echo
if [ "$CONFIRMAR" = "sim" ]; then
  echo "PRONTO: o acerto de contas foi gravado. A linha TOTAL acima diz exatamente o quê."
else
  echo "PRONTO: ensaio concluído, nada foi gravado. A linha TOTAL acima é o que SERIA pago."
  echo "Para gravar de verdade, dispare o workflow de novo marcando 'confirmar'."
fi
