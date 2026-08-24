<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §3 — Ambiente (Windows, esta máquina)
     ID historico: §3.19  ·  referencias antigas "ARMADILHAS §3.19" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 3.19 A conferência de CRLF do §3.12 (`grep -c $'\r'`) dá FALSO-POSITIVO no Git Bash desta máquina

**Sintoma:** `git show :ci/orcamento-de-mudanca.sh | grep -c $'\r'` responde `88`
num arquivo cujo blob tem **zero** bytes CR (provado por
`git cat-file blob :<arquivo> | tr -dc '\r' | wc -c` → `0`, e por `od -c`
mostrando `\n` puro). O número "de CRs" é na verdade o número de LINHAS do
arquivo: o CR do argumento se perde no caminho MSYS→grep e o grep roda com
padrão vazio — que casa toda linha. Medido em 23/08/2026, neste repositório.
**Causa:** conversão de argumentos do MSYS2 ao invocar o `grep` nativo — o
byte `\r` sozinho como argv não chega inteiro. O comando é o recomendado no
§3.12, então quem segue aquela receita ao pé da letra conclui "CRLF!" num
arquivo limpo (o inverso do falso-verde: um falso-VERMELHO que manda o agente
"consertar" o que não está quebrado).
**Solução:** medir por bytes, não por linhas casadas:
```bash
git cat-file blob :<arquivo> | tr -dc '\r' | wc -c   # 0 = limpo, N>0 = tem CR
```
Se der N>0, aí sim vale o §3.12 (`.gitattributes` com `*.sh text eol=lf` já
protege o blob neste repositório). Em caso de dúvida, `od -c` é o juiz.
**Origem:** despacho ci/lane-traducoes (23/08/2026) — a conferência exigida
pelo próprio despacho acusou 88 CRs num `.sh` limpo; meia hora de diagnóstico
para descobrir que o instrumento era o problema.
