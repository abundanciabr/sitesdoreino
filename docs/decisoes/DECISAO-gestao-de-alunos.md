# DECISÃO — a gestão de alunos: o que se edita na tela, o que não se edita, e por quê

> **Pedida pelo mantenedor em 28/08/2026**, ao usar a tela de alunos pela
> primeira vez: *"Os alunos aprovados não aparecem em lugar nenhum do painel.
> Quero poder gerenciá-los."* E, quando perguntado o que "gerenciar" incluía:
> *"Quero um formulário completo com vários campos para alterar o status, a
> situação, tipo (mudar de aluno para administrador, por exemplo), e etc;
> excluir, remover, e etc"*.
>
> **Status:** *isto é lei.* É também o **Rito de Contrato** (`RITOS.md` §3): a
> `alunos` ganha a porta que lista quem já é aluno e a porta que muda o estado
> de uma matrícula.
>
> Continua a `DECISAO-categorias-de-usuario.md` (mesmo dia) e a
> `DECISAO-fila-de-liberacao.md` (27/08).

---

## 1. Dois achados que mudaram o desenho antes de ele começar

Medidos em `origin/main` em 28/08/2026, antes de escrever qualquer linha:

**1.1 Não existe, em lugar nenhum, como listar quem é aluno.** A `alunos` só
sabe responder *"esta pessoa aqui é aluna?"*, um e-mail por vez
(`GET /alunos/{email}/matriculas`) — e agora *"em que categoria ela está?"*.
É por isso que os cartões **Alunos ativos**, **Acesso pausado** e **Encerrados**
mostram traço desde que nasceram: a tela foi honesta sobre uma ausência real.

**1.2 `suspensa` e `reembolsada` nunca foram usados por ninguém — e, do jeito
que estavam, não bloqueavam nada.** `grep` em `services/` não encontra uma
única linha de código que atribua esses status; e os dois estavam em
`STATUS_QUE_VALEM`, ou seja, contavam como *"é aluno"* para efeito de acesso.
Um botão "pausar" que deixasse a pessoa entrar do mesmo jeito seria decoração.

## 2. Os estados de uma matrícula, e o que cada um faz

O mantenedor foi perguntado se pausar deveria tirar o acesso e respondeu **"sem
preferência"** — a decisão voltou para o agente, com a recomendação que já
estava na mesa. Fica assim:

| Estado | Dá acesso? | Quem coloca | O que significa |
|---|---|---|---|
| `aguardando` | não | a pessoa, ao pedir | está na fila |
| `recusada` | não | o mantenedor | pediu e não foi aprovada |
| `ativa` | **sim** | compra, ou liberação | é aluno |
| `suspensa` | **não** *(mudou)* | o mantenedor | acesso pausado — volta com um clique |
| `encerrada` *(novo)* | não | o mantenedor | saiu da escola |
| `reembolsada` | **sim** *(inalterado)* | ninguém ainda | devolveu o dinheiro |

**`suspensa` sai de `STATUS_QUE_VALEM`, e isso NÃO reverte a decisão de
24/08/2026.** Aquela decisão — *"quem já foi aluno mantém a voz na Caixa"* —
foi tomada sobre **reembolso**, e `reembolsada` continua valendo acesso,
exatamente como ela manda. `suspensa` é outra intenção: é o mantenedor dizendo
*"agora não"*. Duas intenções diferentes não podem ter o mesmo efeito.

**A migração custa zero, e isso foi medido, não suposto:** como nada nunca
atribuiu `suspensa`, não há linha em produção nesse estado para mudar de
comportamento. (Se houver uma posta à mão, ela perde o acesso — e é o que a
palavra sempre prometeu.)

## 3. O que o formulário edita

Um formulário por aluno, na tela `/admin/escola/alunos/`.

| Campo | Editável | Por quê |
|---|---|---|
| **estado** | **sim** | é o pedido central: ativar, pausar, encerrar |
| **nome** | **sim** | a pessoa digitou o próprio nome; erro de digitação é comum |
| **WhatsApp** | **sim** | idem, e é por ele que o mantenedor acha a pessoa |
| **turma** | **sim** | pista de conferência, corrigível |
| **data da compra** | **sim** | idem |
| **e-mail** | **não** | é a IDENTIDADE da linha. Trocá-lo moveria a matrícula, em silêncio, para outra pessoa — e é por e-mail que todo o resto do sistema pergunta quem é aluno |
| **escola, pedido, produto** | **não** | vêm do fato que criou a linha (uma compra, um pedido de entrada). Editá-los seria reescrever o que aconteceu |
| **tipo (administrador)** | **não** | §4 |

