#!/usr/bin/env bash
# =============================================================================
# INV-P8 MECANIZADO — segredo de produção não existe fora da VPS.
# Credencial cara alcançável de ambiente de teste queima dinheiro real,
# mais cedo ou mais tarde. Aqui o CI reprova antes do merge.
# =============================================================================
set -euo pipefail
VIOLACAO=0

# 02-RED-TEAM.md cita APP_USR-fake123 como EXEMPLO do golpe nº 10, não como segredo real — excluído para não se autoacusar.
if git grep -nE 'APP_USR-[0-9A-Za-z]' -- . ':!ci/guarda-de-segredos.sh' ':!02-RED-TEAM.md' > /tmp/seg1 2>/dev/null; then
  echo "❌ SEGREDO: credencial de PRODUÇÃO do Mercado Pago (APP_USR-) no repositório:"
  cat /tmp/seg1
  VIOLACAO=1
fi

if git grep -nE 'BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY' -- . > /tmp/seg2 2>/dev/null; then
  echo "❌ SEGREDO: chave privada no repositório:"
  cat /tmp/seg2
  VIOLACAO=1
fi

if (( VIOLACAO == 0 )); then
  echo "✅ Guarda de segredos: OK"
fi

# Os arquivos abaixo são MODELOS e devem SEMPRE conter placeholders TROQUE_.
# Se um deles perdeu o TROQUE_, é sinal de que um valor real foi gerado ali
# e commitado por engano (foi exatamente assim que provisionamento-postgres.sql
# quase vazou 7 senhas reais de banco — pego na auditoria, não pela lista).
TEMPLATES_COM_TROQUE=("infra/provisionamento-postgres.sql")
for f in infra/env/*.env.exemplo; do
  [[ -f "$f" ]] && TEMPLATES_COM_TROQUE+=("$f")
done
for f in "${TEMPLATES_COM_TROQUE[@]}"; do
  if [[ -f "$f" ]] && ! grep -q 'TROQUE' "$f"; then
    echo "❌ SEGREDO: '$f' perdeu os placeholders TROQUE_ — pode ter valor real commitado."
    VIOLACAO=1
  fi
done

exit $VIOLACAO
