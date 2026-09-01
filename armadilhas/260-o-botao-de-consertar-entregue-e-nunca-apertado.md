---
schema_version: 2
armadilha: 260
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: `nenhum portao do CI consegue saber que um workflow de disparo manual DEVIA ter sido disparado: o gatilho e humano por desenho, e um portao que exigisse um run por PR reprovaria todos os outros. A cura e de METODO, e cabe numa frase: quem entrega um botao aperta o botao na MESMA sessao, e prova com o id do run no registro. Se nao puder apertar, o registro nasce com precisa_do_dono: true, para a caixa de entrada do mantenedor cobrar por ele.`
sinal:
  - `workflow_dispatch`
  - `eu disparo`
  - `voce nao precisa colar nada`
---

# O botão de consertar foi entregue, ficou verde, e ninguém nunca o apertou

**Sintoma.** Uma tela abre vazia. O diagnóstico é feito e está certo, o conserto
entra num PR, o CI fica verde, o deploy também, e o registro no livro diz, com
todas as letras, *"você não precisa colar nada: eu disparo"*. Horas depois a tela
continua **exatamente igual** — vazia. Nada está vermelho em lugar nenhum.

**Medido em 31/08 → 01/09/2026.** A tela `/admin/economia/` abriu sem nenhuma
regra porque a economia nunca fora semeada em produção. O conserto foi o
workflow `semear-economia.yml` (PR #796), mergeado às 22:52 com deploy verde. A
conferência do dia seguinte:

```
gh api repos/<dono>/<repo>/actions/workflows/semear-economia.yml/runs --jq '.total_count'
0
```

Zero execuções. O botão existia, estava verde, testado, documentado — e a tela
do mantenedor tinha passado a madrugada inteira vazia, pelo mesmo motivo de
antes.

**Causa.** Entregar a CAPACIDADE de consertar e CONSERTAR são dois fatos
diferentes, e o rito só mede o primeiro. Todo mecanismo desta casa vigia o PR: a
muralha, o portão de pouso, o deploy, o alarme da `main`. Um `workflow_dispatch`
nasce fora desse alcance por definição — ele existe justamente porque alguém
precisa decidir apertá-lo. Quando a sessão que o entrega termina no merge (o
rito manda pedir pouso e ir embora), o aperto fica órfão: não há PR pendente, não
há check vermelho, não há dívida no livro. Só a tela, que continua igual, e
ninguém olhando para ela.

É primo do `armadilhas/253` (*arquivo corrigido, deploy verde, página no ar com o
texto antigo*) e da lição que o fórum e a economia repetiram em dois dias
seguidos: **publicar o código de uma parte do sistema e POVOAR essa parte são
dois passos, e o segundo não acontece sozinho.** A diferença é onde o passo se
perde: lá, alguém esqueceu que ele existia; aqui, alguém o escreveu, o prometeu
por escrito no livro, e mesmo assim ele não aconteceu.

**Solução.**

1. **Quem entrega um botão aperta o botão na mesma sessão**, depois do merge e do
   deploy verde, e põe o **id do run** na evidência do registro. Sem o id, o
   livro registrou uma intenção, não um fato.
2. **Se não puder apertar** (depende de um segredo, de uma janela, de uma decisão
   do dono), o registro nasce com `precisa_do_dono: true`. A caixa "Precisa de
   você" é CALCULADA e não esquece; uma frase no meio de um `detalhe` esquece.
3. **Ao retomar qualquer frente, meça o estado, não leia a promessa.** Um
   `total_count: 0` numa linha responde o que três registros bem escritos não
   respondem. Vale para workflow de disparo manual, para passo de VPS e para
   qualquer conserto cujo último passo seja um dedo humano.

**Como conferir em uma linha:**

```
gh api repos/<dono>/<repo>/actions/workflows/<nome>.yml/runs --jq '.total_count'
```

Zero num workflow que já deveria ter rodado é a assinatura desta armadilha.
