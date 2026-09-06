---
schema_version: 2
armadilha: 357
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: a colisão acontece no disco da máquina do mantenedor, não no repositório, e nenhum portão do CI enxerga duas sessões entrando na mesma pasta. Tapar a janela invertendo a ordem (balcão antes da bancada) reabriria a armadilhas/192, que custou comprovante órfão e falso-verde no validador da fila. O que existe é o gesto deste arquivo, feito por quem topa com a pasta já criada: perguntar ao balcão ANTES de escrever um byte
sinal:
  - fatal: ... already exists
  - already exists
  - RECUSADO: TAR-NNN esta 'reivindicada'
  - RECUSADO PELO SERVIDOR
  - arquivo que voce nao escreveu dentro da sua bancada
  - dois robos na mesma bancada
---

# A trava do balcão tranca a TAREFA, não a PASTA: dois robôs escrevem na mesma bancada antes de saber quem perdeu

**Data:** 05/09/2026 · **Onde:** TAR-178 (as tabelas da casa `pages`), bancada `wt-modelos-do-portfolio` · **Custo evitado:** dois arquivos escritos dentro da bancada alheia, com a prova de que não destruíram nada vindo DEPOIS do gesto.

## Sintoma

Um destes três, e eles costumam vir em sequência:

1. `git worktree add ../wt-<nome> ...` recusa dizendo que o caminho já existe
   (`fatal: '../wt-<nome>' already exists`).
2. Você percebe, dentro da SUA bancada, arquivos que não escreveu: um
   `__init__.py` que já estava lá, um contêiner de teste de pé, um `.pyc` de
   código que você ainda não rodou.
3. `python ci/fila.py pegar TAR-NNN` recusa com
   `RECUSADO: TAR-NNN está 'reivindicada'.` (ou `RECUSADO PELO SERVIDOR`, quando
   a corrida é no mesmo minuto) **depois** de você já ter mexido na pasta.

A ordem importa: quando o balcão recusa, o estrago possível já aconteceu.

## Causa

Duas regras da casa, cada uma certa sozinha, se somam em exposição.

**1. O nome da bancada vem escrito DENTRO do despacho da tarefa.** Ele mora no
campo `despacho` de `fila/tarefas/NNN-*.json`, na linha
`CELULA: <celula> - WORKTREE: wt-<nome> - BRANCH: agent/<celula>/<nome>`. Dois
robôs que peguem a mesma tarefa vão para a MESMA pasta **por construção**, não
por azar. Não é como a [068](068-lote-outra-sessao-escrevendo-no-seu-worktree-git.md),
onde duas sessões acabam no mesmo diretório por descuido de lote: aqui o texto
da tarefa manda as duas para lá.

**2. A bancada nasce ANTES do balcão.** É a lei do RITOS §5 peça 1, e ela existe
por um motivo medido: inverter a ordem faz o comprovante de reivindicação nascer
no clone principal, órfão, com o validador da fila respondendo `✅ Fila válida`
sem ele (a [192](192-pegar-a-tarefa-antes-do-worktree-deixa-o-evento-no-espelho.md)).
Consequência direta: o segundo robô **necessariamente** cria ou encontra a pasta
ANTES de descobrir que perdeu a reserva.

**O miolo, dito com todas as letras: a trava do balcão é de TAREFA, não de
PASTA.** A reserva é uma referência atômica no servidor do GitHub
(`ci/reservar.py`) e ela protege o TRABALHO com perfeição: só um robô constrói,
nada é duplicado, nenhum PR nasce em dobro. Ela não tem, e não pode ter, opinião
sobre um diretório no disco da máquina do mantenedor. Entre o `git worktree add`
e o `fila.py pegar` existe uma janela em que dois robôs estão dentro do mesmo
diretório e o segundo ainda não sabe. A janela existe por construção das duas
regras acima, não por descuido de ninguém.

E o gesto natural de recuperação é justamente o errado: `git worktree add`
recusa porque o caminho existe, o robô lê "a pasta já está pronta", entra nela e
começa a trabalhar.

## O que aconteceu em 05/09/2026

Duas sessões do mantenedor foram atrás da TAR-178 com minutos de diferença. O
balcão funcionou: o primeiro robô (`despacho-pages-20260905`, evento de
23:54:38 UTC) ficou com a reserva, o segundo recebeu a recusa e parou sem abrir
PR. **Nenhum trabalho foi duplicado.**

Antes disso, porém, o segundo robô entrou na bancada do primeiro e escreveu dois
arquivos dentro dela:

```
services/pages/apps/portfolio/__init__.py
services/pages/apps/portfolio/migrations/__init__.py
```

Ambos vazios. A prova de que nada foi destruído veio depois: os `.pyc` que o
primeiro robô já havia gerado mostram `co_consts = (None,)`, ou seja, os
originais também eram vazios. O segundo robô não commitou, não trocou de ramo e
removeu o contêiner de teste que tinha subido. Foi sorte com prova depois do
gesto, não método. Se aqueles dois arquivos tivessem conteúdo, a sobrescrita
seria silenciosa e o primeiro robô descobriria pela suíte vermelha, ou não
descobriria.

## Solução

**Quando `git worktree add` recusar porque o caminho já existe, NÃO entre na
pasta.** Pergunte ao balcão primeiro:

```bash
python ci/fila.py listar --ao-vivo    # lê o estado do origin/main e as reservas do servidor
```

- Se a tarefa aparecer `reivindicada`, você perdeu a corrida. Pare ali, **sem
  escrever um byte** dentro daquela pasta, e devolva à maestro.
- Se ela aparecer na fila e você precisar mesmo da bancada, use um sufixo
  próprio: `git worktree add ../wt-<nome>-2 -b agent/<celula>/<nome>-2 origin/main`.
  Foi o que fez, no mesmo dia, o robô que consertou a corrente da fila.

Duas cercas que valem sempre:

- **Leia do `origin/main`, nunca do espelho.** O clone principal fica semanas
  atrasado sem avisar (a [148](148-o-reconhecimento-acontece-no-espelho-velho-e-a.md)),
  e um estado velho da fila é exatamente o que faz você achar que a tarefa está
  livre.
- **Jamais apague bancada alheia.** Pedido do mantenedor em 29/08/2026: trabalho
  não commitado já morreu numa bancada apagada. A pasta que atrapalha você é o
  trabalho vivo de outro robô.

## Por que não há guarda, e por que declarar isso é a entrega

Nenhum portão do repositório vê duas sessões entrando na mesma pasta: a colisão
acontece no disco da máquina do mantenedor, e o CI só conhece o que chega em
commit. Inverter a ordem (balcão antes da bancada) fecharia esta janela e
reabriria a [192](192-pegar-a-tarefa-antes-do-worktree-deixa-o-evento-no-espelho.md),
que custou comprovante órfão com o validador respondendo verde. Trocar um buraco
medido por outro medido não é conserto. O que esta armadilha entrega é o buraco
declarado, com o gesto certo escrito, para quem topar com a pasta já criada não
inventar a recuperação errada.

## A diferença para a vizinha

A [349](349-duas-sessoes-do-mantenedor-na-mesma-obra.md) é duas sessões na mesma
OBRA sem número de tarefa: nada trancava, e por isso dois PRs nasceram. Aqui a
tarefa TINHA número, a trava FUNCIONOU e nenhum PR nasceu em dobro, e mesmo assim
houve colisão, porque o que ela tranca não é a pasta.
