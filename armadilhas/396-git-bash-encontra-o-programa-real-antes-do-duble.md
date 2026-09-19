---
schema_version: 2
armadilha: 396
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: teste
  dono: ci/tests/test_por_a_chave_da_ia_do_admin.py
gatilho:
  - ci/tests/test_por_a_chave_da_ia_do_admin.py
licao: O Git Bash antepõe seus binários ao PATH herdado do Windows. Para simular a falha do sha256sum neste teste, carregue a função de falha por BASH_ENV restrito ao subprocesso; um executável falso no PATH pode ser ignorado.
---

# 396: Git Bash encontra o programa real antes do dublê

**Sintoma.** O teste de calculadora de resumo indisponível reprova no Windows:
o roteiro imprime PRONTO apesar do executável falso `sha256sum` devolver erro.

**Causa.** O Git Bash antepõe `/mingw64/bin:/usr/bin` ao PATH recebido do
Windows e encontra o `sha256sum` real. O docker falso continua funcionando
porque essas pastas não contêm docker, o que esconde a diferença entre os casos.

**Solução.** Neste teste, um arquivo temporário com LF define
`sha256sum() { return 1; }`. O `BASH_ENV` do subprocesso aponta para ele.
O Bash carrega a função antes do roteiro e a falha passa a ser executada.
O ambiente dos demais testes e o roteiro de produção permanecem intactos.

**Prova.** A suíte dirigida passou de 1 falha e 28 acertos para 29 acertos.
Numa cópia temporária do roteiro, remover a guarda de resumo vazio voltou
a reprovar o teste. A execução original é 34153354461 do workflow rede-do-windows.
