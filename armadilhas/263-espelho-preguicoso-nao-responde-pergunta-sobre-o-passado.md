---
schema_version: 2
armadilha: 263
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: services/gamificacao/tests/test_conceder_fundador.py
sinal:
  - backfill que consulta a tabela `Pessoa` da propria celula
  - "espelho minimo"
  - `get_or_create` de Pessoa dentro de um comando de backfill
---

# O backfill perguntou "quem estava aqui no começo?" ao espelho local, e recebeu "quem chegou por último"

**Sintoma.** Você escreve um comando de backfill histórico (a medalha de
Fundador, o selo de veterano, o brinde de aniversário da escola) e resolve a
lista de destinatários com uma consulta à tabela de pessoas da própria célula,
ordenando por `criada_em`. O comando roda, imprime uma lista plausível, concede
tudo. **Nada dá errado.** Sem exceção, sem log vermelho, sem teste amarelo.

E a lista está invertida. Quem entrou na escola há seis meses não aparece; quem
entrou anteontem recebe a medalha que diz "estava aqui no começo de tudo".
Quando alguém percebe, a concessão já existe, e desfazer concessão é um gesto
que este projeto não tem.

**Causa.** A tabela `Pessoa` de uma célula de consumo **não é cadastro: é
espelho, e ele é PREGUIÇOSO**. A linha não nasce quando a pessoa se matricula na
escola; nasce no primeiro momento em que ESTA célula precisou dela, que na
`gamificacao` é o primeiro XP creditado ou a primeira visita a `/conquistas`.
`criada_em` responde "quando esta célula viu esta pessoa pela primeira vez",
que é uma pergunta parecida com "quando esta pessoa entrou" e não é a mesma.

Para uma célula que subiu depois da escola, a diferença é total: **toda linha do
espelho é posterior à célula**, então nenhuma delas pode testemunhar sobre o
período que a medalha celebra. A consulta devolve linhas de verdade, com datas
de verdade, sobre um fato que não é o perguntado.

Isso é a mesma família da `armadilhas/253`: o dado que está ali não é a fonte da
verdade daquele fato, e a diferença não produz erro nenhum, só uma resposta
errada com cara de medida. É a **prova de fora** (RETROSPECTIVA-FASE-D §3)
aplicada a dado em vez de a teste.

**A tentação seguinte, e por que ela é pior.** Ao descobrir que meia lista está
faltando, o caminho curto é fazer o comando CRIAR as pessoas ausentes a partir
dos ids. Não faça: `Pessoa.email` é `unique`, e um e-mail fabricado
(`{id}@backfill.local`) não some quando a pessoa real chega. Ele ocupa a chave, e
a linha verdadeira passa a não conseguir nascer. Você troca um relatório errado
por um bloqueio permanente e silencioso no cadastro daquela pessoa.

**Solução, em três partes:**

1. **A lista de um backfill histórico é ARGUMENTO, não consulta.** Quem sabe
   quem estava lá é o mantenedor (ou a célula dona daquele fato, se você tiver
   mandato para consumi-la). O comando recebe `--ids` e executa. Um comando que
   deduz destinatário de um fato que ele não presenciou está adivinhando.
2. **Id que o espelho não conhece é REPORTADO, nunca criado.** Deixe a pessoa
   nascer pelo caminho normal e rode o comando de novo. Isso só é aceitável
   porque a parte 3 existe.
3. **Re-executável por construção, e provado por teste.** O `Unique(pessoa,
   conquista)` do banco é o que permite a lista chegar em pedaços. Sem essa
   garantia, "rode de novo depois" vira "credite duas vezes depois".

O comando que saiu disso, com as três partes juntas:
`services/gamificacao/apps/gamificacao/management/commands/conceder_fundador.py`.

**A regra de bolso:** antes de escrever qualquer consulta dentro de um backfill,
pergunte *esta tabela presenciou o fato que eu estou perguntando?*. Se a tabela
nasceu depois do fato, a resposta dela é ficção, e nenhum portão vai avisar.

**Origem.** 01/09/2026, degrau 22 da escada da gamificação (TAR-094), ao
desenhar `conceder_fundador`. O erro foi evitado no papel e não em produção:
`validacao.conceder()` já dizia na docstring que a idempotência existia "para o
backfill do Fundador poder ser re-executado", e foi olhar POR QUE ele precisaria
ser re-executado que expôs a preguiça do espelho. A armadilha fica escrita
porque a próxima célula a ganhar uma medalha de época terá exatamente o mesmo
espelho e exatamente a mesma tentação.
