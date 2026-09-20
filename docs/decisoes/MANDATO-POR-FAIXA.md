# MANDATO POR FAIXA: o que já está autorizado, e o que nunca está

**Data:** 20/09/2026
**Quem decidiu:** o mantenedor, na sessão, com as duas listas fechadas por ele
**Estado:** vigente
**Mede o quê:** os vãos longos entre commits, medidos em 20/09/2026

## O problema

Nos PRs de 19/09/2026, reconstruídos commit a commit pelo `gh` em 20/09/2026,
quatro concentram os maiores vãos entre commits consecutivos:

| PR | Parou | Voltou | Vão |
|---|---|---|---:|
| 1768 | 16:23 | 16:57 | 33,6 min |
| 1773 | 17:45 | 19:32 | 107,4 min |
| 1788 | 19:41 | 20:33 | 51,1 min |
| 1784 | 19:41 | 21:49 | 128,4 min |

Os horários estão em `America/Sao_Paulo`, e isso importa: os carimbos do Git são
UTC, e lidos como hora local eles fazem parecer que um dos vãos atravessou a
janela em que a máquina fica desligada. Nenhum atravessou. **Os quatro vãos
inteiros, 320,6 minutos, aconteceram com a máquina ligada**, e o último terminou
às 21h49, dezenove minutos depois da hora em que já não se começa nada.

Do primeiro ao último commit, esses mesmos quatro PRs levaram 113,35, 179,75,
105,82 e 204,73 minutos, na ordem da tabela, contra uma mediana de 19,33 minutos
nos 57 PRs de ramo `agent/` pousados em 19 e 20/09/2026. O trabalho é o mesmo.

O que os dados **não** dizem é a causa. Nos PRs 1768 e 1773 o commit que encerra
o vão é um merge da `main`, ou seja, máquina esperando outro PR pousar, não
pessoa decidindo. Nenhum carimbo prova espera por autorização.

O que se sabe sem medir é mais simples, e basta para esta decisão: hoje o agente
só descobre que precisa da palavra do mantenedor quando o ramo já está pronto, e
pedir naquele instante transforma trinta segundos de resposta em horas de ramo
aberto. A aposta deste documento é que trocar o instante do pedido encurta o
ciclo. Se os vãos sumirem e o ciclo não encurtar, a aposta estava errada.

## Lista A: exige mandato nominal do mantenedor, sempre, antes de tocar

1. Pagamento e cobrança
2. Servidor e infraestrutura
3. Senhas e chaves

Estes três nomes são a autoridade. Os caminhos literais de cada um são
derivados de `celulas.yml` e da pasta `infra/` por `ci/mandato_por_faixa.py`,
nunca colados numa lista à parte. Lista colada envelhece em silêncio no dia em
que uma célula muda de pasta, e um caminho de pagamento fora da lista é um
caminho sem dono.

Em 20/09/2026 os três nomes resolvem para 2 caminhos de pagamento e cobrança
(`services/checkout/` e `services/pagamentos/`), 1 de servidor (`infra/`) e 41
de senhas e chaves. Os 41 são os arquivos de ambiente do repositório mais os
workflows de `.github/` que sacam do cofre de segredos. Essa última parte é
deliberada e é apertada: mexer num workflow que lê `secrets.` passa a exigir a
palavra dele. Um item chamado "senhas e chaves" que cobrisse só os moldes
`.env.exemplo`, onde não há segredo nenhum, seria cobertura de mentira. A conta
do dia sai no próprio comando.

## Lista B: mandato prévio por faixa, concedido de uma vez

Documentos, painel, fila, testes, e os arquivos normais da faixa da tarefa.

O mandato para esses caminhos já está dado, por este documento, para toda
tarefa cuja faixa os contenha. Não se pede de novo a cada PR.

## A regra de colisão

Um PR que toque qualquer caminho da Lista A é Lista A inteiro, mesmo que a
maior parte dele seja Lista B.

Na dúvida sobre a classificação de um caminho, ele é Lista A. A dúvida é
resolvida pelo mantenedor, nunca pelo despacho.

## O que NÃO muda

A linha `Mandato-do-mantenedor:` continua obrigatória no corpo de todo PR que
toque caminho de `CODEOWNERS`, e `ci/mergear.py` continua a conferir que o
caminho aparece nela como token separado por espaço. O que muda é o que a linha
**cita**:

- PR de Lista A: cita o pedido do mantenedor, os caminhos autorizados e a
  origem (a sessão e a data), exatamente como hoje.
- PR de Lista B: cita a faixa da tarefa e este documento, no lugar da sessão e
  da data.

Isto não é ausência de mandato. É mandato dado uma vez, por escrito, em vez de
mandato pedido toda vez.

## Como o agente descobre em que lista está, antes de construir

