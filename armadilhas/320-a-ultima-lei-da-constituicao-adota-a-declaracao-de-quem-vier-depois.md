---
schema_version: 2
armadilha: 320
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  detector: ci/leis_sem_mecanismo.py
  motivo: "O censo reprova com '1 lei(s) sem mecanismo e fora da dívida' e nomeia 'CONSTITUICAO.md::Lei 9 — Multissítio' no instante em que uma lei nova entra depois dela sem que a declaração da Lei 9 tenha subido junto. O portão pega a queda, mas depois do fato: a lição aqui é o pré-diagnóstico, para ninguém gastar uma rodada procurando o erro na lei NOVA."
sinal:
  - "sem mecanismo e fora da dívida"
  - "CONSTITUICAO.md::Lei 9"
  - "CLAUDE.md::0. O princípio que governa"
---

# A última lei da Constituição adota a declaração de quem vier depois dela, e uma lei nova no fim rouba o mecanismo da anterior

**Sintoma.** Você acrescenta uma lei nova ao `CONSTITUICAO.md`, com a linha
`**Quem faz valer:**` corretamente escrita, e o censo reprova acusando **outra**
lei, que você nem tocou:

```
  toda lei declara quem a faz valer  FAIL   1 lei(s) sem mecanismo e fora da dívida
  - CONSTITUICAO.md::Lei 9 — Multissítio
```

**Causa.** `ci/leis_sem_mecanismo.py` corta o arquivo em `re.split(r"^## (Lei
\d+[^\n]*)$")`. O corpo de cada lei é tudo o que vem até o título da próxima —
e o corpo da **última** lei é tudo até o fim do arquivo, seções que não são leis
incluídas. Em 04/09/2026 a declaração da Lei 9 vivia na última linha do
`CONSTITUICAO.md`, depois de `## Definição de Pronto Arquitetônica` e de
`## Ritos`. O censo estava verde por acidente de posição: a Lei 9 herdava uma
declaração escrita três seções abaixo dela.

Entrou a `## Lei 10`, o corpo da Lei 9 encolheu até ali, e a declaração que ela
vinha adotando passou a pertencer à Lei 10. A Lei 9 ficou nua, e o vermelho
apontou para o único lugar onde você não mexeu.

**Solução.** Antes de acrescentar uma lei ao fim de um arquivo-lei, confira se a
lei que hoje é a última tem a declaração DENTRO do corpo dela — e, se não tiver,
suba a declaração junto no mesmo PR:

```bash
python ci/leis_sem_mecanismo.py --listar | tail -6   # quem declara o quê, hoje
```

A regra geral, que vale para qualquer arquivo-lei: **declaração colada logo
abaixo do texto da lei, nunca no rodapé do arquivo.** Rodapé funciona enquanto
ninguém escrever depois.

**A lição irmã, da mesma tarefa: onde uma lei nova fica para ninguém conseguir
ignorá-la.** O `CLAUDE.md` da raiz é o ÚNICO documento deste repositório que
entra sozinho no contexto de toda sessão, em toda bancada — arquivo novo na
raiz, por mais bem nomeado que seja, só é lido por quem lembrar de abri-lo. Ao
colar um texto de fora dentro dele, **demova os títulos**: neste arquivo `##` é
o marcador que o censo lê como "uma lei", e um documento colado com onze `##`
vira onze leis, cada uma cobrando a própria linha `**Quem faz valer:**`:

```
  - CLAUDE.md::0. O princípio que governa todos os outros
  - CLAUDE.md::1. Antes de escrever qualquer linha de código
  (… mais nove …)
```

`#` vira `###` e `##` vira `####`; o texto continua palavra por palavra, e o
censo continua contando uma lei só.
