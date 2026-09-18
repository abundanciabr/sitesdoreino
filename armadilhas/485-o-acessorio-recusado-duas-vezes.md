---
schema_version: 2
armadilha: 485
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/pr.py
  - ci/fila.py
  - ci/sessao.py
sinal:
  - "tarefa já encerrada por outro fato"
  - "tarefa ausente, ambígua ou fila inválida"
  - "o ramo já tem o PR fechado"
  - "não existe na fila"
guarda:
  tipo: sino
  dono: ci/consultar_armadilhas.py
  detector: gatilho por caminho (ci/pr.py, ci/fila.py, ci/sessao.py)
licao: O rito recusou DUAS vezes um artefato que não é a entrega (registro de aceite, etiqueta, comentário)? Pare, relate em uma linha e siga: a terceira tentativa custou 20 minutos, um PR fechado pela metade e dois números de tarefa queimados. Regra irmã: UMA entrega, UMA bancada, UM ramo; reusar a bancada anterior deixa a tarefa ambígua para o ci/pr.py.
---

# Artefato acessório recusado duas vezes vira relato, não terceira tentativa

Medido em 17/09/2026, depois que a entrega de verdade (PR #1703) já estava
integrada e publicada. Faltava só um registro de aceite no livro. A sequência
que se pagou caro, na ordem:

1. `make pr` sem `TAR`: **tarefa não identificada para esta sessão**.
2. `make pr TAR=TAR-446`: o PR abriu, mas o recibo não embarcou porque a tarefa
   já tinha sido encerrada pela própria entrega. Um PR aberto pela metade
   (#1706), que precisou ser fechado à mão.
3. Tarefa nova (TAR-447) na MESMA bancada: **tarefa ausente, ambígua ou fila
   inválida**, porque o `ci/pr.py` soma a tarefa da abertura com a do pedido e
   recusa quando sobra mais de uma candidata.
4. `git clean` para limpar o ramo: apagou o JSON da TAR-447, que só existia ali.
   O número morreu com o arquivo.
5. Bancada nova com o mesmo slug: `ci/sessao.py` recusou, porque **o ramo já tem
   o PR fechado #1706**.

Só a sexta tentativa (bancada nova, slug novo, tarefa nova) passou. O artefato
valia um minuto; o caminho até ele custou vinte.

As duas regras que saem daí:

- **Uma entrega, uma bancada, um ramo.** Terminou o PR? A próxima entrega abre
  `python ci/sessao.py` de novo, com slug novo. Reaproveitar worktree é onde
  nascem as três recusas de cima.
- **Dois nãos do rito num artefato acessório = relate e siga.** O relatório
  honesto ("publicado, aceite não registrado porque o balcão recusa fechar
  tarefa já encerrada") entrega mais valor ao mantenedor que a terceira
  tentativa. Em cima disso, `git clean` e `git checkout .` numa bancada apagam
  arquivo de fila e registro que ainda não estão no Git: confira
  `git status --short` antes, sempre.
