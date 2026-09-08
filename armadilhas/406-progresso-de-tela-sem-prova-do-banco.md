---
schema_version: 2
armadilha: 406
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  dono: services/cursos/tests/test_catalogo_de_cursos.py
  detector: test_catalogo_mostra_progresso_real
gatilho:
  - services/cursos/apps/core/views.py
  - services/cursos/apps/core/templates/cursos/catalogo.html
  - services/cursos/apps/core/templates/cursos/mapa.html
licao: 'Quando a tela exibe progresso, o resumo deve nascer da consulta de Progresso da pessoa e ser testado junto dos estados sem aulas, rascunho e curso alheio. Aulas publicadas não são progresso concluído.'
---

# 406: Progresso de tela sem prova do banco

**Data:** 08/09/2026. **Onde:** Fase 3 da sala de cursos.

## Sintoma e causa

O catálogo e o mapa precisavam mostrar progresso, mas a tela só tinha a
contagem de aulas publicadas. Isso poderia virar um percentual inventado ou
uma segunda fonte de estado, especialmente para visitante e aluno de outro
curso.

## Solução

O resumo passou a contar aulas concluídas em `Progresso` filtrado pela pessoa
da sessão e pelo curso. Aulas em rascunho continuam visíveis como preparo,
sem convite quebrado, e estados de acesso continuam decididos pela porta.

## Guarda

Os testes da célula devem cobrir catálogo vazio, curso sem aulas, rascunho,
progresso real, curso alheio e mapa com próxima aula. A suíte local passou com
83 testes usando `--no-migrations`; o banco SQLite padrão não executa a
constraint composta PostgreSQL da célula.
