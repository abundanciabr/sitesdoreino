#!/usr/bin/env bash
# =============================================================================
# MURALHA DO PAINEL — ela MATERIALIZA o painel e depois confere o que saiu.
#
# Roda em todo PR (via ci/ci.py --apenas muralhas). Desde 28/08/2026 (Onda 3 do
# PLANO-MESTRE-ROBOS-SEM-COLISAO.md) o painel tem ESCRITOR ÚNICO: a fonte é
# `painel/registros/` (um arquivo por ocorrência, multiescritor, imune a
# conflito por construção) e os artefatos — `painel.html` e `livro-AAAAMM.js` —
# são construídos aqui, não commitados. Antes disso, todo PR que registrasse
# qualquer coisa reescrevia os dois arquivos inteiros, e dois robôs no mesmo dia
# colidiam sem ter escrito uma linha em comum (`armadilhas/156`: oito tentativas
# para um PR de 4 arquivos entrar).
#
# Cinco garantias, nesta ordem:
#   1. o painel CONSTRÓI a partir do livro (gerar_manifesto — inclui a validação
#      completa de cada registro, com a mesma logica.js que a página usa). Se um
#      registro estiver inválido, nada é escrito e a muralha reprova aqui;
#   2. construir de novo dá exatamente os mesmos bytes (`--conferir` logo depois
#      do build). Gerador não determinístico faria o mesmo livro virar imagens
#      diferentes a cada deploy, sem nada acusar;
#   3. a lógica que calcula as vistas continua passando no teste-guarda
#      (quem vigia o vigia da tela);
#   4. o gerador continua reprovando sabotagem (suíte adversarial dele);
#   5. um verificador ESCRITO DE FORA confere o resultado contra o índice do Git
#      (ci/verificar_painel.py) — e é ele que também reprova se um artefato
#      gerado voltar a ser commitado.
#
# Por que o passo 5 existe, sendo que os anteriores já conferem: os passos 1 a 4
# saem todos do mesmo programa. O `--conferir` compara a saída do gerador com a
# recomputação do gerador — um bug que pule registros gera os dois lados errados
# do mesmo jeito e fica verde. O passo 5 parte de `git ls-files`, em Python, sem
# reusar uma linha de código do gerador, e compara CONJUNTOS de ids em vez de
# contagens. É a resposta ao achado que três consultorias fizeram em 27/08/2026
# (correlated failure) — e o único passo capaz de dizer que o gerador mentiu.
#
# As duas provas medem coisas DIFERENTES de propósito: passos 1+2 são byte a
# byte (o build é reprodutível), o passo 5 é semântico (o conjunto de registros
# do Git chegou inteiro à tela). Nenhuma cobre a outra.
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
  "painel/gerar_manifesto.js" \
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

# O verificador independente. Python, e não node, de propósito — ver o cabeçalho.
# Ele fala o mesmo dialeto: 0 PASS, 1 FAIL, 2 ERROR.
if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "❌ ERROR muralha-do-painel: 'python' não está disponível nesta máquina."
  echo "   O verificador independente NÃO rodou. Este resultado NÃO é um OK."
  exit 2
fi
PY_BIN="$(command -v python3 || command -v python)"
saida="$("$PY_BIN" ci/verificar_painel.py 2>&1)"
codigo=$?
if [[ $codigo -ne 0 ]]; then
  echo "❌ MURALHA DO PAINEL — reprovou em: verificar_painel.py (exit $codigo)"
  echo "$saida" | tail -n 25 | sed 's/^/   /'
  # ERROR aqui só vira ERROR da muralha se NADA tiver reprovado antes. Se um
  # passo anterior já achou defeito de conteúdo, o veredito é FAIL: dizer "não
  # consegui medir" quando já se mediu e está quebrado é rebaixar uma certeza a
  # uma dúvida — e mandar quem lê investigar o instrumento em vez do defeito.
  if [[ $codigo -eq 2 && $falhou -eq 0 ]]; then
    echo "   ⚠️ exit 2 = ERROR: a muralha NÃO conseguiu inspecionar o painel. Isto NÃO é um OK."
    exit 2
  fi
  falhou=1
fi

if [[ $falhou -eq 1 ]]; then exit 1; fi
echo "✅ Muralha do painel: construiu do livro, reconstruiu igual byte a byte, guardas"
echo "   verdes, e o verificador de fora confirmou."
