# Execução `cancelled` da pista de pouso é o desenho funcionando, não falha

**Sintoma:** a aba Actions do repositório aparece com uma parede de execuções
`pouso` cinzas seguidas, uma atrás da outra, todas com duração de 3–8 s, e uma
verde perdida no meio. Pela tela, parece que a pista quebrou e está falhando em
série:

```
pouso #698  completed  3s   ⊘
pouso #697  completed  6s   ⊘
pouso #696  completed  3s   ⊘
pouso #695  completed  8s   ⊘
pouso #691  completed  34s  ✅
```

`⊘` é **`cancelled`**, não `failure`. Na aba do GitHub os dois ícones são
pequenos e cinza-vs-vermelho é a única diferença — e ninguém repara nisso quando
há dez seguidos.

**Causa:** o `concurrency` do Actions **não é fila FIFO**. Quando existe uma
execução rodando e uma pendente, e chega uma terceira, a **pendente é cancelada**
para dar lugar à nova. O `pouso.yml` roda com `group: pouso` e
`cancel-in-progress: false` — ou seja, quem já está no ar nunca é interrompido
(cancelar um pouso no meio deixaria um PR atualizado e não mergeado), mas quem
está na sala de espera é descartado o tempo todo. Isso está escrito no cabeçalho
do próprio `pouso.yml` desde que ele nasceu, em 28/08/2026.

O que empilha os pedidos é o gatilho: a pista se **encadeia** ao terminar cada
pouso, o `schedule` a chama a cada 15 min, e cada merge na `main` movimenta a
fila. Num dia movimentado — a `main` deste projeto anda ~98 vezes por dia — dá
uma cancelada a cada duas execuções.

**Medido em 29/08/2026**, nas 100 execuções mais recentes do workflow:

| conclusão | quantas |
|---|---|
| `success` | 58 |
| `cancelled` | 41 |
| `failure` | **0** |

**Solução: não conserte nada — confira a conclusão, não o ícone.**

```bash
gh run list --workflow=pouso.yml --limit 100 --json conclusion -q '.[].conclusion' | sort | uniq -c
```

- Só `success` e `cancelled` na saída ⇒ **saudável**. O pedido cancelado não se
  perde: quem retoma é o encadeamento do fim de cada pouso e, se ele se perder,
  o `schedule` de 15 min.
- Apareceu `failure` ⇒ aí sim é ocorrência: `gh run view <id> --log-failed`.
- A prova de que a pista está viva não é a cor dos ícones, é o resultado dela —
  PRs entrando: `gh pr list --state merged --limit 10 --json number,mergedAt`.

**Não tente “arrumar” trocando o `concurrency`.** Ligar `cancel-in-progress:
true` interromperia pouso no meio (PR atualizado e não mergeado — estado pior que
não ter começado), e tirar o grupo poria dois pousos simultâneos disputando a
mesma `main`, que é exatamente a colisão que a pista existe para acabar.

**Por que isto vale uma entrada:** o custo não é de máquina, é de susto. O
mantenedor é leigo e abre a aba Actions; um agente sem contexto gasta uma rodada
de investigação para concluir “está tudo bem”. Ruído esperado que ninguém
declarou vira alarme falso — e alarme falso repetido é o caminho mais curto para
alguém deixar de olhar quando o ícone for vermelho de verdade.

**Origem:** pergunta do mantenedor em 29/08/2026, ao ver a aba Actions durante um
lote com 8 merges em 25 minutos. A pista estava com 0 falhas.
**Categoria** (`RETROSPECTIVA-FASE-D`): falso-verde (aqui pelo avesso — falso
vermelho) · garantia sem mecanismo.
