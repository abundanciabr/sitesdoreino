---
schema_version: 2
armadilha: 423
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: medio
gatilho:
  - services/cursos/apps/core/templates/cursos/mapa.html
  - services/cursos/apps/cursos/management/commands/marcar_bosses_primeiros_dolares.py
guarda:
  tipo: CI
  dono: services/cursos/tests/test_marcar_bosses_primeiros_dolares.py
  detector: 'o comando não marca exatamente um Boss em cada módulo'
  motivo: "o mapa do curso não mostra nenhum desafio principal"
licao: "O mapa já desenha a marcação e_boss, mas o conteúdo existente precisa ter exatamente um desafio escolhido por módulo. A escolha deve ser aplicada por comando idempotente, com falha sem gravação quando algum título não existir."
---

# Boss do curso precisa de marcação real

O rótulo Boss não pode ser inventado pela posição da aula. Ele é uma marcação
estrutural de `Aula.e_boss`. Para preencher uma base existente, o comando deve
casar curso, módulo e título exato, conferir todos os módulos antes de gravar e
ser seguro para repetir.
