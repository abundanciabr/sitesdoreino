---
schema_version: 2
armadilha: 447
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  motivo: ci/mandato_publicacao.py confere destino e commits antes dos envios de sessao.py e pr.py
sinal: segredo removido da árvore final permanece no histórico transmitido
gatilho:
  - ci/pr.py
  - ci/sessao.py
  - ci/mandato_publicacao.py
licao: Conferir só a árvore final não inspeciona todo o envio. Verifique os commits novos, os caminhos declarados e os URLs efetivos de leitura e push antes da publicação.
---

# Publicação inclui commits intermediários e destinos efetivos

Um segredo introduzido e removido em seguida continua no histórico que um
push transmite. A conferência do último diff não basta. Teste com Git real:
crie a versão indevida, remova-a num segundo commit e confirme a recusa.

O destino de push pode diferir do de leitura, e um remoto pode enviar a mais
de um endereço. Confira ambos antes de divulgar o conteúdo. O rito publica
apenas o ramo, sem incluir tags automaticamente.

A guarda identifica sinais conhecidos e exige arquivos declarados. Ela não
classifica toda informação confidencial nem substitui revisão do conteúdo,
a autorização do mantenedor ou a revisão automática do aplicativo.
