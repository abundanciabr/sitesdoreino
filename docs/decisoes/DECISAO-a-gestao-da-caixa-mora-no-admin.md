# DECISÃO — a gestão da Caixa mora no Admin, e em nenhum outro lugar

> **Tomada pelo mantenedor em 28/08/2026**, em sessão, com as opções e os custos
> na mesa. Este documento é **lei** para tudo que vier depois. Ele complementa
> `DECISAO-EVO-01-identidade.md` (§3, o e-mail), `DECISAO-EVO-40-quem-aprova-e-quem-e-avisado.md`
> (os dois papéis) e `DECISAO-celula-admin.md` (a porta).
>
> A frase dele, e é a regra inteira em uma linha:
> *"não vamos espalhar painéis ou gestão por aí, tudo será em /admin"*.

---

## 1. O que foi decidido

O painel de gestão da Caixa de Sugestões — entregue em 28/08/2026 em
`meshcraft.top/forms/sugestoes/gestao`, com três abas — **muda de casa**. Ele
passa a morar em **`/admin/caixa/`**, dentro da área administrativa, e o endereço
antigo deixa de servir a gestão.

Não é um atalho nem um link: **é mudança de endereço**. Os dois não coexistem —
coexistir seria exatamente o "espalhar" que a decisão proíbe.

A Caixa volta a ser **só o lugar do aluno**: escrever, votar, comentar,
acompanhar, receber aviso.

### O endereço, e por que não foi o pedido ao pé da letra

Ele pediu `/admin/painel/gestao-caixa`. Esse caminho **já tem dono**:
`/admin/painel/` é onde a célula `admin` serve o livro de ocorrências do
projeto (`painel/painel.html` e os arquivos dele, via `painel_arquivo`). Pôr a
gestão ali criaria colisão de rota com uma superfície que já existe.

O endereço escolhido é **`/admin/caixa/`**, na mesma gramática de
`/admin/escola/` — e ele confirmou, sabendo da alternativa de aninhar em
`escola/`: a Caixa é uma ferramenta inteira, com vida própria, e espremê-la
dentro de "Escola" a transformaria num porão.

---

## 2. Por que isto custa um contrato (e não é burocracia)

**Lei 3: nenhuma célula lê o banco de outra.** A Caixa guarda as ideias; o Admin
não pode ir buscá-las. O que se faz é o Admin **perguntar** e a Caixa
**responder**, por uma superfície congelada que não muda por acidente — o mesmo
desenho que a tela de alunos do Admin já usa com a célula `alunos`.

Criar essa superfície é **Rito de Contrato** (`RITOS.md` §3), e é a única parte
que exigiu o mantenedor presente. A sessão aconteceu em 28/08/2026 e produziu
as duas decisões da §3.

### A forma do contrato: DOMÍNIO, não tela

`listManagementIdeas` devolve os **fatos** de cada ideia — votos, plateia,
estado, datas, se tem avaliação, se tem ChangeSpec — e **não** as colunas, os
baldes nem a ordem. Quem agrupa é o Admin.

A escolha não é estética: um contrato com forma de TELA precisaria de um Rito
novo (uma conversa com o mantenedor) **a cada ajuste de layout**. Um contrato com
forma de domínio deixa a tela evoluir de graça.

A única conta que viaja PRONTA é a **plateia** — quantas pessoas distintas estão
atrás de cada ideia. Ela é definição desta célula (`[INV-SUG13]`) e é a mesma
gente que o sininho vai avisar; recalculá-la do outro lado da fronteira criaria
uma segunda verdade sobre quantas pessoas esperam.

---

## 3. As duas decisões do mantenedor

### 3.1 Quem modera: **uma lista só** — a do Admin

**Decidido: quem entra no Admin (`ADMIN_EMAILS`) modera as ideias.**
`SUGESTOES_STAFF_EMAILS` deixa de governar essas ações, e a `sugestoes` confia no
Bearer do par — o token é justamente a afirmação de que o chamador já passou pela
porta fail-closed do Admin.

**Esta escolha foi feita CONTRA a recomendação da sessão, e com a consequência na
mesa.** A recomendação era manter duas listas, por coerência com o que ele mesmo
decidiu em 25/08 (separar "moderar" de "autorizar obra", sabendo que custava uma
lista a mais). Ele escolheu a lista única.

