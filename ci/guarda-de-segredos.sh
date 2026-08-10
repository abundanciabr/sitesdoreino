#!/usr/bin/env bash
# =============================================================================
# INV-P8 MECANIZADO — segredo de produção não existe fora da VPS.
# Credencial cara alcançável de ambiente de teste queima dinheiro real,
# mais cedo ou mais tarde. Aqui o CI reprova antes do merge.
# =============================================================================
set -euo pipefail
VIOLACAO=0

if git grep -nE 'APP_USR-[0-9A-Za-z]' -- . ':!ci/guarda-de-segredos.sh' > /tmp/seg1 2>/dev/null; then
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
exit $VIOLACAO
