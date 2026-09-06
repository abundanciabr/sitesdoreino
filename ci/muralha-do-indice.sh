#!/usr/bin/env bash
# =============================================================================
# MURALHA DO ÍNDICE — ela MATERIALIZA os gerados das armadilhas e confere o que
# saiu. Roda em todo PR (via ci/ci.py --apenas muralhas).
#
# POR QUE ELA EXISTE (30/08/2026, TAR-022)
# ----------------------------------------
# `armadilhas/INDICE.md`, `GUARDAS.json`, `SINAIS.json` e `GATILHOS.json`
# são GERADOS de `armadilhas/NNN-slug.md` por `ci/indice_de_armadilhas.py`. Até
# 30/08/2026 os três viajavam no Git — e a lei desta casa MANDA todo robô
# acrescentar uma armadilha ao fim de cada tarefa. Cada entrada nova reescreve
# os três arquivos inteiros (a tabela ganha uma linha, o rodapé muda a contagem,
# os dois JSON ganham um bloco no fim do array), então dois robôs do mesmo lote
# colidiam SEM TER ESCRITO UMA LINHA EM COMUM.
#
# Medido no lote de 4 robôs de 30/08/2026: DOIS dos quatro PRs foram devolvidos
# pela pista pelo mesmo conflito — o #571 uma vez e o #573 DUAS. Registro
# `20260830-024`.
#
# É a doença do painel (`armadilhas/156`), curada com o MESMO desenho — Onda 3
# do PLANO-MESTRE-ROBOS-SEM-COLISAO.md, F1:
#     fonte multiescritor (um arquivo por entrada, só se acrescenta)
#   + materialização de ESCRITOR ÚNICO (a integração gera, ninguém commita)
#   + validação independente (o passo 3 aqui embaixo, fora do gerador).
#
# AS TRÊS GARANTIAS, NESTA ORDEM
# ------------------------------
#   1. o índice CONSTRÓI a partir das entradas. É na construção que moram os
#      portões do catálogo: NNN repetido (armadilhas/085), frontmatter fora do
#      schema, guarda apontando arquivo que não existe, sinal que casa saída
#      benigna. Entrada quebrada reprova aqui, e nada é escrito;
#   2. construir de novo dá exatamente os mesmos bytes (`--conferir` logo
#      depois). Gerador não determinístico faria o mesmo catálogo virar índices
#      diferentes a cada máquina, sem nada acusar;
#   3. NENHUM dos três está no índice do Git. Este passo não reusa uma linha do
#      gerador: ele pergunta ao `git ls-files`, que é a fonte que o gerador não
#      visita. Quem devolvesse um deles ao Git reabriria a colisão em silêncio —
#      e silêncio é exatamente o que esta muralha existe para não permitir.
#
# O passo 3 é o que o `.githooks/pre-commit` já tenta pegar aqui na máquina; a
# diferença é que este vale para todo mundo, inclusive para quem clonou hoje e
# nunca rodou `git config core.hooksPath .githooks`.
#
# Dialeto (RETROSPECTIVA-FASE-D §1): exit 0 PASS · 1 FAIL · 2 ERROR.
# ERROR nunca vira PASS: "não consegui medir" é resultado, não silêncio.
# =============================================================================
set -uo pipefail

if [[ ! -d armadilhas ]]; then
  echo "❌ MURALHA DO ÍNDICE: armadilhas/ não existe."
  echo "   A memória de campo faz parte do repositório desde 23/08/2026 —"
  echo "   apagá-la (ou movê-la) não pode passar verde."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "❌ ERROR muralha-do-indice: 'python' não está disponível nesta máquina."
  echo "   A muralha NÃO inspecionou o índice. Este resultado NÃO é um OK."
  exit 2
fi
PY_BIN="$(command -v python3 || command -v python)"

falhou=0

# --------------------------------------------------- 1 e 2: construir e reconstruir
for passo in "" "--conferir"; do
  # O código do passo é lido ANTES de qualquer teste — veredito nunca se lê de
  # algo que passou por outro operador (`armadilhas/123`, e a lição gêmea que a
  # muralha do painel aprendeu ao imprimir "(exit 0)" ao reprovar).
  # shellcheck disable=SC2086
  saida="$("$PY_BIN" ci/indice_de_armadilhas.py $passo 2>&1)"
  codigo=$?
  if [[ $codigo -ne 0 ]]; then
    echo "❌ MURALHA DO ÍNDICE — reprovou em: python ci/indice_de_armadilhas.py $passo (exit $codigo)"
    echo "$saida" | tail -n 25 | sed 's/^/   /'
    if [[ $codigo -eq 2 ]]; then
      echo "   ⚠️ exit 2 = ERROR: a muralha NÃO conseguiu construir o índice. Isto NÃO é um OK."
      exit 2
    fi
    falhou=1
  fi
done

# ------------------------------------- 3: o escritor único, conferido de fora
# `git ls-files` é a fonte independente: ela enxerga o índice do Git, que é o
# que viaja no PR, e não a varredura de pasta que o gerador acabou de fazer.
no_git="$(git ls-files -- \
  armadilhas/INDICE.md armadilhas/GUARDAS.json armadilhas/SINAIS.json \n  armadilhas/GATILHOS.json 2>/dev/null)"
codigo=$?
if [[ $codigo -ne 0 ]]; then
  echo "❌ ERROR muralha-do-indice: 'git ls-files' não conseguiu inspecionar os gerados (exit $codigo)."
  echo "   A muralha NÃO mediu o índice do Git. Este resultado NÃO é um OK."
  exit 2
fi

if [[ -n "$no_git" ]]; then
  echo "❌ MURALHA DO ÍNDICE: artefato GERADO de volta no índice do Git."
  echo "$no_git" | sed 's/^/     /'
  echo
  echo "   Desde 30/08/2026 (TAR-022) quem materializa estes arquivos é a"
  echo "   integração — esta muralha, o SessionStart de .claude/settings.json e"
  echo "   'python ci/indice_de_armadilhas.py' na mão. Commitá-los devolve a"
  echo "   colisão diária entre robôs: toda armadilha nova reescreve os três"
  echo "   arquivos inteiros (medido: 2 dos 4 PRs de um lote devolvidos)."
  echo
  echo "   O que fazer: git rm --cached $(echo "$no_git" | tr '\n' ' ')"
  echo "   A fonte é armadilhas/NNN-slug.md — é ELA que viaja no PR."
  falhou=1
fi

if [[ $falhou -eq 1 ]]; then exit 1; fi
echo "✅ Muralha do índice: construiu das entradas, reconstruiu igual byte a byte,"
echo "   e nenhum dos gerados está no índice do Git."
