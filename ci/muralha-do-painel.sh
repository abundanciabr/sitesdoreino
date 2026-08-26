#!/usr/bin/env bash
# =============================================================================
# MURALHA DO PAINEL — o livro de ocorrências não mente e não fica para trás.
#
# Roda em todo PR (via ci/ci.py --apenas muralhas). Três garantias:
#   1. manifesto.js está EM DIA com painel/registros/ (gerar_manifesto --conferir
#      — inclui a validação completa de cada registro, com a mesma logica.js
#      que a página usa);
#   2. a lógica que calcula as vistas continua passando no teste-guarda
#      (quem vigia o vigia da tela);
#   3. o gerador continua reprovando sabotagem (suíte adversarial dele).
#
# Nasceu da reforma dos painéis (26/08/2026): o painel antigo apodreceu porque
# NENHUMA trava alcançava os dados — arquivos/ era gitignored e nenhum workflow
# o validava. Com os registros no Git, esta muralha é o que faz "esquecer o
# painel" deixar de ser possível: PR que toca registros sem regenerar o
# manifesto reprova aqui.
#
# Dialeto (RETROSPECTIVA-FASE-D §1): exit 0 PASS · 1 FAIL · 2 ERROR.
# ERROR nunca vira PASS: "não consegui medir" é resultado, não silêncio.
# =============================================================================
set -uo pipefail

if [[ ! -d painel/registros ]]; then
  echo "❌ MURALHA DO PAINEL: painel/registros/ não existe."
  echo "   O livro de ocorrências faz parte do repositório desde 26/08/2026 —"
  echo "   apagá-lo (ou movê-lo) não pode passar verde."
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "❌ ERROR muralha-do-painel: 'node' não está disponível nesta máquina."
  echo "   A muralha NÃO inspecionou o painel. Este resultado NÃO é um OK."
  exit 2
fi

falhou=0
for passo in \
  "painel/gerar_manifesto.js --conferir" \
  "painel/testes/teste_logica.js" \
  "painel/testes/teste_gerador.js"; do
  # O código do passo é capturado ANTES de qualquer teste. Antes isto era
  # `if ! saida="$(node $passo)"; then codigo=$?`, e ali o `$?` já era o
  # resultado do `!` — sempre 0. Efeito medido em 26/08/2026: a muralha
  # imprimia "(exit 0)" ao reprovar, e o `exit 2` do instrumento quebrado
  # virava FAIL de conteúdo. Mesma família da armadilha 123 (veredito perdido
  # no cano): aqui ele se perdia na negação. Veredito se lê da fonte, nunca de
  # algo que passou por outro operador.
  # shellcheck disable=SC2086
  saida="$(node $passo 2>&1)"
  codigo=$?
  if [[ $codigo -ne 0 ]]; then
    echo "❌ MURALHA DO PAINEL — reprovou em: node $passo (exit $codigo)"
    echo "$saida" | tail -n 25 | sed 's/^/   /'
    # ERROR do passo (exit 2) é ERROR da muralha — instrumento quebrado não é FAIL de conteúdo.
    if [[ $codigo -eq 2 ]]; then
      echo "   ⚠️ exit 2 = ERROR: a muralha NÃO conseguiu inspecionar o painel. Isto NÃO é um OK."
      exit 2
    fi
    falhou=1
  fi
done

if [[ $falhou -eq 1 ]]; then exit 1; fi
echo "✅ Muralha do painel: manifesto em dia, lógica e gerador com os guardas verdes."
