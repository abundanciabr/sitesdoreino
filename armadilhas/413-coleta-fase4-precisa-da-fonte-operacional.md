---
schema_version: 2
armadilha: 413
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: medio
gatilho:
  - ci/sessao.py
  - ci/registrar_tarefa_fase4.py
  - ci/fila.py
guarda:
  tipo: CI
  motivo: a fila valida a classificacao e a sessao encaminha a medicao ao registrador idempotente
sinal: 'a tarefa real existe na fila, mas nenhum manifesto chega ao caderno privado'
licao: 'A coleta Fase 4 deve nascer do contexto confiavel da fila e da sessao, carregar fonte, tarefa e tentativa e registrar campos ausentes como nulos; um comando manual paralelo cria relacao falsa ou duplicacao.'
---

# 413: Coleta Fase 4 precisa da fonte operacional

**Sintoma.** A tarefa foi executada, mas a análise não encontra manifesto ou não consegue relacionar tentativa, revisão e evidência.

**Causa.** O fluxo de sessão conhecia a tarefa e a tentativa, mas o registrador só era chamado por manifesto manual. A coleta dependia de uma segunda ação e podia perder dados ou duplicar a mesma tentativa.

**Lição.** A sessão deve chamar o registrador existente usando a classificação validada da fila. O manifesto precisa identificar a fonte confiável e preencher explicitamente métricas ainda ausentes com nulo.

**Limite da constatação.** A correção foi exercitada com uma tarefa elegível em fixture de fila e a prova operacional real da TAR-280 foi preservada. Isso comprova o caminho de coleta neste caso, não ganho geral de produtividade.
