#!/usr/bin/env bash
# =============================================================================
# MURALHA DE CÓDIGO — contratos mudam sozinhos e com rito.
#
# A CERCA "1 PR = 1 CÉLULA" CAIU EM 29/08/2026 (Onda 5 do
# `docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md`). Ela existia para comprar
# uma coisa que não era largura: restringir QUANTO do sistema um PR toca não
# compra exclusividade, e o argumento que encerrou a discussão é medido — a
# cerca **não teria evitado** o pior incidente já registrado aqui (o serviço
# novo e a configuração no mesmo commit passaram por dentro dela sem encostar).
#
# O que ficou no lugar dela, e por que só agora ela pôde cair:
#
#   celulas.yml + varredor    o mapa de quem é dono do quê, verificado contra
#                             o código em toda muralha (PR #442)
#   ci-celula em MATRIZ       o CI deriva do diff e roda a suíte de CADA célula
#                             tocada, em vez de recusar por largura (PR #443)
#   contrato aditivo          crescer é livre, remover exige autorização
#                             explícita (PR #445)
#   Depende-de: #N            ordem entre PRs, cobrada por máquina
#
# Proibição virou prova. O orçamento de 15 arquivos FICA: ele é barato, mede
# outra coisa (tamanho de uma mudança revisável) e continua útil. Desde o PR
# #1167 (06/09/2026) o que ele conta é CÓDIGO: a escrituração que a casa OBRIGA
# cada PR a carregar (`painel/` e `fila/`, a lista de `PASTAS_DE_ESCRITURACAO`
# em ci/divida_do_livro.py) sai da conta, porque comia o orçamento do trabalho
# de verdade. Quem mede é ci/orcamento-de-mudanca.sh, não este arquivo.
#
# O que este script ainda faz: o Rito de Contrato (RITOS.md §3) — contrato não
# pode crescer junto com seu provedor apenas com prova aditiva e freeze vivo; exige etiqueta.
# Roda em todo PR (workflow muralhas.yml).
# =============================================================================
set -euo pipefail
BASE="${BASE_REF:-origin/main}"
PR_LABELS="${PR_LABELS:-}"

# [INV-CI01] O diff é a MEDIÇÃO desta muralha. `mapfile < <(git diff ...)` não
# propaga a falha da substituição de processo: com um BASE_REF inválido, FILES
# vinha vazia, N virava 0 e a muralha imprimia "OK — 0 células". Aqui a falha do
# git é ERROR explícito, porque "não consegui ler o diff" não é "o diff está
# limpo".
if ! DIFF_BRUTO="$(git diff --name-only "$BASE"...HEAD)"; then
  echo "❌ ERROR cerca-de-celula: não foi possível calcular o diff."
  echo "   Comando: git diff --name-only $BASE...HEAD"
  echo "   BASE_REF='$BASE' existe? O checkout tem fetch-depth: 0?"
  echo "   A muralha NÃO inspecionou o PR. Este resultado NÃO é um OK."
  exit 2
fi

mapfile -t FILES <<< "$DIFF_BRUTO"

CELULAS=()
TEM_CONTRATO=0
CONTRATOS_HTTP=()
CONTRATO_FORA_HTTP=0
for f in "${FILES[@]}"; do
  case "$f" in
    services/*)  CELULAS+=("$(echo "$f" | cut -d/ -f2)") ;;
    contracts/README.md) TEM_CONTRATO=1 ;;
    contracts/*.openapi.yaml) TEM_CONTRATO=1; CONTRATOS_HTTP+=("$f") ;;
    contracts/*) TEM_CONTRATO=1; CONTRATO_FORA_HTTP=1 ;;
  esac
done

UNICAS=$(printf '%s\n' "${CELULAS[@]:-}" | sed '/^$/d' | sort -u)
# Contagem em bash puro: `grep -c . || true` mascarava tanto "zero linhas"
# (saída 1, legítima) quanto erro real do grep (saída 2) no mesmo resultado.
if [[ -z "$UNICAS" ]]; then N=0; else N=$(printf '%s\n' "$UNICAS" | wc -l); fi

if (( TEM_CONTRATO == 1 )); then
  if [[ ",$PR_LABELS," != *",contrato,"* ]]; then
    echo "❌ MURALHA: mudança em contracts/ exige a label 'contrato' (Rito de Contrato)."
    exit 1
  fi
  if (( N > 0 )); then
    if (( CONTRATO_FORA_HTTP == 1 || ${#CONTRATOS_HTTP[@]} == 0 )); then
      echo "❌ MURALHA: apenas contratos HTTP do próprio provedor podem acompanhar código. Separe os demais contratos."
      exit 1
    fi
    for contrato in "${CONTRATOS_HTTP[@]}"; do
      celula="${contrato#contracts/}"; celula="${celula%.openapi.yaml}"
      if ! printf '%s\n' "$UNICAS" | grep -Fxq "$celula"; then
        echo "❌ MURALHA: $contrato não pertence ao provedor tocado. Separe a mudança."
        exit 1
      fi
    done
    # Uma autorização de remoção não amplia esta exceção: o PR misto só cresce.
    PR_LABELS="" python ci/contrato_aditivo.py
    python - "$BASE" "${CONTRATOS_HTTP[@]}" <<'PY'
import copy, subprocess, sys
from pathlib import Path
import yaml
for arquivo in sys.argv[2:]:
    anterior = subprocess.run(["git", "show", f"{sys.argv[1]}:{arquivo}"], capture_output=True, text=True, encoding="utf-8")
    if anterior.returncode:
        print(f"ERROR: base de {arquivo} ausente. Publique o contrato novo pelo rito separado.")
        sys.exit(2)
    antigo, novo = yaml.safe_load(anterior.stdout), yaml.safe_load(Path(arquivo).read_text(encoding="utf-8"))
    reduzido = copy.deepcopy(novo)
    for doc in (antigo, reduzido):
        doc.get("info", {}).pop("description", None)
    metodos_http = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
    for caminho, item in antigo["paths"].items():
        extras = set(novo.get("paths", {}).get(caminho, {})) - set(item)
        if extras - metodos_http:
            print(f"FAIL: {arquivo} altera parâmetros ou configuração de caminho publicado. Use o rito separado.")
            sys.exit(1)
    try:
        reduzido["paths"] = {p: {m: novo["paths"][p][m] for m in metodos} for p, metodos in antigo["paths"].items()}
        if "components" in antigo:
            reduzido["components"] = {grupo: {nome: novo["components"][grupo][nome] for nome in itens} for grupo, itens in antigo["components"].items()}
        else:
            reduzido.pop("components", None)
    except (KeyError, TypeError):
        print(f"FAIL: {arquivo} remove estrutura publicada. Use o rito separado.")
        sys.exit(1)
    if reduzido != antigo:
        print(f"FAIL: {arquivo} altera uma operação ou definição publicada. O PR misto aceita apenas novas operações e definições.")
        sys.exit(1)
PY
    for contrato in "${CONTRATOS_HTTP[@]}"; do
      celula="${contrato#contracts/}"; celula="${celula%.openapi.yaml}"
      python ci/contract_freeze.py "$celula"
    done
  fi
fi

echo "✅ Cerca de célula: OK — ${N} célula(s) tocada(s)${UNICAS:+: $(echo $UNICAS | tr '\n' ' ')}"
