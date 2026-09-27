---
schema_version: 2
armadilha: 541
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: mover o check de 1 KB para antes da validacao exigiria montar o texto do recibo (titulo, detalhe, frente, evidencia) sem o commit/arvore validados ainda, mudanca de ordem no rito fora do alcance de uma entrada de licao
sinal:
  - "Encurte título e detalhe; preserve a evidência determinística"
gatilho:
  - "python ci/pr.py"
licao: "ci/pr.py roda a validacao do conteudo e faz git push + abre o PR (_achar_ou_abrir_o_pr) ANTES de montar e medir o recibo; se o recibo estourar 1 KB, o PR ja esta aberto e a tentativa inteira (validacao + push) se repete do zero. Meça o tamanho de titulo+detalhe (renderizar(campos) < 1024 bytes) antes de rodar o ci/pr.py, não depois de ver o erro."
---

# 541: `ci/pr.py` só mede o 1 KB do recibo depois de validar e abrir o PR

**Data:** 27/09/2026 · **Onde:** `ci/pr.py`, PR #2238 · **Custo evitado:**
repetir um ciclo inteiro de validação (~13 min por tentativa) só para
descobrir, no fim, que título e detalhe eram longos demais.

## Sintoma

Duas tentativas no PR #2238 pararam com

```
recibo excede 1 KB
```

depois de a validação inteira já ter rodado e o PR já estar aberto no
GitHub (o `git push` e `_achar_ou_abrir_o_pr` já tinham acontecido).

## Causa

Em `ci/pr.py`, a ordem de execução é: validar o conteúdo → `git push` →
abrir/achar o PR → só então montar `campos` com `renderizar(campos)` e medir
`len(texto.encode("utf-8")) >= 1024`. O tamanho do recibo depende de título e
detalhe, que já são conhecidos desde o início da chamada, mas o script só os
mede depois de gastar a parte mais cara do rito (validação e publicação).

## Solução

Antes de rodar `python ci/pr.py`, meça você mesmo o tamanho aproximado do
recibo: título + detalhe devem somar bem menos que 1 KB (o molde de
`painel/registros/` soma outros campos fixos). Se o `--detalhe` for longo,
encurte antes da primeira chamada, não depois do erro; encurtar depois exige
repetir validação e push.

## Evidência

PR #2238, 27/09/2026, duas tentativas reprovadas por `recibo excede 1 KB`
depois do PR já aberto.
