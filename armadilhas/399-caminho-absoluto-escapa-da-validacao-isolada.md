---
schema_version: 2
armadilha: 399
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: ci/tests/test_pr.py
  detector: test_argumento_absoluto_original_e_recusado
sinal: 'teste verde usa arquivo que não viaja no PR'
gatilho:
  - ci/pr.py
licao: 'Valide o commit em árvore isolada e use argumentos relativos ao repositório. Caminho absoluto de script pode importar arquivo ignorado ou não rastreado da bancada original, mesmo com cwd isolado.'
---

# 399: Caminho absoluto escapa da validação isolada

**Data:** 08/09/2026. **Onde:** auditoria do PR #1377, Fase 1.

## Sintoma

O comando Python executava `check.py` por caminho absoluto na bancada original.
O teste importava `necessario.py`, não rastreado, e aprovava. A revisão entregue
falhava com `ModuleNotFoundError` na árvore limpa.

## Causa

Mudar apenas o diretório de execução não muda o diretório de importação de um
script absoluto. Arquivos ignorados e não rastreados podem mascarar o defeito.

## Solução

Executar a validação em worktree efêmero do commit e recusar argumentos absolutos
de arquivos, inclusive no formato de opção com valor. O caminho absoluto do
interpretador continua permitido. Repetir a prova no SHA final com recibos,
guardando logs privados sanitizados fora da árvore entregue.

## Evidência

PR #1377, `ci/tests/test_pr.py::test_argumento_absoluto_original_e_recusado`:
reprodução com Git real e variantes de argumento. Auditoria independente aprovou
os 113 testes focais; a suíte composta posterior passou 2333 testes.