**Toda edição gera linha de auditoria** na área administrativa, append-only,
como toda escrita desta área (`DECISAO-celula-admin` §3) — com o valor
ANTERIOR, que é o que permite reconstruir o que foi mudado.

## 4. "Mudar de aluno para administrador" NÃO é um campo desta tela

É o único item do pedido que não entra, e a razão não é esforço.

**Quem é administrador é decidido pela lista `ADMIN_EMAILS`, lida na hora, na
porta da célula `admin`** — nunca gravada, nunca vinda de outra célula. Isso é
lei em dois lugares que o mantenedor aprovou, um deles **hoje de manhã**:

- `DECISAO-celula-admin` §2: *"quem decide quem entra é esta lista, na hora,
  derivada e nunca gravada — trocar quem é admin = editar env + reiniciar"*;
- `DECISAO-categorias-de-usuario` §2.1: *"administrador é ortogonal e mora só
  na célula `admin`. Se a `alunos` pudesse responder isso, a autorização da
  área administrativa passaria a depender de uma célula de produto."*

Um campo "tipo: administrador" gravado ao lado da matrícula criaria exatamente
o caminho que as duas leis fecham: **um defeito na célula de produto viraria
acesso de administrador na plataforma inteira.** Hoje, para virar admin, é
preciso ter acesso ao servidor. Isso é uma propriedade de segurança, não um
inconveniente.

**O que a tela FAZ, então:** mostra quem é administrador (lendo a lista que já
manda), e entrega o comando pronto de uma linha para promover ou remover —
o mantenedor cola no servidor, como já faz nos outros passos dele. A tela faz o
trabalho difícil (saber o que digitar); ele faz o gesto que só ele pode fazer.

**A alternativa existe e é dele:** mover a lista de administradores para o
banco da própria célula `admin`, com auditoria — o que manteria a lei §2.1
(continua morando na `admin`) e quebraria a `DECISAO-celula-admin` §2. O preço
é real: passa a ser possível ganhar acesso de administrador sem tocar no
servidor. Fica registrado como **pergunta aberta a ele**, não como omissão.

## 5. "Excluir" apaga o acesso, não a história

O pedido dizia *"excluir, remover, e etc"*. O botão existe e se chama
**Encerrar**: a pessoa perde o acesso e sai da lista principal.

**O que ele NÃO faz é apagar a linha do banco**, e isso é decisão:

- a linha é o que permite **desfazer** (encerrar por engano volta com um
  clique) e o que dá sentido à auditoria — uma linha de auditoria apontando
  para um registro que não existe mais conta metade da história;
- e **apagar de verdade tem outra natureza**: é o direito da pessoa de sumir do
  sistema (proteção de dados), não uma ferramenta de organização do dia a dia.
  Merece botão próprio, aviso próprio e decisão própria — inclusive sobre o que
  fazer com a auditoria que menciona aquele alvo.

Fica como segunda **pergunta aberta** ao mantenedor.

## 6. Onde cada porta fica

| Porta | Quem usa | Para quê |
|---|---|---|
| `GET /matriculas` | painel admin | a lista de quem já é aluno, por estado |
| `PATCH /matriculas/{id}` | painel admin | mudar estado e corrigir os campos do §3 |

`site_id` opcional nas duas, e cada linha diz de qual escola veio — a mesma
decisão da fila (`DECISAO-categorias-de-usuario`): o painel é
plataforma-inteira (Lei 9).

**PII:** `GET /matriculas` devolve o WhatsApp, e continua sendo **porta de
painel** — a mesma família de `GET /pre-matriculas`. A lei da fila §5 diz que o
número sai *"por uma porta só, a do painel administrativo"*; as duas portas
**são** essa porta. O que segue proibido é ele aparecer em
`GET /alunos/{email}/matriculas` (a que a Caixa usa) e em evento.

---

*Relacionados: `DECISAO-categorias-de-usuario.md` §2.1 (administrador é
ortogonal) · `DECISAO-celula-admin.md` §2 e §3 (a lista de admins e a
auditoria) · `DECISAO-fila-de-liberacao.md` §5 (o WhatsApp) · `RITOS.md` §3.*
