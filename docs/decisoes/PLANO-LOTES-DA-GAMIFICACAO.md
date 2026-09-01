# PLANO — os lotes que fecham a gamificação

**Escrito em 01/09/2026**, a pedido do mantenedor, no fim do dia em que a célula
saiu de 9 para 14 degraus prontos. Ele é a ponte entre duas coisas que já
existem e não se falavam: a **escada de 23 degraus** do
`PLANO-CELULA-GAMIFICACAO.md` §6 e o **RUNBOOK-LOTES.md**, que diz como reger
vários robôs em paralelo.

Este documento NÃO é um painel: não guarda estado e não se atualiza sozinho.
Quem responde *"isto foi feito?"* é o livro (`painel/registros/`) e a fila
(`fila/`). O que ele responde é outra pergunta, e só ela: **em que ordem, e em
que companhia, os degraus que faltam devem ser tocados.**

---

## §1 Onde a escada está, em 01/09/2026

**14 degraus de 23.** Prontos: 0 (mapa), 1 (gênese), 2 (registro), 3 (modelos),
4 (contrato), 5 (provisionamento), 6 (infra), 7 (porta e Base), 8 (motor de XP),
9 (cartas de celebração), 12 (medalhas e marcos), 13 (painel da equipe),
16 (porta de máquina) e 17 (o fórum fala e a gamificação escuta).

**Faltam nove:** 10, 11, 14, 15, 18, 19, 20, 21, 22.

---

## §2 A restrição que decide o desenho dos lotes

**Um PR toca uma célula** (CONSTITUICAO Lei 2.3, e a cerca do CI faz valer), e
duas tarefas da mesma célula **não correm em paralelo** — viram fila interna
(RUNBOOK §1).

E aqui está o fato que manda neste plano: **cinco dos nove degraus que faltam
são todos da célula `gamificacao`** (10, 11, 14, 15, 19). Eles são o miolo, e o
miolo é serial por construção. Os outros quatro moram nas vizinhas: 18 no
`forum`, 20 no `funil`, 21 no `sugestoes` **e** no `funil`, 22 na própria
`gamificacao`.

**A receita que sai disso:** lotes de 3 a 4 despachos, com **no máximo UM de
gamificação por lote**. O paralelismo real vem de intercalar as células
vizinhas — não de espremer a gamificação, que não comprime.

---

## §3 Os lotes, na ordem

A regra 1 do runbook manda ordenar pelo dinheiro. A gamificação não é caminho de
cobrança, então a pergunta equivalente, e é ela que ordena o que vem abaixo:
**o que separa o aluno de VER que existe progresso?**

### Lote A — as quatro bordas

Quatro células distintas, quatro robôs em paralelo. É o lote de maior retorno
por hora do plano inteiro: hoje o progresso só aparece para quem abre
`/conquistas` de propósito.

| # | despacho | célula | por que |
|---|---|---|---|
| 22 | a medalha de **Fundador** para quem já estava | `gamificacao` | **canário**: um comando idempotente e um registro. Se ele atravessa PR, portão, merge e deploy, a esteira está provada hoje (RUNBOOK §3 regra 2) |
| 18 | a etiqueta "Nv 7 · Modelador" ao lado de quem escreve | `forum` | o lugar com mais gente passando |
| 20 | o quadrinho de progresso na home de quem entrou | `funil` | a primeira tela depois do login |
| 21a | as frases dos avisos novos na tela do sininho | `sugestoes` | hoje a carta de nível chega e cai no texto genérico |

**O que este lote devolve ao mantenedor:** UM bloco único de colar, com as duas
senhas de máquina que 18 e 20 exigem (`forum→gamificacao` e `funil→gamificacao`).
Elas são passo dele por lei (INV-P8, Lei 5) e vêm juntas de propósito — dois
blocos em dias diferentes é o que transforma um passo de trinta segundos numa
pendência de semana.

