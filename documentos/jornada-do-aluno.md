---
titulo: A jornada do aluno — o mapa para administrar
publico: false
ordem: 20
---

# A jornada do aluno

Todo caminho que uma pessoa pode percorrer entre chegar no site e sair da escola,
com quem decide cada passo e onde você mexe nisso.

**Este documento não traz números.** Quantas pessoas estão em cada ponto é uma
pergunta viva, e ela tem tela própria: **Painel da escola → Ver a jornada do
aluno** (`/admin/escola/jornada/`). Um número escrito aqui viraria mentira no dia
seguinte.

## Entrar com o Google não é virar aluno

A porta do Google só **reconhece** quem a pessoa é — ela nunca decide o que a
pessoa pode fazer. Qualquer um do mundo entra com o Google no meshcraft.top e vê
"Olá, Fulano" no canto.

O que separa um aluno de um estranho é o que a página oferece depois disso: o
aluno ganha o caminho da Caixa de Sugestões; quem não é, não.

Vale lembrar disso quando alguém disser *"eu consegui entrar"* — entrar no site e
ter acesso à escola são duas coisas.

## As quatro faixas, e as oito paradas

### Fora da escola

**Visitante** — abriu o site e não entrou com o Google. Vê o convite para entrar,
e nada mais. Sai daqui entrando com a conta do Google.

**Cadastrado** — entrou com o Google e nunca pediu para estudar aqui. Vê o
convite para pedir entrada, que leva ao formulário. Sai daqui pedindo entrada.

### Pedindo entrada

**Aguardando** — preencheu o formulário e espera a sua decisão. Vê há quantos
dias está esperando. Sai daqui quando você liberar ou recusar, na fila da lista
de alunos.

**Recusado** — você disse não, e escreveu o motivo. A pessoa lê o motivo e sabe
que pode pedir de novo. Sai daqui pedindo de novo — e o pedido volta limpo para a
sua fila.

### Dentro da escola

**Aluno** — tem acesso agora. Vê o caminho da Caixa de Sugestões. Sai daqui
quando você mudar a situação dela no formulário do aluno.

**Reembolsado** — devolveu o dinheiro e **continua entrando**. Foi a sua decisão
de 24 de agosto: quem já foi aluno mantém a voz na Caixa.

### Depois

**Pausado** — você desligou o acesso; volta com um clique. A pessoa vê que é
temporário e **não recebe formulário nenhum** — não há o que ela pedir. Sai daqui
quando você puser a situação de volta em Ativo.

**Ex-aluno** — saiu da escola, e a ficha continua aqui inteira. Vê que o acesso
acabou e o botão *Pedir para voltar*. Sai daqui de dois jeitos: ela pedindo para
voltar (nasce uma ficha nova), ou você pondo a situação em Ativo na ficha antiga.

## As doze passagens

Cada linha é um caminho que existe de verdade. Não existe nenhum outro: estado
não muda sozinho, e ninguém muda de estado sem passar por uma destas portas.

- **Visitante → Cadastrado** — *a pessoa*: clica em Entrar e usa a conta do
  Google.
- **Cadastrado → Aguardando** — *a pessoa*: preenche o formulário de pedido de
  entrada.
- **Aguardando → Aluno** — *você*: botão **Liberar** na fila.
- **Aguardando → Recusado** — *você*: botão **Recusar**, com o motivo escrito.
  Sem motivo o painel não deixa.
- **Recusado → Aguardando** — *a pessoa*: pede de novo. O motivo antigo é limpo.
- **Cadastrado → Aluno** — *a compra*: compra confirmada cria a matrícula direto,
  sem passar pela fila.
- **Aluno → Pausado** — *você*: situação **Pausado**.
- **Pausado → Aluno** — *você*: situação **Ativo**. Um clique, e ela volta a
  entrar.
- **Aluno → Ex-aluno** — *você*: situação **Ex-aluno**. É a única forma de tirar
  o acesso de vez.
- **Aluno → Reembolsado** — *você*: situação **Reembolsado**. O acesso continua —
  é sobre o dinheiro, não sobre a porta.
- **Ex-aluno → Aguardando** — *a pessoa*: botão **Pedir para voltar**. Nasce uma
  ficha nova; a antiga vira história.
- **Ex-aluno → Aluno** — *você*: situação **Ativo** direto na ficha antiga, sem
  esperar a pessoa pedir.

## Onde você mexe

**Painel da escola** (`/admin/escola/`) — a porta. Daqui se chega aos alunos e a
este mapa em versão viva.

**A jornada, com os números de agora** (`/admin/escola/jornada/`) — quantas
pessoas em cada parada, e um clique leva à lista de cada uma.

**A fila e os alunos** (`/admin/escola/alunos/`) — quem espera (com nome,
e-mail, WhatsApp e dias de espera) e quem já passou da fila, cada um com o
formulário completo. Tem busca por nome, e-mail ou turma, filtro por situação, e
o formulário de **cadastrar alguém à mão** para quando a pessoa não consegue usar
o do site.

**O prontuário** (`/admin/escola/alunos/prontuario?email=…`) — a história inteira
de um e-mail: todas as passagens, em ordem, com quem decidiu o quê e quando.

## Três regras que valem a pena ter na cabeça

**Nenhuma ficha se apaga.** Tirar o acesso tem uma forma só — a situação
**Ex-aluno**. A ficha fica com a data da saída, e quem sai pode pedir para
voltar. Você decidiu isso em 29 de agosto, e o botão que apagava foi removido do
sistema junto com a porta que ele usava.

**Quem ganha acesso é avisado.** Ao liberar alguém — da fila ou religando quem
estava pausado — a pessoa recebe um recado no sininho do site. Perder o acesso
**não** gera aviso: quem está pausado ou encerrado não consegue abrir a página de
avisos, porque ela mora dentro da Caixa, e a Caixa só abre para aluno.

**O aviso nunca impede a liberação.** Se a peça que traduz o e-mail estiver fora
do ar, a liberação acontece do mesmo jeito e o aviso simplesmente não sai. Você
clicar em Liberar e nada acontecer, por causa de uma peça de notificação, seria
muito pior que um aviso a menos.
