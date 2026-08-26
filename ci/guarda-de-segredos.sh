#!/usr/bin/env bash
# =============================================================================
# INV-P8 MECANIZADO — segredo de produção não existe fora da VPS.
# Credencial cara alcançável de ambiente de teste queima dinheiro real,
# mais cedo ou mais tarde. Aqui o CI reprova antes do merge.
# =============================================================================
set -euo pipefail
VIOLACAO=0

# [INV-CI01] `git grep` devolve 0 com achados, 1 sem achados e >1 em ERRO. O
# `if git grep ... 2>/dev/null` original juntava "não achei" e "não consegui
# procurar" no mesmo ramo — um git quebrado ou um repositório não resolvido
# fazia a guarda passar sem ter varrido nada. Aqui os três casos são distintos,
# e o stderr do git deixou de ser jogado fora.
procurar() {
  local rotulo="$1" saida="$2"; shift 2
  local status=0
  git grep -nE "$@" > "$saida" || status=$?
  case "$status" in
    0) echo "❌ SEGREDO: $rotulo no repositório:"; cat "$saida"; VIOLACAO=1 ;;
    1) : ;;  # nenhuma ocorrência — a varredura ACONTECEU e não achou nada
    *) echo "❌ ERROR guarda-de-segredos: git grep saiu com $status ao procurar $rotulo."
       echo "   A varredura NÃO aconteceu. Este resultado NÃO é um OK."
       exit 2 ;;
  esac
}

# 02-RED-TEAM.md cita APP_USR-fake123 como EXEMPLO do golpe nº 10, não como segredo real — excluído para não se autoacusar.
# docs/paineis/fotografias/ são os painéis HISTÓRICOS congelados (reforma de
# 26/08/2026): eles CITAM os mesmos exemplos fake do red-team dentro dos textos
# da época (o falso positivo do PR #3, de novo — mesma causa, mesma cura).
# Fotografia é imutável por regra; a exclusão cobre só o passado congelado,
# nunca o painel vivo (painel/), que continua varrido.
procurar "credencial de PRODUÇÃO do Mercado Pago (APP_USR-)" /tmp/seg1 \
  'APP_USR-[0-9A-Za-z]' -- . ':!ci/guarda-de-segredos.sh' ':!02-RED-TEAM.md' ':!docs/paineis/fotografias/'

procurar "chave privada" /tmp/seg2 \
  'BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY' -- .

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