**A consequência, escrita por extenso para nenhuma sessão futura tratá-la como
descuido:** dar acesso ao Admin a alguém passa a dar, **no mesmo gesto**, o poder
de mudar a fase das ideias dos alunos e escrever a avaliação interna. Não há
segundo passo, não há segunda lista, e ninguém será avisado disso na hora.

Se um dia isso incomodar, o conserto é uma decisão nova — não um "ajuste" que
alguém faz por achar que a lista única foi esquecimento.

### 3.2 O e-mail do aluno: **continua sem sair**

**Decidido: as telas do Admin mostram o nome de quem sugeriu, nunca o e-mail.**
Mantém a `DECISAO-EVO-01` §3 — o e-mail vive numa linha só, dentro da Caixa.

Ele considerou a alternativa (o Admin ver o e-mail, como já vê o telefone na
tela de alunos) e recusou: hoje não precisa dele para decidir nada, e abrir um
dado pessoal "por via das dúvidas" é o tipo de coisa que ninguém volta a fechar.

Há guarda mecânico: `test_o_email_do_aluno_nao_atravessa` varre o **corpo
inteiro** da resposta em texto, não os campos que alguém lembrou de conferir —
um campo novo que carregue e-mail por descuido cai ali sem ter sido previsto.

---

## 4. O que NÃO mudou, e não muda

**A assinatura de obra continua sendo da Caixa, e continua sendo só dele.**
`registerApprovedChangeSpec` recusa quem não estiver em `SUGESTOES_APROVADORES`,
e a lista vazia recusa todo mundo — o fail-closed do EVO-40, intacto. Estar
autorizado no Admin **não basta**; há guarda para isso
(`test_estar_no_admin_nao_da_o_direito_de_assinar`).

Mudar de casa a tela não afrouxa a lei. As três escritas do contrato passam pelos
**mesmos caminhos** que as telas usavam — `registrar_mudanca_de_status` e
`changespecs.registrar` —, então o histórico continua nascendo na mesma transação
da mudança, a plateia inteira continua sendo avisada, "não vamos fazer" continua
exigindo justificativa e `planejado → em desenvolvimento` continua exigindo o
corredor. Reimplementar qualquer uma dessas regras do lado do Admin seria abrir
uma segunda porta para o mesmo cofre.

### Uma exigência que a mudança revelou

`[INV-SUG12]` diz que toda mudança de status vira carta endereçada, e que quem
moderou precisa ter o **id que atravessa a plataforma**. Vindo pelo contrato, o
Admin tem de enviá-lo (`por_id_da_plataforma`) — ele já o possui, é o mesmo
`SessionFull.id` com que abriu a própria porta. Quando faltar, a Caixa **recusa
com instrução em português** em vez de estourar: a pessoa entra uma vez no site e
a porta grava o dado. Descobrir isso foi o que a primeira rodada de testes deu.

---

## 5. O caminho, em etapas

1. **O contrato** — PR só de `contracts/`, com a label `contrato` (este PR).
2. **O provedor** — a `sugestoes` aprende a responder e a aceitar. *Provedor
   primeiro* é a regra da §3 do RITOS.
3. **O consumidor** — o Admin ganha `/admin/caixa/` com as três abas.
4. **As ações** — mudar fase, avaliar e assinar de dentro do Admin.
5. **A mudança de casa se completa** — as telas de gestão saem da Caixa e o
   endereço antigo passa a redirecionar. Só aqui a decisão está cumprida: até
   este passo, existem dois lugares, que é o que ela proíbe.

---

*Relacionados: `RITOS.md` §3 (o rito) · `CONSTITUICAO.md` Lei 3 (banco por
célula) · `DECISAO-EVO-01-identidade.md` §3 (o e-mail) ·
`DECISAO-EVO-40-quem-aprova-e-quem-e-avisado.md` (os dois papéis) ·
`INVARIANTES.md` `[INV-SUG10]`, `[INV-SUG12]`, `[INV-SUG13]` ·
`docs/paineis/painel-da-caixa-de-sugestoes/` (a planta das telas).*