```bash
$ python ci/mandato_por_faixa.py --arquivos services/pagamentos/Dockerfile
LISTA A: exige mandato nominal antes de editar
  services/pagamentos/Dockerfile é pagamento e cobrança

$ python ci/mandato_por_faixa.py --arquivos painel/registros/nota.js --faixa admin
LISTA B: mandato prévio por faixa, concedido por docs/decisoes/MANDATO-POR-FAIXA.md
```

Sai 1 na Lista A e 0 na Lista B, antes da primeira edição, e não depois do PR
pronto. Com `--corpo-arquivo` ele julga também a linha do PR, cobrando na Lista
B as mesmas cercas de `CODEOWNERS` que `ci/mergear.py` vai cobrar no pouso. Um
pré-voo que aprovasse o que o pouso recusa seria pior que pré-voo nenhum.

## O que o agente faz quando cai em Lista A sem mandato

Ele não espera. Nesta ordem:

1. leva o ramo a ponto seguro, com commit e push do que existe e os testes no
   estado em que estiverem, dito no relatório. Trabalho pela metade se
   preserva, nunca se apaga;
2. escreve no balcão o que falta, em uma frase, com o caminho ou a decisão
   exata que destrava (`python ci/fila.py bloquear TAR-NNN --quem <agente>
   --motivo "<o que trava, e o que destrava>" --espera mantenedor`), e deixa o
   registro com `precisa_do_dono: true`;
3. devolve à maestro e encerra o seu turno.

Robô ocioso de ramo aberto é o custo que esta decisão existe para eliminar. Quem
pergunta ao mantenedor é a maestro, e ela pergunta com o trabalho guardado.

## A hora de parar

A partir das 21h30 em `America/Sao_Paulo`, nenhum agente que constrói começa
caixa nova do plano: fecha ou bloqueia a que está aberta, pelos três passos
acima, e devolve à maestro.

A máquina do mantenedor desliga por volta das 22h. Trabalho pendurado nesse
instante não perde só as horas da noite: perde o contexto da sessão e deixa ramo
aberto sem dono. O PR 1784 voltou a commitar às 21h49, onze minutos antes disso.

O fuso está escrito porque o contêiner da bancada marca UTC, e entre 21h e 24h
em Brasília as duas datas são diferentes, que é como `armadilhas/158` nasceu.
Um agente que leia `date` sem fuso ou nunca para, ou para às 18h30:

```bash
python -c "import datetime, zoneinfo; print(datetime.datetime.now(zoneinfo.ZoneInfo('America/Sao_Paulo')).strftime('%H:%M'))"
```

## O que este documento não faz

- Não altera workflow, `infra/`, `celulas.yml` nem comportamento de produção.
- Não mexe nos portões do pouso. A volta de checks mede p50 de 155 s e p90 de
  164 s em 50 amostras, por `ci/medir_tempos.py`: a conferência é barata e fica
  como está.
- Não toca a fila de deploy, que segue no degrau A com mandato próprio.
- Não revoga a exigência de mandato.

## Como se muda este documento

As duas listas são do mantenedor e vieram fechadas em 20/09/2026. Acrescentar
item a qualquer uma delas é decisão dele, não do despacho. Um despacho que
receba pedido de acrescentar item recusa e devolve à maestro.

## Como se sabe se funcionou

Trinta dias depois do merge, um registro `medicao` em `painel/registros/`
compara contra esta linha de base, reconstruída pelo `gh` em 20/09/2026:

| Medida, nos PRs de ramo `agent/` pousados em 19 e 20/09/2026 | Linha de base | Meta |
|---|---:|---:|
| PRs medidos | 57 | não é alvo |
| Mediana do primeiro ao último commit | 19,33 min | cai |
| Vãos entre commits de 30 min ou mais | 19, somando 2313,9 min | nenhum com a máquina ligada |
| Vãos da tabela acima, todos com a máquina ligada | 4, somando 320,6 min | 0 |

Falta o instrumento para a conta inteira. Nenhum comando da casa mede vão entre
commits nem separa a janela desligada, e a linha de base acima é conta à mão.
A conferência que dá para fazer em trinta dias sem instrumento novo é mais
estreita, e é esta: contar, com `gh pr list`, quantos PRs de Lista A saíram com
a linha `Mandato-do-mantenedor:` já escrita no primeiro commit em vez de no
último. Hoje esse número é zero, porque a linha só existia no fim.

Se os vãos sumirem e a mediana não cair, a causa apontada aqui estava errada, e
o registro diz isso com todas as letras. A tarefa seguinte volta à construção
com outra hipótese, e a primeira candidata já está nos dados: em dois dos quatro
vãos, o que a máquina esperava era outro PR pousar.

## Fontes

- `gh pr view <N> --json commits`, de onde saíram os carimbos da tabela.
- `ci/medir_tempos.py`, a régua das esperas de check e deploy.
- `ci/mandato_por_faixa.py`, a tradução dos três nomes da Lista A em caminhos.
- `.github/CODEOWNERS`, as fronteiras que `ci/mergear.py` confere.
- `docs/decisoes/DECISAO-merge-sem-rito-de-pouso.md`, a integração automática.
