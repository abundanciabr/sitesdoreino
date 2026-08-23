#!/usr/bin/env bash
# =============================================================================
# ALARME DE ESCOPO — "corrigir o Pix" não volta com 42 arquivos.
# fix: 1–5 arquivos · feature: 5–15 · acima disso: rito arquitetural (label).
# Válvulas: label 'arquitetural' (rito próprio) · lane 'traducoes' (só dados
# em services/*/traducoes/** — ver o bloco da lane abaixo).
# =============================================================================
set -euo pipefail
BASE="${BASE_REF:-origin/main}"
PR_LABELS="${PR_LABELS:-}"

# `set -euo pipefail` já derrubava o script quando o git falhava aqui — mas com
# exit 128 e sem uma linha sequer explicando o que aconteceu. Falhar fechado sem
# diagnóstico manda o próximo agente investigar do zero (§19).
if ! DIFF_BRUTO="$(git diff --name-only "$BASE"...HEAD)"; then
  echo "❌ ERROR orcamento-de-mudanca: não foi possível calcular o diff."
  echo "   Comando: git diff --name-only $BASE...HEAD"
  echo "   BASE_REF='$BASE' existe? O checkout tem fetch-depth: 0?"
  echo "   O orçamento NÃO foi medido. Este resultado NÃO é um OK."
  exit 2
fi
if [[ -z "$DIFF_BRUTO" ]]; then N=0; else N=$(printf '%s\n' "$DIFF_BRUTO" | wc -l | tr -d ' '); fi
echo "Arquivos alterados: $N  (fix: 1–5 · feature: 5–15 · >15: mudança arquitetural)"

if (( N > 15 )) && [[ ",$PR_LABELS," != *",arquitetural,"* ]]; then
  # ---------------------------------------------------------------------------
  # Lane 'traducoes' (docs/i18n/PLANO-I18N.md, decisão D9): lote de tradução
  # pode exceder o teto de 15 arquivos SE E SOMENTE SE todo caminho do diff
  # estiver dentro da árvore de traduções de alguma célula
  # (services/<celula>/traducoes/**) e todo arquivo entrar como DADO — arquivo
  # regular ou remoção; executável, symlink e submódulo não passam (symlink
  # escaparia da árvore por referência). Mede superfície de risco, não
  # contagem bruta.
  #
  # A outra condição da D9 — "validadores i18n verdes" — é imposta pelo rito
  # de merge (ci/mergear.py exige TODOS os checks do PR verdes), não por este
  # script: aqui só entra o que o orçamento consegue medir sozinho, o diff.
  #
  # A label NUNCA aperta o portão: com N ≤ 15 este bloco nem roda, e a válvula
  # 'arquitetural' continua passando na frente (o if acima já deixou passar).
  # ---------------------------------------------------------------------------
  if [[ ",$PR_LABELS," == *",traducoes,"* ]]; then
    # --raw dá caminho E modo numa linha; --no-renames desdobra rename em
    # remoção+adição, para nenhum dos dois lados escapar da inspeção.
    if ! DIFF_CRU="$(git diff --raw --no-renames "$BASE"...HEAD)"; then
      echo "❌ ERROR orcamento-de-mudanca: não foi possível inspecionar o diff da lane traducoes."
      echo "   Comando: git diff --raw --no-renames $BASE...HEAD"
      echo "   O orçamento NÃO foi medido. Este resultado NÃO é um OK."
      exit 2
    fi
    N_CRU=$(printf '%s\n' "$DIFF_CRU" | wc -l | tr -d ' ')
    if [[ -z "$DIFF_CRU" ]] || (( N_CRU < N )); then
      echo "❌ ERROR orcamento-de-mudanca: o diff cru ($N_CRU linhas) não cobre os $N arquivos contados."
      echo "   Instrumento incoerente — a lane NÃO inspecionou o PR inteiro. Isto NÃO é um OK."
      exit 2
    fi
    while IFS= read -r LINHA; do
      [[ -z "$LINHA" ]] && continue
      # Formato: ':<modo-velho> <modo-novo> <sha> <sha> <status>\t<caminho>'
      read -r _ MODO_NOVO _ <<< "$LINHA"
      CAMINHO="${LINHA#*$'\t'}"
      if [[ ! "$CAMINHO" =~ ^services/[^/]+/traducoes/.+$ ]]; then
        echo "❌ ORÇAMENTO (lane traducoes): '$CAMINHO' está fora de services/*/traducoes/."
        echo "   A lane só cobre arquivos de dados dentro da árvore de traduções de uma"
        echo "   célula; qualquer outro caminho volta ao orçamento normal (≤15 arquivos)"
        echo "   ou ao rito arquitetural."
        exit 1
      fi
      case "$MODO_NOVO" in
        100644|000000) : ;;  # arquivo regular ou remoção — dados, como prometido
        *)
          echo "❌ ORÇAMENTO (lane traducoes): '$CAMINHO' entra com modo $MODO_NOVO."
          echo "   Tradução é DADO: só arquivo regular (100644) ou remoção (000000)."
          echo "   Executável (100755), symlink (120000) e submódulo (160000) não têm"
          echo "   lugar em services/*/traducoes/ — isso não é um lote de tradução."
          exit 1
          ;;
      esac
    done <<< "$DIFF_CRU"
    echo "✅ Orçamento de mudança: OK (lane traducoes — $N arquivos, todos dados em services/*/traducoes/)"
    exit 0
  fi
  echo "❌ ORÇAMENTO: $N arquivos sem a label 'arquitetural'."
  echo "   Ou o escopo vazou (o caso mais provável — reveja o diff contra o brief),"
  echo "   ou é mudança estrutural de verdade — e ela tem PR e rito próprios."
  exit 1
fi
echo "✅ Orçamento de mudança: OK"