**Fica FORA deste lote, e é de propósito:** 21b (o texto do aviso no celular)
também mora no `funil`, e duas tarefas da mesma célula não correm em paralelo.
Ela entra no lote seguinte.

### Lote B — a Forja

| # | despacho | célula |
|---|---|---|
| 14 | o medidor de tentativas por desafio, e o selo na obra | `gamificacao` |
| 21b | o texto do aviso no celular para os assuntos novos | `funil` |
| — | um despacho de outra frente do site, à escolha do mantenedor | qualquer |

A Forja destrava a medalha "Dez forjas" — a segunda medalha automática que a
escola consegue conceder — e põe na obra o atributo que o VEREDITO chama de
prova de insistência.

### Lote C — a Galeria

| # | despacho | célula |
|---|---|---|
| 19 | post do fórum vira card de obra, curadoria, Destaques da semana | `gamificacao` |
| — | dois despachos de outras frentes | quaisquer |

É o **coração** segundo a consultoria (*"a obra é a unidade central"*), e o
degrau que destrava duas coisas de uma vez: a medalha "Primeira obra" e a
quarta carta de celebração (`gamificacao.destaque-da-semana`), que está
congelada desde 30/08 e nunca teve fato para sair.

### Lote D — a Sequência semanal

O "não faltei esta semana", com escudo automático e Modo Férias. Célula
`gamificacao`, mais dois de outras frentes.

### Lote E — as Missões

Diárias, semanais e a Encomenda da Semana. Célula `gamificacao`, mais dois de
outras frentes.

### Lote F — a Loja

Os Cristais viram decoração do Meu Estúdio. Vem por último porque só faz sentido
quando já há Cristal circulando — e quem os cria hoje são as medalhas.

---

## §4 O que NÃO cabe em lote nenhum

Está aqui para ninguém tentar empurrar para dentro de um brief:

- **Ligar as regras e as conquistas.** É decisão do mantenedor, na tela dele
  (`/admin/economia/`), com data. Um robô que ligasse por conta própria estaria
  mudando a economia que ninguém decidiu.
- **Os dois passos de VPS** (as senhas de máquina do Lote A). Credencial não
  viaja por esteira (Lei 5).
- **Cristais por regra de evento.** Mexe no vocabulário fechado que o [INV-GAM1]
  protege — é decisão dele, e de outro dia.
- **O portão da Camada 1:** conferir as regras de idade vigentes do Roblox e do
  Fiverr **antes** de ligar os marcos de carreira. É conferência de fato externo,
  não código.
- **O ritmo do aviso** (*"máx 1/dia, nunca depois das 20h"*, § do plano da
  célula). É regra de ENTREGA, nenhuma camada a implementa, e escolher onde ela
  mora é decisão de produto.

E duas dívidas técnicas que podem virar despacho quando ele quiser, mas não
bloqueiam nada:

- **O estorno da mensagem removida.** O fórum já emite o fato; falta a ligação
  da mensagem para o lançamento que a pagou (o ledger guarda o id do EVENTO).
  Declarado em `handlers.NAO_CREDITAM`, com teste.
- **O quiz não dá XP.** O contrato dele identifica por e-mail; falta
  `findPersonByEmail`, já congelada na `identidade`.

---

## §5 Como o mantenedor dispara

Numa janela NOVA do Claude Code, no PC dele (`PS C:\>`):

```
Leia RUNBOOK-LOTES.md e docs/decisoes/PLANO-LOTES-DA-GAMIFICACAO.md
e toque o Lote A.
```

Sessão nova, e não a que escreveu isto: a maestro precisa de contexto folgado
para reger N agentes e ainda conduzir a janela de merge serial. Robô afogado em
documentação erra mais e custa mais (RUNBOOK §3 regra 3) — e a sessão que
escreveu este plano já vem carregada do dia inteiro.

`um lote menor (3 despachos)` gasta a franquia mais devagar. É o mesmo trabalho
total, com o ritmo mais suave.
