---
schema_version: 2
armadilha: 221
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: teste
  detector: ci/tests/test_conferencia_do_toca.py::test_todo_toca_das_tarefas_reais_aponta_para_algo_que_existe
  motivo: o mesmo guarda que reprovou a genese agora conhece a terceira causa legitima, e continua reprovando as duas primeiras porque a dispensa exige declaracao escrita no arquivo da tarefa
sinal: null
---

# O guarda do `toca` não sabia expressar a gênese: a tarefa que CRIA a célula reprovava por declarar a célula que ela mesma inaugura

**Sintoma.** A muralha reprova um PR que só acrescenta tarefas à fila, com esta
mensagem:

```
AssertionError: `toca` apontando para caminho que não existe: TAR-031: gamificacao, TAR-032: gamificacao
FAILED ci/tests/test_conferencia_do_toca.py::test_todo_toca_das_tarefas_reais_aponta_para_algo_que_existe
```

O `toca` está certo, o nome está certo, e não houve rename nenhum. A pasta
simplesmente ainda não existe, porque quem a cria é a própria tarefa que a
declara.

**Causa.** `test_todo_toca_das_tarefas_reais_aponta_para_algo_que_existe` exige
que toda área declarada por uma tarefa aponte para caminho existente, e o
docstring dele enumerava DUAS causas de falha, as duas defeitos: vocabulário
errado, e pasta renomeada sem avisar a fila. Falta a terceira, e ela não é
defeito: **a tarefa de gênese**. A fila nasceu em 29/08/2026 num repositório
onde todas as células já existiam; a primeira célula a nascer DEPOIS dela
encontrou um guarda que não tinha como ser convencido.

O efeito é grande e silencioso até acontecer: enquanto durar, **nenhuma célula
nova pode nascer pela fila**. Ou o robô declara um `toca` mentiroso (e a
conferência do diff passa a alertar contra ele, com razão), ou o trabalho de
gênese fica fora do balcão, que é onde o RITOS §5 manda tarefa morar.

**Solução.** Uma porta explícita, e só ela: o campo opcional `cria` no arquivo
da tarefa, no MESMO vocabulário do `toca`.

```
python ci/fila.py criar --titulo "..." --toca gamificacao --cria gamificacao ...
```

Lê-se "eu mexo nesta célula, e sou eu quem a inaugura". `areas_criadas`, em
`ci/conferencia_do_toca.py`, é a única leitura desse campo, e o guarda dispensa
da existência apenas o que a tarefa assumiu por escrito.

**Por que a dispensa não afrouxa o guarda.** Porque ela exige uma frase que
ninguém escreve por acidente. Erro de digitação (`gamifikacao`) continua
reprovando, pasta renomeada continua reprovando, e declarar a criação de uma
coisa não absolve o nome errado de outra — há teste para cada um dos três. A
dispensa também vale só na janela entre a tarefa nascer e a célula existir:
depois disso a pasta está lá, e a conferência do diff nem precisa dela, porque
o PR da gênese declara a célula em `celulas.yml` e aí o `toca` e o diff se
encontram sozinhos.

**Prova.** Vermelho→verde por asserção, sem rede: uma tarefa temporária
declarando `toca: [gamificacao]` sem `cria` deixa o guarda em `1 failed`; a
MESMA tarefa com `cria: [gamificacao]` passa. Antes disso, a medição de fora:
o PR #624 reprovou na muralha do GitHub com a mensagem acima.

**Origem.** 30/08/2026, ao enfileirar a escada da célula de gamificação
aprovada pelo mantenedor na Sessão A (registro `20260830-061`). Custo: uma
rodada de CI e o lote parado até o conserto.
