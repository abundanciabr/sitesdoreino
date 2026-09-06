#!/usr/bin/env bash
# =============================================================================
# ALARME DE ESCOPO — "corrigir o Pix" não volta com 42 arquivos.
# fix: 1–5 arquivos · feature: 5–15 · acima disso: rito arquitetural (label).
# O que se conta é CÓDIGO: a escrituração obrigatória sai da conta (ver abaixo).
# Válvulas: label 'arquitetural' (rito próprio) · lane 'traducoes' (só dados
# em services/*/traducoes/** — ver o bloco da lane abaixo).
# =============================================================================
set -euo pipefail
BASE="${BASE_REF:-origin/main}"
PR_LABELS="${PR_LABELS:-}"

# -----------------------------------------------------------------------------
# A escrituração obrigatória NÃO entra no orçamento — e o porquê tem número.
#
# Desde 31/08/2026 a casa obriga cada PR a carregar a própria papelada: o
# registro do livro (o portão de pouso recusa PR sem ele), os eventos da fila,
# o mapa do site. Ninguém pode remover esses arquivos, e mesmo assim eles
# comiam o orçamento do trabalho de verdade.
#
# O caso medido é o PR #1161 (degrau 06 da escada do portfólio): 19 arquivos no
# diff, 13 de código e 6 de escrituração, reprovado por um contador que nunca
# teve a intenção de barrar aquilo. Para vencer o contador, a sessão aplicou a
# etiqueta 'arquitetural' num PR que não é arquitetural — e é assim que uma
# etiqueta morre, virando senha de contador em vez de significar "este PR muda
# a arquitetura".
#
# A isenção vale SÓ para esses caminhos: 16 arquivos de código continuam
# reprovando, tenham eles escrituração ao lado ou não. Isenção que salvasse
# código seria o fim do portão.
#
# As pastas vêm de `PASTAS_DE_ESCRITURACAO`, em ci/divida_do_livro.py, que já é
# a definição desta casa para "isto é papelada, não entrega". Uma segunda lista
# aqui divergiria da primeira no dia em que alguém mexesse numa só.
# -----------------------------------------------------------------------------
DIR_DO_PORTAO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_BIN=""
for candidato in python python3; do
  if command -v "$candidato" >/dev/null 2>&1; then
    PY_BIN="$(command -v "$candidato")"
    break
  fi
done
if [[ -z "$PY_BIN" ]]; then
  echo "❌ ERROR orcamento-de-mudanca: 'python' não está no PATH."
  echo "   As pastas de escrituração isentas são lidas de ci/divida_do_livro.py,"
  echo "   e sem Python não há como saber quais são. O orçamento NÃO foi medido."
  echo "   Este resultado NÃO é um OK. Ative o venv (ou instale o Python) e rode de novo."
  exit 2
fi
LEITURA_DAS_PASTAS='import sys; sys.path.insert(0, sys.argv[1]); from divida_do_livro import PASTAS_DE_ESCRITURACAO; print("\n".join(PASTAS_DE_ESCRITURACAO))'
if ! PASTAS_ISENTAS="$("$PY_BIN" -c "$LEITURA_DAS_PASTAS" "$DIR_DO_PORTAO")" || [[ -z "$PASTAS_ISENTAS" ]]; then
  echo "❌ ERROR orcamento-de-mudanca: não consegui ler PASTAS_DE_ESCRITURACAO."
  echo "   Origem: ci/divida_do_livro.py (o arquivo sumiu, mudou de nome, ou a"
  echo "   constante saiu de lá?). O orçamento NÃO foi medido; isto NÃO é um OK."
  exit 2
fi
# O Python do Windows traduz \n em \r\n ao imprimir, e um 'painel/<CR>' nunca
# casaria com 'painel/registros/...'. Medido nesta máquina: a isenção passava
# só para a última pasta da lista.
PASTAS_ISENTAS="${PASTAS_ISENTAS//$'\r'/}"

# Para a mensagem de recusa nomear as pastas sem guardar uma segunda cópia delas.
ISENTAS_EM_LINHA="$(printf '%s' "$PASTAS_ISENTAS" | tr '\n' ' ')"

eh_escrituracao() {
  local caminho="$1" pasta
  while IFS= read -r pasta; do
    if [[ -n "$pasta" && "$caminho" == "$pasta"* ]]; then
      return 0
    fi
  done <<< "$PASTAS_ISENTAS"
  return 1
}

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
# `N` é o que o orçamento MEDE (código); `N_BRUTO`, o tamanho do diff inteiro.
N=0
N_BRUTO=0
while IFS= read -r CAMINHO; do
  if [[ -n "$CAMINHO" ]]; then
    N_BRUTO=$((N_BRUTO + 1))
    if ! eh_escrituracao "$CAMINHO"; then
      N=$((N + 1))
    fi
  fi
done <<< "$DIFF_BRUTO"
echo "Arquivos alterados: $N_BRUTO ($N de código medidos, $((N_BRUTO - N)) de escrituração isentos)  (fix: 1–5 · feature: 5–15 · >15: mudança arquitetural)"

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
    if [[ -z "$DIFF_CRU" ]] || (( N_CRU < N_BRUTO )); then
      echo "❌ ERROR orcamento-de-mudanca: o diff cru ($N_CRU linhas) não cobre os $N_BRUTO arquivos contados."
      echo "   Instrumento incoerente — a lane NÃO inspecionou o PR inteiro. Isto NÃO é um OK."
      exit 2
    fi
    while IFS= read -r LINHA; do
      [[ -z "$LINHA" ]] && continue
      # Formato: ':<modo-velho> <modo-novo> <sha> <sha> <status>\t<caminho>'
      read -r _ MODO_NOVO _ <<< "$LINHA"
      CAMINHO="${LINHA#*$'\t'}"
      # A escrituração já saiu da conta lá em cima; ela também não é medida
      # aqui, senão o registro do próprio PR reprovaria o lote de tradução.
      if eh_escrituracao "$CAMINHO"; then continue; fi
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
  echo "❌ ORÇAMENTO: $N arquivos de código sem a label 'arquitetural'."
  echo "   (o diff tem $N_BRUTO arquivos; a escrituração em $ISENTAS_EM_LINHA não conta)"
  echo "   Ou o escopo vazou (o caso mais provável — reveja o diff contra o brief),"
  echo "   ou é mudança estrutural de verdade — e ela tem PR e rito próprios."
  exit 1
fi
echo "✅ Orçamento de mudança: OK"
