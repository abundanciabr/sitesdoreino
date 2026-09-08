---
schema_version: 2
armadilha: 405
estado: documentada
degrau: 4
confianca: alta
custo_por_queda: medio
guarda:
  tipo: teste
  dono: services/cursos/tests/test_telas_da_sala.py
  detector: estados_de_lancamento_do_mapa
gatilho:
  - services/cursos/apps/core/views.py
  - services/cursos/apps/core/templates/cursos/catalogo.html
  - services/cursos/apps/core/templates/cursos/mapa.html
licao: 'O estado de publicação da Aula e o estado de Progresso respondem perguntas diferentes. Rascunho deve aparecer como em preparo e nunca virar link; aula publicada trancada deve explicar a dependência do progresso; publicada disponível pode abrir. publicada_em registra um fato e nunca agenda a porta.'
---

# 405: estado de lançamento não é progresso

**Data:** 08/09/2026. **Onde:** Fase 4 da sala de cursos.

## Sintoma e causa

O mapa usava o estado de Progresso como rótulo principal. Isso fazia uma aula
em rascunho parecer trancada quando ainda não havia uma linha de progresso, e
permitia que a primeira porta em preparo ocupasse o destaque da sala mesmo
quando uma aula publicada já estava aberta.

## Correção comprovada

A view combina `Aula.estado` com `Progresso.estado`: em preparo não tem link,
trancada explica que a aula anterior precisa ser concluída, aberta informa que
está disponível e concluída mantém o selo de conclusão. A seleção da porta em
destaque considera somente uma porta publicada e aberta. Nenhuma data de
publicação é consultada para liberar conteúdo.
