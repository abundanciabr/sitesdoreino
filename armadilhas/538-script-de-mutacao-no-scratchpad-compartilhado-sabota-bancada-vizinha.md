---
schema_version: 2
armadilha: 538
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/provar_guardas.py
sinal:
  - "sabotagem inesperada em arquivo que a tarefa não tocou"
guarda:
  tipo: nenhum
  motivo: "o scratchpad compartilhado da sessao e espaco livre por design; ensinar a maquina a recusar escrita ali para scripts de mutacao exigiria mudanca de codigo fora do alcance de uma entrada de licao"
licao: "Script de mutacao no scratchpad compartilhado da sessao pode ser sobrescrito por outro despacho paralelo e, ao rodar depois, sabotar o arquivo de producao de uma bancada vizinha. Script de mutacao so em %TEMP%/sitesdoreino-sessoes/<celula>-<tarefa>/, nunca no scratchpad compartilhado."
---

# 538: script de mutação no scratchpad compartilhado sabota bancada vizinha

**Data:** 27/09/2026 · **Onde:** scratchpad compartilhado da sessão, bancada
`wt-forum-comunidade-rastro-da-moderacao` (`moderacao.py`), obra Comunidade ·
**Custo evitado:** uma bancada de despacho paralelo teve seu arquivo de
produção sabotado por um script de mutação que não era dela, descoberto só
pelo relatório de outra tarefa (TAR-849).

## Sintoma

Um script de mutação (usado para a prova vermelho→verde da Lei 6) foi salvo
no scratchpad compartilhado da sessão, fora de qualquer bancada. Outro
despacho, rodando em paralelo na mesma sessão, escreveu por cima do mesmo
arquivo do scratchpad para o próprio uso. Quando o primeiro script foi
executado (por volta das 08h05), ele já não era mais o que o autor original
tinha escrito: rodou contra o caminho errado e sabotou `moderacao.py` na
bancada vizinha, sem qualquer aviso na hora. O problema só apareceu no
relatório de um despacho diferente (TAR-849), que teve de provar a limpeza
rodando a suíte no HEAD numa árvore separada (415 passed) e fazendo
`git grep` pelos marcadores de sabotagem.

## Causa

O scratchpad compartilhado da sessão é um único diretório usado por todos os
despachos daquela sessão ao mesmo tempo; não há isolamento por tarefa nem por
bancada. Um arquivo salvo ali (nome genérico, tipo `mutar.py`) é visível e
sobrescrevível por qualquer despacho paralelo. Um script de mutação guardado
lá carrega o caminho do alvo (ou é reescrito com um caminho novo por outro
despacho) e, ao ser executado por engano ou por atraso entre gravação e
execução, aplica a sabotagem no arquivo de quem escreveu por último, não no
arquivo de quem pretendia rodá-lo.

## Solução

1. Trabalho de despacho, inclusive scripts de mutação temporários usados na
   prova da Lei 6, vai sempre em
   `%TEMP%/sitesdoreino-sessoes/<celula>-<tarefa>/`, que é exclusivo da
   bancada, nunca no scratchpad compartilhado da sessão.
2. Depois de qualquer prova por mutação, confirme a limpeza com `git status`
   e `git grep` pelos marcadores de sabotagem na própria bancada antes de
   fechar o PR; se outra bancada pode ter sido afetada, rode a suíte dela
   numa árvore separada a partir do HEAD.
3. Nunca reaproveite um script de mutação salvo por outro despacho: escreva
   o seu na pasta exclusiva da própria tarefa.

## Origem

Relatório da TAR-849, obra Comunidade, 27/09/2026, bancada
`wt-forum-comunidade-rastro-da-moderacao`, `moderacao.py`.
