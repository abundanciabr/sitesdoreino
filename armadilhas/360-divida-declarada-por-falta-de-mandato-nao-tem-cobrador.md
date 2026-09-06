---
schema_version: 2
armadilha: 360
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: nenhum portão lê a prosa do relatório de um robô, e um guarda que exigisse tarefa nova a cada corte reprovaria os cortes legítimos (o que foi cortado porque é escopo do degrau seguinte, que já tem tarefa); o que existe é a regra escrita aqui, e ela custa um arquivo em `fila/`, que é pasta de escrituração e não pede recibo
sinal:
  - declarei a divida
  - cortei porque o mandato
  - precisa de uma tarefa propria com mandato
  - a unica divida que este degrau deixa
---

# Dívida declarada por falta de mandato não tem cobrador: quem corta na cerca cria a tarefa no mesmo PR

**Sintoma.** Um robô chega numa cerca CODEOWNERS (`ci/`, `contracts/`, `infra/`,
`.github/`), faz a coisa certa e **para**, porque o mandato do despacho dele não
cobria aquele caminho. No relatório final ele escreve, com todas as letras, o
que ficou faltando: *"cortei porque o mandato autoriza `infra/` e proíbe `ci/`;
isto precisa de uma tarefa própria, e é a única dívida que este degrau deixa"*.

O PR pousa verde. O relatório rola para cima. **E a dívida não existe em lugar
nenhum.**

**Causa.** Esta casa tem cobrador para dois tipos de dívida, e a dívida
declarada não é nenhum dos dois: `ci/divida_do_livro.py` cobra registro do
livro, e a fila cobra trabalho que tem número no balcão. Uma frase no relatório
de um robô não está em nenhum dos dois lugares. Pior: quem a escreveu **já
terminou** quando alguém poderia agir, então não sobra nem a memória viva.

O corte em si é correto e não é o defeito. Atravessar cerca CODEOWNERS por
conveniência é violação de lei da casa; parar é o comportamento certo. O buraco
é o que acontece **depois** de parar.

**O que custou em 05/09/2026**, o dia em que isto foi medido, na obra do
portfólio do aluno: o robô do degrau 04 escreveu `infra/provisionar-pages.sh` e
não pôde ligar o guarda que vigia esse roteiro (`ci/tests/test_provisionamento_nao_perde_variavel.py`),
porque o mandato dele proibia `ci/`. Ele declarou a dívida no relatório, e
estava certo. **Ela só foi paga porque a maestro, por acaso, estava montando
naquela mesma hora uma pergunta ao mantenedor sobre outro mandato para `ci/` e
juntou as duas.** Sem essa coincidência, o guarda ficaria cego para uma célula
nova por tempo indeterminado, e nada, em lugar nenhum, diria isso a ninguém.

**Solução: quem declara a dívida cria a TAREFA, no mesmo PR.**

```bash
python ci/fila.py criar --titulo "..." --toca ci --move manutencao \
  --evidencia-exigida "..." --despacho "..."
python ci/fila.py bloquear TAR-NNN --quem "<seu nome>" \
  --motivo "espera mandato escrito do mantenedor para ci/; volta a andar com: python ci/fila.py soltar TAR-NNN"
```

Custa um arquivo, e `fila/` é pasta de escrituração (`PASTAS_DE_ESCRITURACAO`
em `ci/divida_do_livro.py`), então ele não puxa recibo do livro atrás.

Três detalhes que fazem a diferença entre uma tarefa útil e uma lápide:

- **Nasce `bloqueada`, não `na fila`.** `na fila` significa "livre para
  qualquer robô pegar", e um robô que a pegue vai criar bancada, gastar a
  reserva do almoxarife e ler tudo antes de descobrir que não pode seguir.
- **O motivo diz COMO ela volta a andar**, com o comando. Quem achar a tarefa
  daqui a um mês não vai reconstruir o raciocínio sozinho.
- **`bloqueada` é EVENTO, não edição do arquivo.** É append-only e não esbarra
  na [356](356-corrente-errada-na-fila-nao-tem-evento-que-a-conserte.md).

**E a outra metade, para quem rege:** a maestro que for pedir mandato ao
mantenedor **junta todas as dívidas do mesmo tipo numa pergunta só**. Ele é
leigo e o custo dele é a interrupção, não o número de itens dentro dela. Três
consertos em `ci/` cabem numa caixa; três caixas em sequência é que não cabem.

**Por que tarefa parada não incomoda ninguém**, e isso é medido, não promessa:
nada neste repositório lê estado de tarefa para cobrar. Uma tarefa `bloqueada`
pode esperar meses sem reprovar PR, sem aparecer como dívida e sem nag. O
custo de criá-la é um arquivo; o custo de não criá-la é a dívida sumir.

**Não confunda com a vizinha.** A [181](181-consultoria-aberta-fora-do-livro-e-invisivel-e-ninguem-cobra.md)
é o mesmo formato num domínio diferente (a consultoria que fica fora do livro e
cujo veredito ninguém cobra). Esta é sobre trabalho cortado na cerca de
permissão, e a cura é a fila, não o livro.
