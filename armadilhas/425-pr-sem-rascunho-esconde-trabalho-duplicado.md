---
schema_version: 2
armadilha: 425
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/sessao.py
  - ci/pr.py
guarda:
  tipo: teste
  dono: ci/tests/test_sessao.py
sinal:
  - "a sessão começou sem PR draft e só anunciou o trabalho ao terminar"
licao: A abertura precisa criar e conferir o PR em rascunho antes do primeiro arquivo de código. O fechamento deve transformar esse mesmo PR em pronto para revisão depois da validação final, e um ramo com PR encerrado deve ser recusado.
---

# PR sem rascunho esconde trabalho duplicado

**Sintoma.** A sessão só anunciava o trabalho quando `ci/pr.py` terminava. Durante
a construção, outra sessão podia escolher a mesma tarefa ou repetir a mesma
correção porque o GitHub não mostrava intenção nenhuma.

**Causa.** O rito criava a bancada e esperava o código ficar pronto antes de
abrir o PR. A ausência de uma chamada no começo era tratada como silêncio, não
como uma falha de governança.

**Lição.** A abertura agora cria um commit de anúncio, publica um PR draft e
confere o estado remoto antes de liberar o trabalho. O fechamento reutiliza o
PR, valida a revisão final e só então o torna pronto para revisão. Consulta de
PR usa todos os estados para impedir que um ramo encerrado seja reaproveitado.
